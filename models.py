
from pathlib import Path
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QAbstractTableModel, QThreadPool
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPen, QFont, QColor

STATUS_ACTIVATED = "Activated"
STATUS_USERDISABLED = "UserDisabled"
STATUS_SYSTEMDISABLED = "SystemDisabled"


@dataclass
class PackageRow:
    name: str
    status: str
    raw_index: int
    category: str = "Other"
    vendor: str = ""
    sim: str = "fs24"
    source: str = "official"
    original_status: str = field(default=None)
    thumbnail_path: str = None

    @property
    def readonly(self) -> bool:
        return self.status == STATUS_SYSTEMDISABLED


class PackageTableModel(QAbstractTableModel):
    THUMB_WIDTH = 160
    THUMB_HEIGHT = 90

    def __init__(self, rows, thumb_cache=None, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._thumb_cache = thumb_cache
        self._thumb_pix: dict[str, QIcon] = {}
        self._loading: set[str] = set()

        # Ensure original_status is set for dirty tracking
        for r in self._rows:
            if getattr(r, "original_status", None) is None:
                r.original_status = r.status

        # Placeholder & "Not Found" tiles
        placeholder_path = Path(__file__).parent / "icons" / "placeholder.png"
        self._placeholder = (
            QIcon(str(placeholder_path)) if placeholder_path.exists() else QIcon()
        )
        self._not_found_icon = self._make_not_found_icon()

        # Async thumbnail jobs
        from thumbnails import ThumbSignals, ThumbJob
        self._signals = ThumbSignals()
        self._signals.ready.connect(self._on_thumb_ready)
        self._pool = QThreadPool.globalInstance()
        try:
            self._pool.setMaxThreadCount(3)  # keep UI smooth
        except Exception:
            pass

    # ----- helpers -----
    def _make_not_found_icon(self) -> QIcon:
        w, h = self.THUMB_WIDTH, self.THUMB_HEIGHT
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        # soft grey tile
        tile = QColor(120, 120, 120, 40)
        p.fillRect(0, 0, w, h, tile)
        # dashed border
        pen = QPen(QColor(200, 120, 120, 200))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(2, 2, w - 4, h - 4, 8, 8)
        # text
        p.setPen(QColor(220, 140, 140, 240))
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        txt = "Not Found"
        br = p.boundingRect(0, 0, w, h, Qt.AlignCenter, txt)
        p.drawText(br, Qt.AlignCenter, txt)
        p.end()
        return QIcon(pm)

    # ----- Qt model API -----
    def rowCount(self, parent=None):
        return len(self._rows)

    def columnCount(self, parent=None):
        return 6

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            headers = ["Thumbnail", "Name", "Status", "Category", "Vendor", "Sim"]
            return headers[section] if 0 <= section < len(headers) else ""
        else:
            return ""

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        base_flags = super().flags(index) | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == 2:
            row = self._rows[index.row()]
            if row.status != STATUS_SYSTEMDISABLED:
                return base_flags | Qt.ItemIsUserCheckable
            else:
                return base_flags
        return base_flags

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.TextAlignmentRole and col == 0:
            return Qt.AlignHCenter | Qt.AlignVCenter

        if role == Qt.ToolTipRole and col == 0 and self._thumb_cache:
            name = row.name
            orig, _ = self._thumb_cache.get_paths_if_known(name)
            status = getattr(self._thumb_cache, "get_scan_status", lambda n: "unknown")(name)
            if orig:
                return f"Original: {orig}"
            if status == "missing":
                return "No thumbnail found (already scanned)."
            return "Thumbnail not cached yet.\n(Will appear once discovered.)"

        if col == 0 and role in (Qt.DecorationRole, Qt.DisplayRole):
            name = row.name
            icn = self._thumb_pix.get(name)
            if icn:
                return icn
            if self._thumb_cache:
                # Prefer original mapped path
                orig, _ = self._thumb_cache.get_paths_if_known(name)
                if orig and orig.exists():
                    pm = QPixmap(str(orig)).scaled(
                        self.THUMB_WIDTH,
                        self.THUMB_HEIGHT,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    icn = QIcon(pm)
                    self._thumb_pix[name] = icn
                    return icn

                # If we've already scanned and found nothing → show "Not Found" and don't queue again
                status = getattr(self._thumb_cache, "get_scan_status", lambda n: "unknown")(name)
                if status == "missing":
                    self._thumb_pix[name] = self._not_found_icon
                    return self._not_found_icon

                # Kick off async discovery job once
                if name not in self._loading:
                    self._loading.add(name)
                    from thumbnails import ThumbJob  # ensure latest def
                    job = ThumbJob(
                        row.name, row.source, row.sim, self._thumb_cache, self._signals
                    )
                    self._pool.start(job)
            return self._placeholder

        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 1:
                return row.name
            if col == 2:
                return row.status
            if col == 3:
                return getattr(row, "category", "")
            if col == 4:
                return getattr(row, "vendor", "")
            if col == 5:
                return getattr(row, "sim", "")
            return None

        if role == Qt.CheckStateRole and col == 2:
            if row.status == STATUS_SYSTEMDISABLED:
                return None
            return Qt.Checked if row.status == STATUS_ACTIVATED else Qt.Unchecked

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        row = self._rows[index.row()]
        col = index.column()

        if col == 2 and role == Qt.CheckStateRole:
            if row.status == STATUS_SYSTEMDISABLED:
                return False
            new_status = (
                STATUS_ACTIVATED if value == Qt.Checked else STATUS_USERDISABLED
            )
            if new_status != row.status:
                row.status = new_status
                self.dataChanged.emit(index, index, [Qt.CheckStateRole, Qt.DisplayRole])
            return True

        return False

    def _on_thumb_ready(self, name: str):
        # When a background job completes: load original if found; else mark Not Found
        if self._thumb_cache:
            orig, _ = self._thumb_cache.get_paths_if_known(name)
            if orig and orig.exists():
                pm = QPixmap(str(orig)).scaled(
                    self.THUMB_WIDTH,
                    self.THUMB_HEIGHT,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self._thumb_pix[name] = QIcon(pm)
            else:
                status = getattr(self._thumb_cache, "get_scan_status", lambda n: "unknown")(name)
                if status == "missing":
                    self._thumb_pix[name] = self._not_found_icon
        self._loading.discard(name)
        for r, rrow in enumerate(self._rows):
            if getattr(rrow, "name", "") == name:
                idx = self.index(r, 0)
                self.dataChanged.emit(
                    idx, idx, [Qt.DecorationRole, Qt.DisplayRole, Qt.ToolTipRole]
                )

    # ----- public helpers -----
    def refresh_thumbnails_for_rows(self, rows: list[int]):
        """Forget cached mapping & icon for these rows and re-queue discovery."""
        from thumbnails import ThumbJob
        for r in rows:
            if r < 0 or r >= len(self._rows):
                continue
            row = self._rows[r]
            name = row.name
            # drop any in-memory icon so we redraw placeholder / Not Found
            self._thumb_pix.pop(name, None)
            # nuke mapping on disk and requeue a background scan
            if self._thumb_cache:
                try:
                    self._thumb_cache.forget(name)
                except Exception:
                    pass
                self._loading.add(name)
                job = ThumbJob(name, row.source, row.sim, self._thumb_cache, self._signals)
                self._pool.start(job)
            # trigger repaint of the cell now
            idx = self.index(r, 0)
            self.dataChanged.emit(idx, idx, [Qt.DecorationRole, Qt.DisplayRole, Qt.ToolTipRole])

    def get_rows(self):
        return self._rows

    def dirty_changes(self):
        changes = []
        for r in self._rows:
            orig = getattr(r, "original_status", r.status)
            if r.status != orig:
                changes.append(r)
        return changes

    def clear_dirty(self):
        for r in self._rows:
            r.original_status = r.status

from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QPixmap

STATUS_ACTIVATED = "Activated"
STATUS_USERDISABLED = "UserDisabled"
STATUS_SYSTEMDISABLED = "SystemDisabled"

@dataclass
class PackageRow:
    name: str
    status: str
    source: str
    sim: str
    category: str
    vendor: str
    raw_index: int
    thumbnail_path: Optional[Path] = None

    @property
    def readonly(self) -> bool:
        return self.status == STATUS_SYSTEMDISABLED

class PackageTableModel(QAbstractTableModel):
    # Thumbnail is column 0
    HEADERS = ["Thumbnail", "Name", "Status", "Category", "Vendor", "Sim"]
    THUMB_WIDTH = 160
    THUMB_HEIGHT = 100

    def __init__(self, rows: List[PackageRow]):
        super().__init__()
        self._rows = rows
        self._dirty_names = set()
        self._pixmap_cache = {}

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row = self._rows[index.row()]
        col = index.column()

        # Thumbnail column
        if col == 0 and role == Qt.DecorationRole:
            if not row.thumbnail_path:
                return None
            
            # Use a cache to avoid reloading pixmaps from disk constantly
            path_str = str(row.thumbnail_path)
            if path_str in self._pixmap_cache:
                return self._pixmap_cache[path_str]

            pixmap = QPixmap(path_str)
            if pixmap.isNull():
                return None
            
            scaled_pixmap = pixmap.scaled(self.THUMB_WIDTH, self.THUMB_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._pixmap_cache[path_str] = scaled_pixmap
            return scaled_pixmap

        # Text columns (indices shifted by 1)
        if role == Qt.DisplayRole:
            if col == 1: return row.name
            if col == 2: return row.status
            if col == 3: return row.category
            if col == 4: return row.vendor
            if col == 5: return row.sim.upper()
        
        # Checkbox and tooltip for Status column (now col 2)
        if col == 2:
            if role == Qt.CheckStateRole:
                if row.status == STATUS_SYSTEMDISABLED:
                    return None
                return Qt.Checked if row.status == STATUS_ACTIVATED else Qt.Unchecked
            if role == Qt.ToolTipRole and row.readonly:
                return "SystemDisabled (managed by the sim)"

        # Text color for readonly rows
        if role == Qt.ForegroundRole and row.readonly:
            return QColor("gray")

        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled
        base = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        # Make status column checkable (now col 2)
        if index.column() == 2:
            row = self._rows[index.row()]
            if not row.readonly:
                base |= Qt.ItemIsUserCheckable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        row = self._rows[index.row()]
        # Handle checkbox changes in status column (now col 2)
        if index.column() == 2 and role == Qt.CheckStateRole and not row.readonly:
            new_status = STATUS_ACTIVATED if value == Qt.Checked else STATUS_USERDISABLED
            if new_status != row.status:
                row.status = new_status
                self._dirty_names.add(row.name)
                self.dataChanged.emit(index, index)
            return True
        return False

    def get_rows(self) -> List[PackageRow]:
        return self._rows

    def dirty_changes(self) -> List[PackageRow]:
        dirty = [r for r in self._rows if r.name in self._dirty_names]
        dirty.sort(key=lambda x: x.raw_index)
        return dirty

    def clear_dirty(self):
        self._dirty_names.clear()

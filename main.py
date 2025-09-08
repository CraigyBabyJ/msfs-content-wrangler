import sys
from pathlib import Path
import json

from PySide6.QtGui import QGuiApplication, QAction, QPalette, QColor, QIcon, QPixmap
from PySide6.QtCore import (
    Qt,
    QSortFilterProxyModel,
    QRegularExpression,
    QSettings,
    QTimer,
    QSize,
    QObject,
    QEvent,
    QItemSelectionModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QTableView,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QTabWidget,
    QToolBar,
    QStatusBar,
    QHeaderView,
    QInputDialog,
    QAbstractItemView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QMenu,  # <<< added
    QSplashScreen,
)

from models import (
    PackageTableModel,
    STATUS_ACTIVATED,
    STATUS_USERDISABLED,
    STATUS_SYSTEMDISABLED,
)
from content_io import (
    load_packages,
    backup_content,
    save_packages,
    list_content_xml_candidates,
    best_content_xml,
)
from categorizer import load_rules, save_rules
from settings import SettingsDialog, AppSettings
from thumbnails import ThumbCache

# If you have FooterBar in your project, keep this import. Otherwise, remove it.
from footer import FooterBar  # noqa: F401

CATEGORIES_ALL = [
    "All",
    "Airport",
    "Aircraft",
    "Livery",
    "Scenery",
    "Library",
    "Missions",
    "Utilities",
    "Other",
]
STATUS_ALL = ["All", STATUS_ACTIVATED, STATUS_USERDISABLED, STATUS_SYSTEMDISABLED]

STATUS_COL = 2  # column index for Status
VENDOR_COL = 4
SIM_COL = 5
STATUS_COL_WIDTH = 120  # keep Status column stable


# ---------- UI helpers ----------


class ElidedLabel(QLabel):
    def __init__(self, mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self._full = ""
        self._mode = mode

    def setFullText(self, text: str):
        self._full = text or ""
        self.setToolTip(self._full)
        self._update()

    def resizeEvent(self, e):
        self._update()
        super().resizeEvent(e)

    def _update(self):
        fm = self.fontMetrics()
        self.setText(fm.elidedText(self._full, self._mode, self.width()))


# ---------- Filtering proxy (with stronger FS20 community guard) ----------


class FilterProxy(QSortFilterProxyModel):
    """
    Per-tab proxy that enforces (source, sim) and applies search/category/status.
    Hard-excludes *any* FS2020 community packages.
    """

    def __init__(self, source_name: str, sim_tag: str):
        super().__init__()
        self.source_name = source_name
        self.sim_tag = sim_tag
        self.search_re = QRegularExpression("")
        self.category = "All"
        self.status = "All"
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        src = self.sourceModel()
        if not src:
            return Qt.NoItemFlags
        return src.flags(self.mapToSource(index))

    def set_search(self, text: str):
        self.search_re = QRegularExpression(
            text or "", QRegularExpression.CaseInsensitiveOption
        )
        self.invalidateFilter()

    def set_category(self, cat: str):
        self.category = cat or "All"
        self.invalidateFilter()

    def set_status(self, status: str):
        self.status = status or "All"
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        m = self.sourceModel()
        if not m:
            return True

        # column indices: 0 thumb, 1 name, 2 status, 3 category, 4 vendor, 5 sim
        idx_name = m.index(source_row, 1, source_parent)
        idx_status = m.index(source_row, STATUS_COL, source_parent)
        idx_category = m.index(source_row, 3, source_parent)
        idx_sim = m.index(source_row, SIM_COL, source_parent)

        name = (m.data(idx_name, Qt.DisplayRole) or "").strip()
        status = (m.data(idx_status, Qt.DisplayRole) or "").strip()
        category = (m.data(idx_category, Qt.DisplayRole) or "").strip()
        sim = (m.data(idx_sim, Qt.DisplayRole) or "").strip().lower()

        row_obj = m._rows[source_row]
        name_lc = name.lower()

        # 🚫 Strong guard: hide FS2020 community everywhere
        if "communityfs20-" in name_lc:
            return False
        if row_obj.source == "community" and row_obj.sim == "fs20":
            return False

        # Tab binding
        if row_obj.source != self.source_name:
            return False
        if row_obj.sim != self.sim_tag:
            return False

        # Dropdowns
        if self.category != "All" and category != self.category:
            return False
        if self.status != "All" and status != self.status:
            return False

        # Search (name or vendor, regex ok)
        pat = self.search_re.pattern()
        if pat:
            if not (
                self.search_re.match(name).hasMatch()
                or self.search_re.match(getattr(row_obj, "vendor", "") or "").hasMatch()
            ):
                return False

        return True


# ---------- Mouse event filters ----------


class StatusToggleFilter(QObject):
    """
    Intercepts mouse clicks on the table viewport.
    If the click hits the Status column, we toggle the checkbox ourselves.
    Works on both green (Activated) and red (UserDisabled) boxes + text.
    """

    def __init__(
        self, table: QTableView, proxy: FilterProxy, model: PackageTableModel, update_cb
    ):
        super().__init__(table)
        self.table = table
        self.proxy = proxy
        self.model = model
        self.update_cb = update_cb

    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QEvent.MouseButtonPress:
            idx = self.table.indexAt(event.position().toPoint())
            if idx.isValid() and idx.column() == STATUS_COL:
                mods = event.modifiers()
                # Let Qt handle range/discontiguous selection when modifiers are held
                if mods & (Qt.ShiftModifier | Qt.ControlModifier | Qt.MetaModifier):
                    return False  # do not consume

                # Plain click → toggle (except SystemDisabled)
                self.table.setCurrentIndex(idx)
                sidx = self.proxy.mapToSource(idx)
                row = self.model._rows[sidx.row()]
                if row.status != STATUS_SYSTEMDISABLED:
                    current = self.model.data(
                        self.model.index(sidx.row(), STATUS_COL), Qt.CheckStateRole
                    )
                    new_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
                    self.model.setData(
                        self.model.index(sidx.row(), STATUS_COL),
                        new_state,
                        Qt.CheckStateRole,
                    )
                    if callable(self.update_cb):
                        self.update_cb()
                return True
        return super().eventFilter(obj, event)


class ThumbnailRefreshFilter(QObject):
    """
    Clicking the thumbnail cell (column 0) will forget & rescan the thumbnail mapping
    for that row. We don't consume the event so normal selection still works.
    """

    def __init__(
        self,
        table: QTableView,
        proxy: FilterProxy,
        model: PackageTableModel,
        notify_cb=None,
    ):
        super().__init__(table)
        self.table = table
        self.proxy = proxy
        self.model = model
        self.notify_cb = notify_cb

    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QEvent.MouseButtonPress:
            idx = self.table.indexAt(event.position().toPoint())
            if idx.isValid() and idx.column() == 0:
                sidx = self.proxy.mapToSource(idx)
                self.model.refresh_thumbnails_for_rows([sidx.row()])
                if callable(self.notify_cb):
                    self.notify_cb("Refreshing thumbnail…")
                # Don't consume: allow selection to proceed
                return False
        return super().eventFilter(obj, event)


# ---------- Delegate to style SystemDisabled rows ----------


class RowStylingDelegate(QStyledItemDelegate):
    def __init__(self, proxy: FilterProxy, model: PackageTableModel, parent=None):
        super().__init__(parent)
        self.proxy = proxy
        self.model = model
        self.bg = QColor(255, 99, 99, 60)  # light red, semi-transparent
        self.muted_fg = QColor(255, 220, 220)

    def paint(self, painter, option: QStyleOptionViewItem, index):
        # clone and strip the focus state so no dotted outline is drawn
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.State_HasFocus

        sidx = self.proxy.mapToSource(index)
        row = self.model._rows[sidx.row()]

        if row.status == STATUS_SYSTEMDISABLED:
            painter.save()

            # keep them visually unselected + grey
            opt.state &= ~QStyle.State_Selected
            painter.fillRect(opt.rect, self.bg)

            pal = QPalette(opt.palette)
            pal.setColor(QPalette.Text, self.muted_fg)
            opt.palette = pal

            super().paint(painter, opt, index)
            painter.restore()
        else:
            super().paint(painter, opt, index)


# ---------- Main window ----------


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_dir = Path(__file__).parent
        self.rules_path = self.app_dir / "rules.json"
        self.config_path = self.app_dir / "config.json"
        self.settings = AppSettings()
        self.rules = load_rules(self.rules_path)
        self.config = self.load_config()
        self.current_xml: Path | None = None
        self.model: PackageTableModel | None = None

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.apply_theme()
        self._select_initial_content_xml()
        self._build_toolbar()

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Optional footer (only if FooterBar exists in your project)
        try:
            links_cfg = self.config.get("links") or {
                "Discord": "https://discord.gg/ErQduaBqAg",
                "GitHub": "https://github.com/CraigyBabyJ/msfs-content-wrangler",
                "TikTok": "https://tiktok.com/@craigybabyj_new",
                "Website": "https://craigybabyj.itch.io/",
                "Donate": "https://paypal.me/CJames440?locale.x=en_GB&country.x=GB",
            }
            icons_dir = Path(__file__).parent / "icons"
            self.footer = FooterBar(
                "CraigyBabyJ ✈️ #flywithcraig", links_cfg, icons_dir, self.save_changes
            )
            main_layout.addWidget(self.footer)
        except Exception:
            pass

        self.setCentralWidget(main_widget)

        # window / status
        self.setMinimumSize(1000, 680)
        self.resize(1280, 840)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.path_label = ElidedLabel()
        self.statusBar().addPermanentWidget(self.path_label, 1)

        self._refresh_path_label()
        if self.current_xml:
            self.load_content_file(initial=True)

        self._restore_window_geometry()

    # ----- config/theme -----

    def load_config(self) -> dict:
        defaults = {
            "content_xml_path": "",
            "theme": "dark",
            "show_thumbnails": False,
            "clean_legacy_fs20": True,
        }
        if self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                defaults.update(loaded_config)
        return defaults

    def save_config(self):
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def apply_theme(self):
        theme = self.config.get("theme", "dark")
        qss_file = "light_theme.qss" if theme == "light" else "resources.qss"
        qss_path = self.app_dir / qss_file
        if qss_path.exists():
            with qss_path.open("r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    # ----- content.xml selection -----

    def _select_initial_content_xml(self):
        last = self.settings.get_last_content_xml()
        if last and Path(last).exists():
            self.current_xml = Path(last)
        else:
            p = best_content_xml()
            if p:
                self.current_xml = p
                self.settings.set_last_content_xml(str(p))
        if not self.current_xml:
            QMessageBox.information(
                self,
                "Content.xml not found",
                "No Content.xml detected under LocalCache.\nOpen one manually from File → Open…",
            )

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        btn_switch = QAction("Switch Content.xml…", self)
        btn_switch.triggered.connect(self._switch_content_xml)
        tb.addAction(btn_switch)
        tb.addSeparator()

        btn_change = QAction("Open…", self)
        btn_change.triggered.connect(self.choose_file)
        tb.addAction(btn_change)
        tb.addSeparator()

        act_reload = QAction("Reload", self)
        act_reload.triggered.connect(lambda: self.load_content_file(initial=False))
        tb.addAction(act_reload)
        tb.addSeparator()

        act_settings = QAction("Settings…", self)
        act_settings.triggered.connect(self.open_settings)
        tb.addAction(act_settings)

    def _switch_content_xml(self):
        cands = list_content_xml_candidates()
        if not cands:
            QMessageBox.information(self, "No files", "No Content.xml files found.")
            return
        labels = [f"{c.name} — {c.path}" for c in cands]
        sel, ok = QInputDialog.getItem(
            self, "Choose Content.xml", "Detected profiles:", labels, 0, False
        )
        if ok and sel:
            idx = labels.index(sel)
            self.current_xml = cands[idx].path
            self.settings.set_last_content_xml(str(self.current_xml))
            self.load_content_file(initial=False)
            self._refresh_path_label()
            if any(c.is_profile for c in cands) and not getattr(
                cands[idx], "is_profile", False
            ):
                self.statusBar().showMessage(
                    "Heads up: a profile-scoped Content.xml also exists; the sim usually prefers that one.",
                    8000,
                )

    def _refresh_path_label(self):
        if self.current_xml:
            self.setWindowTitle(f"MSFS2024 Content Wrangler — {self.current_xml}")
            if hasattr(self, "path_label"):
                self.path_label.setFullText(str(self.current_xml))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Content.xml", str(Path.home()), "XML Files (*.xml)"
        )
        if path:
            self.current_xml = Path(path)
            self.settings.set_last_content_xml(str(self.current_xml))
            self.load_content_file(initial=False)
            self._refresh_path_label()

    # ----- load & tabs -----

    def load_content_file(self, initial=False):
        if not self.current_xml or not self.current_xml.exists():
            QMessageBox.critical(
                self,
                "Error",
                f"Content.xml not found at:\n{self.current_xml}\nPlease select a valid file.",
            )
            return

        rows, self.rules = load_packages(self.current_xml, self.rules_path)
        self.thumb_cache = ThumbCache(self.current_xml)
        self.model = PackageTableModel(rows, thumb_cache=self.thumb_cache)
        self._refresh_path_label()
        self._build_tabs()

    def _build_tabs(self):
        self.tabs.clear()
        tabs_spec = [
            ("Official Store (FS2024)", "official", "fs24"),
            ("Community Folder (FS2024)", "community", "fs24"),
            None,  # separator
            ("Official Store (FS2020)", "official", "fs20"),
        ]
        for spec in tabs_spec:
            if spec is None:
                idx = self.tabs.addTab(QWidget(), " ")
                self.tabs.setTabEnabled(idx, False)
                continue
            title, source, sim = spec
            self.tabs.addTab(self._build_tab_page(title, source, sim), title)
        self.status.showMessage(f"Loaded {self.model.rowCount()} packages.", 5000)

    def _warm_visible_thumbnails(self, view: QTableView):
        model = view.model()  # FilterProxy
        if not model:
            return
        source_model = model.sourceModel()
        if not source_model or not hasattr(source_model, "_thumb_cache"):
            return

        top = view.rowAt(0)
        bottom = view.rowAt(view.viewport().height())
        if top < 0:
            top = 0
        if bottom < 0:
            bottom = min(model.rowCount() - 1, 30)

        for r in range(top, bottom + 1):
            proxy_index = model.index(r, 0)
            source_index = model.mapToSource(proxy_index)
            _ = source_model.data(source_index, Qt.DecorationRole)

    def _build_tab_page(self, title: str, source: str, sim: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        # Controls
        ctrl = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Search name or vendor (regex ok)")
        cb_cat = QComboBox()
        cb_cat.addItems(CATEGORIES_ALL)
        cb_status = QComboBox()
        cb_status.addItems(STATUS_ALL)

        proxy = FilterProxy(source, sim)
        proxy.setSourceModel(self.model)

        def update_count(msg: str | None = None):
            if msg:
                self.status.showMessage(msg, 1200)
            else:
                self.status.showMessage(
                    f"{title}: showing {proxy.rowCount()} of {self.model.rowCount()} total",
                    3000,
                )

        search.textChanged.connect(lambda t: (proxy.set_search(t), update_count()))
        cb_cat.currentTextChanged.connect(
            lambda t: (proxy.set_category(t), update_count())
        )
        cb_status.currentTextChanged.connect(
            lambda t: (proxy.set_status(t), update_count())
        )

        ctrl.addWidget(QLabel("Search:"))
        ctrl.addWidget(search, 2)
        ctrl.addWidget(QLabel("Category:"))
        ctrl.addWidget(cb_cat, 1)
        ctrl.addWidget(QLabel("Status:"))
        ctrl.addWidget(cb_status, 1)

        btn_act = QPushButton("Activate Selected")
        btn_dis = QPushButton("Disable Selected")
        ctrl.addWidget(btn_act)
        ctrl.addWidget(btn_dis)

        v.addLayout(ctrl)

        # Table
        table = QTableView()
        table.setModel(proxy)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setSelectionMode(QTableView.ExtendedSelection)

        # We toggle via event filter (avoids double-toggle).
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        show_thumbnails = self.config.get("show_thumbnails", False)
        table.setColumnHidden(0, not show_thumbnails)
        if show_thumbnails:
            table.setIconSize(QSize(self.model.THUMB_WIDTH, self.model.THUMB_HEIGHT))
            table.verticalHeader().setDefaultSectionSize(self.model.THUMB_HEIGHT + 6)
            table.setStyleSheet(
                "QTableView::icon { margin-left: 6px; }\n"
                "QTableView::item:focus { border: none; }"
            )
        else:
            table.verticalHeader().setDefaultSectionSize(24)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Thumbnail column (fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(STATUS_COL, QHeaderView.Fixed)  # fixed status width
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Category
        header.setSectionResizeMode(VENDOR_COL, QHeaderView.Interactive)  # Vendor
        header.setSectionResizeMode(SIM_COL, QHeaderView.ResizeToContents)

        # Make the thumbnail column wide enough for the preview (kept wide)
        if show_thumbnails:
            thumb_w = getattr(self.model, "THUMB_WIDTH", 160)
            table.setColumnWidth(0, thumb_w + 40)  # 200px by default (no clip)
        else:
            table.setColumnWidth(0, 24)  # tiny when hidden

        table.setColumnWidth(VENDOR_COL, 150)
        table.setColumnWidth(STATUS_COL, STATUS_COL_WIDTH)

        v.addWidget(table)

        # Warm thumbs for visible rows
        QTimer.singleShot(0, lambda: self._warm_visible_thumbnails(table))

        # Install the event filters
        filter_obj = StatusToggleFilter(
            table, proxy, self.model, lambda: update_count()
        )
        table.viewport().installEventFilter(filter_obj)
        table._status_toggle_filter = filter_obj  # keep reference

        thumb_filter = ThumbnailRefreshFilter(
            table, proxy, self.model, notify_cb=update_count
        )
        table.viewport().installEventFilter(thumb_filter)
        table._thumb_refresh_filter = thumb_filter  # keep reference

        # Delegate: keep SystemDisabled rows visually grey at all times
        table.setItemDelegate(RowStylingDelegate(proxy, self.model, table))

        # --- Keep SystemDisabled rows unselected so they stay grey in multi-selects ---
        sel_model = table.selectionModel()

        def _prune_disabled_selection(selected, deselected):
            # avoid recursive calls
            if getattr(table, "_pruning_disabled_sel", False):
                return
            table._pruning_disabled_sel = True
            try:
                for idx in sel_model.selectedRows():
                    sidx = proxy.mapToSource(idx)
                    row = self.model._rows[sidx.row()]
                    if row.status == STATUS_SYSTEMDISABLED:
                        sel_model.select(
                            idx, QItemSelectionModel.Deselect | QItemSelectionModel.Rows
                        )
            finally:
                table._pruning_disabled_sel = False

        sel_model.selectionChanged.connect(_prune_disabled_selection)
        # ------------------------------------------------------------------------------

        # Context menu: refresh thumbnails for selected rows
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table, p=proxy, ttl=title: self._on_table_menu(pos, t, p, ttl)
        )

        # Bulk actions
        def bulk_set(status_value: str):
            sel = table.selectionModel().selectedRows()
            if not sel:
                QMessageBox.information(
                    self, "No Selection", "Select one or more rows first."
                )
                return
            changed = 0
            for idx in sel:
                sidx = proxy.mapToSource(idx)
                row = self.model._rows[sidx.row()]
                if row.status == STATUS_SYSTEMDISABLED:
                    continue
                if status_value == STATUS_ACTIVATED:
                    self.model.setData(
                        self.model.index(sidx.row(), STATUS_COL),
                        Qt.Checked,
                        role=Qt.CheckStateRole,
                    )
                else:
                    self.model.setData(
                        self.model.index(sidx.row(), STATUS_COL),
                        Qt.Unchecked,
                        role=Qt.CheckStateRole,
                    )
                changed += 1
            if changed:
                self.status.showMessage(f"{title}: updated {changed} entrie(s).", 4000)
                update_count()

        btn_act.clicked.connect(lambda: bulk_set(STATUS_ACTIVATED))
        btn_dis.clicked.connect(lambda: bulk_set(STATUS_USERDISABLED))

        return page

    # ----- context menu: refresh thumbnails -----
    def _on_table_menu(self, pos, table, proxy, title):
        menu = QMenu(table)
        act_refresh = QAction("Refresh thumbnail(s)", menu)
        act_refresh.triggered.connect(
            lambda: self._refresh_thumbs_selection(table, proxy, title)
        )
        menu.addAction(act_refresh)
        menu.exec(table.viewport().mapToGlobal(pos))

    def _refresh_thumbs_selection(self, table, proxy, title):
        sel_model = table.selectionModel()
        if not sel_model:
            return
        sel = sel_model.selectedRows()
        if not sel:
            self.status.showMessage("No rows selected.", 2000)
            return
        src_rows = [proxy.mapToSource(idx).row() for idx in sel]
        self.model.refresh_thumbnails_for_rows(src_rows)
        self.status.showMessage(
            f"{title}: refreshing {len(src_rows)} thumbnail(s)…", 2500
        )

    # ----- save / settings -----

    def save_changes(self):
        if not self.current_xml or not self.model:
            return
        diffs = self.model.dirty_changes()
        if not diffs:
            QMessageBox.information(self, "Nothing to save", "No changes detected.")
            return

        names_preview = "\n".join(f"{d.name}: → {d.status}" for d in diffs[:30])
        more = "" if len(diffs) <= 30 else f"\n… and {len(diffs)-30} more."
        if (
            QMessageBox.question(
                self,
                "Apply changes?",
                f"This will create a backup and update Content.xml.\n\nPreview of changes:\n{names_preview}{more}\n\nContinue?",
            )
            != QMessageBox.Yes
        ):
            return

        backup_path = backup_content(self.current_xml)
        removed_count = save_packages(
            self.current_xml,
            self.model.get_rows(),
            self.config.get("clean_legacy_fs20", True),
        )
        self.model.clear_dirty()

        QMessageBox.information(
            self,
            "Saved",
            f"Changes saved successfully.\nBackup created at: {backup_path}",
        )

        if removed_count > 0:
            QMessageBox.information(
                self,
                "Cleaned legacy FS20 mods",
                f"Removed {removed_count} legacy FS2020 community entries from Content.xml.\n"
                "You can disable this in Settings → Appearance.",
            )

    def _clear_thumb_cache(self):
        try:
            self.thumb_cache.clear_all()
        except Exception:
            pass
        try:
            self.model._thumb_pix.clear()
        except Exception:
            pass
        if self.model:
            self.model.layoutChanged.emit()
        self.status.showMessage("Thumbnail cache cleared.", 3000)

    def open_settings(self):
        dlg = SettingsDialog(
            self.rules,
            self.config,
            self.current_xml.as_posix() if self.current_xml else "",
            self,
        )
        # Connect the "clear thumbnail cache" action
        try:
            dlg.request_clear_thumb_cache.connect(self._clear_thumb_cache)
        except Exception:
            pass

        if dlg.exec():
            new_rules = dlg.get_updated_rules()
            new_config = dlg.get_updated_config()

            rules_changed = new_rules != self.rules
            config_changed = new_config != self.config

            if rules_changed:
                self.rules = new_rules
                save_rules(self.rules_path, self.rules)

            if config_changed:
                self.config = new_config
                self.save_config()
                self.apply_theme()

            if rules_changed or config_changed:
                self.status.showMessage("Settings updated. Reloading...", 3000)
                self.load_content_file(initial=True)

    # ----- window state -----

    def _restore_window_geometry(self):
        s = QSettings("CraigyBabyJ", "MSFS-Content-Wrangler")
        geo = s.value("window/geometry")
        state = s.value("window/state")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1280, 840)
        if state:
            self.restoreState(state)

    def closeEvent(self, e):
        if self.model and hasattr(self.model, "shutdown"):
            self.model.shutdown()
        s = QSettings("CraigyBabyJ", "MSFS-Content-Wrangler")
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())
        super().closeEvent(e)


# ---------- entry ----------

if __name__ == "__main__":
    # Windows: give the app its own ID so the taskbar uses our icon + groups correctly
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "CraigyBabyJ.MSFSContentWrangler"  # any stable, unique string
            )
        except Exception:
            pass

    # crisp HiDPI scaling
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    # App/window icon
    app_dir = Path(__file__).parent
    ico = app_dir / "icons" / "app.ico"
    png = app_dir / "icons" / "app.png"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    elif png.exists():
        app.setWindowIcon(QIcon(str(png)))

    # Splash screen
    splash = None
    if png.exists():
        splash_pix = QPixmap(str(png)).scaled(
            256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
        splash.setMask(splash_pix.mask())

        font = splash.font()
        font.setPointSize(14)
        splash.setFont(font)

        splash.show()
        splash.showMessage(
            "Loading, please wait...",
            Qt.AlignBottom | Qt.AlignCenter,
            QColor(230, 230, 230),
        )
        app.processEvents()

    win = MainWindow()
    try:
        if ico.exists():
            win.setWindowIcon(QIcon(str(ico)))
        elif png.exists():
            win.setWindowIcon(QIcon(str(png)))
    except Exception:
        pass

    win.show()
    if splash:
        splash.finish(win)
    sys.exit(app.exec())

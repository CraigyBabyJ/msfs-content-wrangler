import sys
import json
from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression
from PySide6.QtGui import QAction
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
)

from models import (
    PackageTableModel,
    STATUS_ACTIVATED,
    STATUS_USERDISABLED,
    STATUS_SYSTEMDISABLED,
)
from content_io import (
    find_content_xml,  # ok if unused
    load_packages,
    backup_content,
    save_packages,
    list_content_xml_candidates,
    best_content_xml,
)
from categorizer import load_rules, save_rules
from settings import SettingsDialog, AppSettings

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


class FilterProxy(QSortFilterProxyModel):
    def __init__(self, source_name: str, sim_tag: str):
        super().__init__()
        self.source_name = source_name
        self.sim_tag = sim_tag
        self.search_re = QRegularExpression("")
        self.category = "All"
        self.status = "All"
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_search(self, text: str):
        self.search_re = QRegularExpression(
            text, QRegularExpression.CaseInsensitiveOption
        )
        self.invalidateFilter()

    def set_category(self, cat: str):
        self.category = cat
        self.invalidateFilter()

    def set_status(self, status: str):
        self.status = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        m = self.sourceModel()
        idx_name = m.index(source_row, 1, source_parent)
        idx_status = m.index(source_row, 2, source_parent)
        idx_category = m.index(source_row, 3, source_parent)
        idx_vendor = m.index(source_row, 4, source_parent)
        idx_sim = m.index(source_row, 5, source_parent)

        name = m.data(idx_name, Qt.DisplayRole) or ""
        status = m.data(idx_status, Qt.DisplayRole) or ""
        category = m.data(idx_category, Qt.DisplayRole) or ""
        sim = (m.data(idx_sim, Qt.DisplayRole) or "").lower()
        row_obj = m._rows[source_row]

        if row_obj.source != self.source_name:
            return False
        if row_obj.sim != self.sim_tag:
            return False
        if self.category != "All" and category != self.category:
            return False
        if self.status != "All" and status != self.status:
            return False
        if self.search_re.pattern() and not (
            self.search_re.match(name).hasMatch()
            or self.search_re.match(row_obj.vendor).hasMatch()
        ):
            return False
        return True


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

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(10, 10, 10, 10)
        save_button = QPushButton("Save Changes")
        save_button.setObjectName("saveButton")
        save_button.clicked.connect(self.save_changes)
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(save_button)
        main_layout.addLayout(bottom_bar)

        self.setCentralWidget(main_widget)
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._refresh_path_label()
        if self.current_xml:
            self.load_content_file(initial=True)

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
        tb.setMovable(False)
        self.addToolBar(tb)

        self.lbl_path = QLabel("Content.xml: (none)")
        tb.addWidget(self.lbl_path)

        btn_switch = QAction("Switch Content.xml…", self)
        btn_switch.triggered.connect(self._switch_content_xml)
        tb.addAction(btn_switch)

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
            return  # <-- fixed indentation
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
        if hasattr(self, "lbl_path") and self.current_xml:
            self.lbl_path.setText(str(self.current_xml))
        if self.current_xml:
            self.setWindowTitle(f"MSFS Content Wrangler — {self.current_xml}")

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Content.xml", str(Path.home()), "XML Files (*.xml)"
        )
        if path:
            self.current_xml = Path(path)
            self.settings.set_last_content_xml(str(self.current_xml))
            self.load_content_file(initial=False)
            self._refresh_path_label()

    def load_content_file(self, initial=False):
        if not self.current_xml or not self.current_xml.exists():
            QMessageBox.critical(
                self,
                "Error",
                f"Content.xml not found at:\n{self.current_xml}\nPlease select a valid file.",
            )
            return

        rows, self.rules = load_packages(self.current_xml, self.rules_path)
        self.model = PackageTableModel(rows)
        self._refresh_path_label()
        self._build_tabs()

    def _build_tabs(self):
        self.tabs.clear()
        tabs_spec = [
            ("Official (FS24)", "official", "fs24"),
            ("Community (FS24)", "community", "fs24"),
            None,  # visual separator
            ("Official (FS20)", "official", "fs20"),
        ]
        for spec in tabs_spec:
            if spec is None:
                idx = self.tabs.addTab(QWidget(), " ")
                self.tabs.setTabEnabled(idx, False)
                continue
            title, source, sim = spec
            self.tabs.addTab(self._build_tab_page(title, source, sim), title)
        self.status.showMessage(f"Loaded {self.model.rowCount()} packages.", 5000)

    def _build_tab_page(self, title: str, source: str, sim: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        ctrl = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Search name or vendor (regex ok)")
        cb_cat = QComboBox()
        cb_cat.addItems(CATEGORIES_ALL)
        cb_status = QComboBox()
        cb_status.addItems(STATUS_ALL)

        proxy = FilterProxy(source, sim)
        proxy.setSourceModel(self.model)

        def update_count():
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

        table = QTableView()
        table.setModel(proxy)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setSelectionMode(QTableView.ExtendedSelection)

        show_thumbnails = self.config.get("show_thumbnails", False)
        table.setColumnHidden(0, not show_thumbnails)
        if show_thumbnails:
            table.verticalHeader().setDefaultSectionSize(self.model.THUMB_HEIGHT)
            table.setColumnWidth(0, self.model.THUMB_WIDTH)
        else:
            table.verticalHeader().setDefaultSectionSize(24)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        table.setColumnWidth(4, 150)
        v.addWidget(table)

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
                        self.model.index(sidx.row(), 2),
                        Qt.Checked,
                        role=Qt.CheckStateRole,
                    )
                else:
                    self.model.setData(
                        self.model.index(sidx.row(), 2),
                        Qt.Unchecked,
                        role=Qt.CheckStateRole,
                    )
                changed += 1
            if changed:
                self.status.showMessage(f"{title}: updated {changed} entrie(s).", 4000)

        btn_act.clicked.connect(lambda: bulk_set(STATUS_ACTIVATED))
        btn_dis.clicked.connect(lambda: bulk_set(STATUS_USERDISABLED))

        return page

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

    def open_settings(self):
        dlg = SettingsDialog(
            self.rules,
            self.config,
            self.current_xml.as_posix() if self.current_xml else "",
            self,
        )
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

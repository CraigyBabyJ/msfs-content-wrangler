import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTableView, QWidget,
    QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QPushButton, QLabel, QTabWidget,
    QToolBar, QStatusBar, QDialog, QTextEdit
)

from models import PackageTableModel, STATUS_ACTIVATED, STATUS_USERDISABLED, STATUS_SYSTEMDISABLED
from content_io import find_content_xml, load_packages, backup_content, save_packages
from categorizer import load_rules, save_rules

CATEGORIES_ALL = ["All", "Airport", "Aircraft", "Livery", "Scenery", "Library", "Missions", "Utilities", "Other"]
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
        self.search_re = QRegularExpression(text, QRegularExpression.CaseInsensitiveOption)
        self.invalidateFilter()

    def set_category(self, cat: str):
        self.category = cat
        self.invalidateFilter()

    def set_status(self, status: str):
        self.status = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        m = self.sourceModel()
        idx_name = m.index(source_row, 0, source_parent)
        idx_status = m.index(source_row, 1, source_parent)
        idx_category = m.index(source_row, 2, source_parent)
        idx_vendor = m.index(source_row, 3, source_parent)
        idx_sim = m.index(source_row, 4, source_parent)

        name = m.data(idx_name, Qt.DisplayRole) or ""
        status = m.data(idx_status, Qt.DisplayRole) or ""
        category = m.data(idx_category, Qt.DisplayRole) or ""
        sim = (m.data(idx_sim, Qt.DisplayRole) or "").lower()
        # Source check via vendor column? Not stored there. We'll inspect model's internal rows:
        row_obj = m._rows[source_row]
        if row_obj.source != self.source_name:
            return False
        if row_obj.sim != self.sim_tag:
            return False

        if self.category != "All" and category != self.category:
            return False
        if self.status != "All" and status != self.status:
            return False
        if self.search_re.pattern() and not (self.search_re.match(name).hasMatch() or self.search_re.match(row_obj.vendor).hasMatch()):
            return False
        return True

class DiffDialog(QDialog):
    def __init__(self, diffs):
        super().__init__()
        self.setWindowTitle("Dry-Run: Pending Changes")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        text = QTextEdit(self)
        text.setReadOnly(True)
        if diffs:
            lines = [f"{d.name}: → {d.status}" for d in diffs]
            text.setPlainText("\n".join(lines))
        else:
            text.setPlainText("No changes.")
        layout.addWidget(text)
        btns = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(close)
        layout.addLayout(btns)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSFS Content Wrangler")
        self.resize(1100, 700)
        self.app_dir = Path(__file__).parent
        self.rules_path = self.app_dir / "rules.json"
        self.rules = load_rules(self.rules_path)
        self.current_xml: Path | None = None
        self.model: PackageTableModel | None = None

        # Global UI
        self._load_styles()
        self._build_toolbar()
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Load initial file
        self.load_content_file(initial=True)

    def _load_styles(self):
        qss = (self.app_dir / "resources.qss")
        if qss.exists():
            with qss.open("r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.lbl_path = QLabel("Content.xml: (none)")
        tb.addWidget(self.lbl_path)

        btn_change = QAction("Change…", self)
        btn_change.triggered.connect(self.choose_file)
        tb.addAction(btn_change)

        tb.addSeparator()

        act_reload = QAction("Reload", self)
        act_reload.triggered.connect(lambda: self.load_content_file(initial=False))
        tb.addAction(act_reload)

        act_dry = QAction("Dry-Run", self)
        act_dry.triggered.connect(self.dry_run)
        tb.addAction(act_dry)

        act_backup = QAction("Backup", self)
        act_backup.triggered.connect(self.do_backup_only)
        tb.addAction(act_backup)

        act_save = QAction("Save", self)
        act_save.triggered.connect(self.save_changes)
        tb.addAction(act_save)

        tb.addSeparator()

        act_edit_rules = QAction("Settings: Edit Rules…", self)
        act_edit_rules.triggered.connect(self.edit_rules)
        tb.addAction(act_edit_rules)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Content.xml", str(Path.home()), "XML Files (*.xml)")
        if path:
            self.current_xml = Path(path)
            self.load_content_file(initial=False)

    def load_content_file(self, initial=False):
        if initial:
            self.current_xml = find_content_xml()
            if not self.current_xml:
                QMessageBox.information(self, "Select Content.xml", "Couldn't auto-locate Content.xml. Please choose it.")
                self.choose_file()
                if not self.current_xml:
                    return
        rows, self.rules = load_packages(self.current_xml, self.rules_path)
        self.model = PackageTableModel(rows)
        self.lbl_path.setText(f"Content.xml: {self.current_xml}")
        self._build_tabs()

    def _build_tabs(self):
        self.tabs.clear()
        # Create four tabs with filtered proxies
        tabs_spec = [
            ("Community (FS24)", "community", "fs24"),
            ("Community (FS20)", "community", "fs20"),
            ("Official (FS24)", "official", "fs24"),
            ("Official (FS20)", "official", "fs20"),
        ]
        for title, source, sim in tabs_spec:
            self.tabs.addTab(self._build_tab_page(title, source, sim), title)
        self.status.showMessage(f"Loaded {self.model.rowCount()} packages.", 5000)

    def _build_tab_page(self, title: str, source: str, sim: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        # Controls: search, category, status filters, buttons
        ctrl = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Search name or vendor (regex ok)")
        cb_cat = QComboBox(); cb_cat.addItems(CATEGORIES_ALL)
        cb_status = QComboBox(); cb_status.addItems(STATUS_ALL)

        proxy = FilterProxy(source, sim)
        proxy.setSourceModel(self.model)

        def update_count():
            self.status.showMessage(f"{title}: showing {proxy.rowCount()} of {self.model.rowCount()} total", 3000)

        search.textChanged.connect(lambda t: (proxy.set_search(t), update_count()))
        cb_cat.currentTextChanged.connect(lambda t: (proxy.set_category(t), update_count()))
        cb_status.currentTextChanged.connect(lambda t: (proxy.set_status(t), update_count()))

        ctrl.addWidget(QLabel("Search:"))
        ctrl.addWidget(search, 2)
        ctrl.addWidget(QLabel("Category:"))
        ctrl.addWidget(cb_cat, 1)
        ctrl.addWidget(QLabel("Status:"))
        ctrl.addWidget(cb_status, 1)

        # Bulk buttons
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
        table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(table)

        def bulk_set(status_value: str):
            sel = table.selectionModel().selectedRows()
            if not sel:
                QMessageBox.information(self, "No Selection", "Select one or more rows first.")
                return
            changed = 0
            for idx in sel:
                sidx = proxy.mapToSource(idx)
                # toggle via CheckState where possible
                row = self.model._rows[sidx.row()]
                if row.status == STATUS_SYSTEMDISABLED:
                    continue
                if status_value == STATUS_ACTIVATED:
                    self.model.setData(self.model.index(sidx.row(), 1), Qt.Checked, role=Qt.CheckStateRole)
                else:
                    self.model.setData(self.model.index(sidx.row(), 1), Qt.Unchecked, role=Qt.CheckStateRole)
                changed += 1
            if changed:
                self.status.showMessage(f"{title}: updated {changed} entrie(s).", 4000)

        btn_act.clicked.connect(lambda: bulk_set(STATUS_ACTIVATED))
        btn_dis.clicked.connect(lambda: bulk_set(STATUS_USERDISABLED))

        return page

    def dry_run(self):
        if not self.model:
            return
        diffs = self.model.dirty_changes()
        dlg = DiffDialog(diffs)
        dlg.exec()

    def do_backup_only(self):
        if not self.current_xml:
            return
        dst = backup_content(self.current_xml)
        QMessageBox.information(self, "Backup created", f"Saved backup:\n{dst}")

    def save_changes(self):
        if not self.current_xml or not self.model:
            return
        diffs = self.model.dirty_changes()
        if not diffs:
            QMessageBox.information(self, "Nothing to save", "No changes detected.")
            return
        # Confirm
        names_preview = "\n".join(f"{d.name}: → {d.status}" for d in diffs[:30])
        more = "" if len(diffs) <= 30 else f"\n… and {len(diffs)-30} more."
        if QMessageBox.question(self, "Apply changes?",
                                f"This will backup and then update Content.xml.\n\nPreview:\n{names_preview}{more}\n\nContinue?") != QMessageBox.Yes:
            return
        # Backup and save
        backup_content(self.current_xml)
        save_packages(self.current_xml, self.model.get_rows())
        self.model.clear_dirty()
        QMessageBox.information(self, "Saved", "Changes saved successfully.")

    def edit_rules(self):
        # Simple inline editor for rules.json
        path = str(self.rules_path)
        mb = QMessageBox(self)
        mb.setWindowTitle("Edit Rules")
        mb.setText(f"Open rules.json in your editor?\n\n{path}")
        mb.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if mb.exec() == QMessageBox.Yes:
            # Try to open in default editor
            import subprocess, os
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore
            else:
                subprocess.Popen(["xdg-open", path])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

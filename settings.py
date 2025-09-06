import copy
from pathlib import Path
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QDialogButtonBox,
    QListWidget,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QListWidgetItem,
    QAbstractItemView,
    QTabWidget,
    QWidget,
    QFormLayout,
    QFileDialog,
    QGroupBox,
    QRadioButton,
    QCheckBox,
)


class AppSettings:
    def __init__(self):
        self.s = QSettings("CraigyBabyJ", "MSFS-Content-Wrangler")

    def get_last_content_xml(self) -> str | None:
        return self.s.value("paths/last_content_xml", None, type=str)

    def set_last_content_xml(self, p: str):
        self.s.setValue("paths/last_content_xml", p)


class SettingsDialog(QDialog):
    def __init__(
        self, rules: dict, config: dict, current_xml_path_str: str, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(800, 500)

        self.rules_copy = copy.deepcopy(rules)
        self.config_copy = copy.deepcopy(config)
        self.current_xml_path_str = current_xml_path_str
        self.app_settings = AppSettings()

        top_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        top_layout.addWidget(self.tabs)

        self.build_rules_tab()
        self.build_paths_tab()
        self.build_appearance_tab()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        top_layout.addWidget(button_box)

        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

    def build_rules_tab(self):
        page = QWidget()
        main_layout = QHBoxLayout(page)

        cat_layout = QVBoxLayout()
        cat_layout.addWidget(QLabel("Categories (drag to reorder)"))
        self.cat_list = QListWidget()
        self.cat_list.setDragDropMode(QAbstractItemView.InternalMove)
        cat_layout.addWidget(self.cat_list)

        cat_btn_layout = QHBoxLayout()
        btn_add_cat = QPushButton("Add…")
        btn_rem_cat = QPushButton("Remove")
        cat_btn_layout.addWidget(btn_add_cat)
        cat_btn_layout.addWidget(btn_rem_cat)
        cat_layout.addLayout(cat_btn_layout)

        pat_layout = QVBoxLayout()
        self.pat_label = QLabel("Patterns")
        pat_layout.addWidget(self.pat_label)
        self.pat_list = QListWidget()
        pat_layout.addWidget(self.pat_list)

        pat_add_layout = QHBoxLayout()
        self.pat_input = QLineEdit()
        self.pat_input.setPlaceholderText("Enter new pattern")
        btn_add_pat = QPushButton("Add")
        pat_add_layout.addWidget(self.pat_input)
        pat_add_layout.addWidget(btn_add_pat)
        pat_layout.addLayout(pat_add_layout)

        btn_rem_pat = QPushButton("Remove Selected Pattern")
        pat_layout.addWidget(btn_rem_pat)

        main_layout.addLayout(cat_layout, 1)
        main_layout.addLayout(pat_layout, 2)

        self.cat_list.currentItemChanged.connect(self.on_category_selected)
        btn_add_cat.clicked.connect(self.add_category)
        btn_rem_cat.clicked.connect(self.remove_category)
        btn_add_pat.clicked.connect(self.add_pattern)
        self.pat_input.returnPressed.connect(self.add_pattern)
        btn_rem_pat.clicked.connect(self.remove_pattern)

        self.tabs.addTab(page, "Categorization Rules")
        self.populate_categories()

    def build_paths_tab(self):
        page = QWidget()
        layout = QFormLayout(page)
        path_layout = QHBoxLayout()
        self.content_path_input = QLineEdit()

        initial_path = self.config_copy.get("content_xml_path")
        if not initial_path:
            # Try session config, then persistent AppSettings, then current file, then blank
            initial_path = self.app_settings.get_last_content_xml()
        if not initial_path and self.current_xml_path_str:
            initial_path = self.current_xml_path_str
        self.content_path_input.setText(initial_path or "")

        btn_browse = QPushButton("Browse…")
        path_layout.addWidget(self.content_path_input)
        path_layout.addWidget(btn_browse)
        layout.addRow("Content.xml Path:", path_layout)
        btn_browse.clicked.connect(self.select_content_path)
        self.tabs.addTab(page, "Paths")

    def build_appearance_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        theme_group_box = QGroupBox("Theme")
        theme_group_layout = QVBoxLayout(theme_group_box)
        self.radio_dark = QRadioButton("Dark Theme")
        self.radio_light = QRadioButton("Light Theme")
        current_theme = self.config_copy.get("theme", "dark")
        if current_theme == "light":
            self.radio_light.setChecked(True)
        else:
            self.radio_dark.setChecked(True)
        theme_group_layout.addWidget(self.radio_dark)
        theme_group_layout.addWidget(self.radio_light)
        layout.addWidget(theme_group_box)

        display_group_box = QGroupBox("Display")
        display_group_layout = QVBoxLayout(display_group_box)
        self.check_show_thumbs = QCheckBox("Show package thumbnails in list")
        self.check_show_thumbs.setChecked(
            self.config_copy.get("show_thumbnails", False)
        )
        display_group_layout.addWidget(self.check_show_thumbs)

        self.check_clean_legacy = QCheckBox("Clean legacy FS20 mods")
        self.check_clean_legacy.setToolTip(
            "Automatically remove legacy FS2020 community mod references from Content.xml when saving."
        )
        self.check_clean_legacy.setChecked(
            self.config_copy.get("clean_legacy_fs20", True)
        )
        display_group_layout.addWidget(self.check_clean_legacy)

        layout.addWidget(display_group_box)

        layout.addStretch(1)
        self.tabs.addTab(page, "Appearance")

    def select_content_path(self):
        start_dir = str(Path(self.content_path_input.text()).parent or Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Content.xml", start_dir, "XML Files (*.xml)"
        )
        if path:
            self.content_path_input.setText(path)

    def find_category_by_name(self, name: str) -> dict | None:
        for cat in self.rules_copy.get("categories", []):
            if cat["name"] == name:
                return cat
        return None

    def populate_categories(self):
        self.cat_list.clear()
        for category in self.rules_copy.get("categories", []):
            self.cat_list.addItem(QListWidgetItem(category["name"]))
        if self.cat_list.count() > 0:
            self.cat_list.setCurrentRow(0)

    def on_category_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        self.pat_list.clear()
        if current is None:
            self.pat_label.setText("Patterns")
            return
        category = self.find_category_by_name(current.text())
        if category:
            self.pat_label.setText(f"Patterns for \"{category['name']}\")")
            self.pat_list.addItems(category.get("patterns", []))

    def add_category(self):
        text, ok = QInputDialog.getText(
            self, "Add Category", "Enter new category name:"
        )
        if ok and text:
            if self.find_category_by_name(text):
                QMessageBox.warning(self, "Duplicate", "Category already exists.")
                return
            self.rules_copy["categories"].append({"name": text, "patterns": []})
            self.cat_list.addItem(QListWidgetItem(text))
            self.cat_list.setCurrentRow(self.cat_list.count() - 1)

    def remove_category(self):
        current_item = self.cat_list.currentItem()
        if not current_item:
            return
        cat_name = current_item.text()
        category = self.find_category_by_name(cat_name)
        if not category:
            return
        if (
            QMessageBox.question(
                self,
                "Remove Category",
                f'Are you sure you want to remove the "{cat_name}" category?',
            )
            == QMessageBox.Yes
        ):
            self.rules_copy["categories"].remove(category)
            self.cat_list.takeItem(self.cat_list.row(current_item))

    def add_pattern(self):
        current_cat_item = self.cat_list.currentItem()
        if not current_cat_item:
            return
        pattern = self.pat_input.text().strip()
        if not pattern:
            return
        category = self.find_category_by_name(current_cat_item.text())
        if category and pattern not in category["patterns"]:
            category["patterns"].append(pattern)
            self.pat_list.addItem(pattern)
        self.pat_input.clear()

    def remove_pattern(self):
        current_cat_item = self.cat_list.currentItem()
        current_pat_item = self.pat_list.currentItem()
        if not current_cat_item or not current_pat_item:
            return
        category = self.find_category_by_name(current_cat_item.text())
        pattern = current_pat_item.text()
        if category and pattern in category["patterns"]:
            category["patterns"].remove(pattern)
            self.pat_list.takeItem(self.pat_list.row(current_pat_item))

    def on_accept(self):
        # Save rules order
        ui_order = [self.cat_list.item(i).text() for i in range(self.cat_list.count())]
        cat_map = {cat["name"]: cat for cat in self.rules_copy["categories"]}
        self.rules_copy["categories"] = [cat_map[name] for name in ui_order]

        # Save path config
        content_path = self.content_path_input.text()
        self.config_copy["content_xml_path"] = content_path
        self.app_settings.set_last_content_xml(content_path)

        # Save theme config
        self.config_copy["theme"] = "light" if self.radio_light.isChecked() else "dark"

        # Save display config
        self.config_copy["show_thumbnails"] = self.check_show_thumbs.isChecked()
        self.config_copy["clean_legacy_fs20"] = self.check_clean_legacy.isChecked()

        self.accept()

    def get_updated_rules(self) -> dict:
        return self.rules_copy

    def get_updated_config(self) -> dict:
        return self.config_copy

from dataclasses import dataclass
from typing import List, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

STATUS_ACTIVATED = "Activated"
STATUS_USERDISABLED = "UserDisabled"
STATUS_SYSTEMDISABLED = "SystemDisabled"

@dataclass
class PackageRow:
    name: str
    status: str  # Activated | UserDisabled | SystemDisabled
    source: str  # community | official
    sim: str     # fs20 | fs24
    category: str
    vendor: str
    raw_index: int

    @property
    def readonly(self) -> bool:
        return self.status == STATUS_SYSTEMDISABLED

class PackageTableModel(QAbstractTableModel):
    HEADERS = ["Name", "Status", "Category", "Vendor", "Sim"]

    def __init__(self, rows: List[PackageRow]):
        super().__init__()
        self._rows = rows
        self._dirty_names = set()

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

        if role == Qt.DisplayRole:
            if col == 0: return row.name
            if col == 1: return row.status
            if col == 2: return row.category
            if col == 3: return row.vendor
            if col == 4: return row.sim.upper()
        if role == Qt.CheckStateRole and col == 1:
            # Checked = Activated, Unchecked = UserDisabled; no checkbox for SystemDisabled
            if row.status == STATUS_SYSTEMDISABLED:
                return None
            return Qt.Checked if row.status == STATUS_ACTIVATED else Qt.Unchecked
        if role == Qt.ToolTipRole and col == 1 and row.readonly:
            return "SystemDisabled (managed by the sim)"
        if role == Qt.TextColorRole and row.readonly:
            return Qt.gray
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled
        base = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == 1:
            row = self._rows[index.row()]
            if not row.readonly:
                base |= Qt.ItemIsUserCheckable
        return base

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        row = self._rows[index.row()]
        if index.column() == 1 and role == Qt.CheckStateRole and not row.readonly:
            new_status = STATUS_ACTIVATED if value == Qt.Checked else STATUS_USERDISABLED
            if new_status != row.status:
                row.status = new_status
                self._dirty_names.add(row.name)
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.CheckStateRole])
            return True
        return False

    def get_rows(self) -> List[PackageRow]:
        return self._rows

    def dirty_changes(self) -> List[PackageRow]:
        dirty = [r for r in self._rows if r.name in self._dirty_names]
        # Keep original order
        dirty.sort(key=lambda x: x.raw_index)
        return dirty

    def clear_dirty(self):
        self._dirty_names.clear()

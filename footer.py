from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton
from PySide6.QtSvg import QSvgRenderer
from pathlib import Path

APP_DARK_LINK = "#9ec7ff"   # link color on dark bg
ICON_SIZE = 18               # px

def svg_icon(path: Path, color: str = APP_DARK_LINK, size: int = ICON_SIZE) -> QIcon:
    """
    Load an SVG and tint it to `color`. If not found or invalid, return null icon.
    """
    if not path.exists():
        return QIcon()
    data = path.read_bytes()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return QIcon()
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    # tint
    tint = QPixmap(pm.size())
    tint.fill(Qt.transparent)
    p = QPainter(tint)
    p.fillRect(tint.rect(), color)
    p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    p.drawPixmap(0, 0, pm)
    p.end()
    return QIcon(tint)

class LinkButton(QToolButton):
    def __init__(self, label: str, url: str, icon_path: Path | None):
        super().__init__()
        self._url = url
        self.setText(label)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        if icon_path:
            self.setIcon(svg_icon(icon_path))
            self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setAutoRaise(True)
        self.clicked.connect(self._open)

    def _open(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(self._url))

class FooterBar(QWidget):
    """
    Two-line footer:
    - Line 1: brand text (left)
    - Line 2: link buttons (left) + Save Changes (right)
    """
    def __init__(self, brand: str, links: dict[str, str] | None, icons_dir: Path, on_save):
        super().__init__()
        links = links or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        brand_lbl = QLabel(brand)
        brand_lbl.setObjectName("FooterBrand")
        root.addWidget(brand_lbl, alignment=Qt.AlignLeft)

        row = QHBoxLayout(); row.setSpacing(8)
        links_row = QHBoxLayout(); links_row.setSpacing(10)

        # map label -> (config key, icon filename)
        items = [
            ("Discord", "Discord", "discord.svg"),
            ("GitHub",  "GitHub",  "github.svg"),
            ("TikTok",  "TikTok",  "tiktok.svg"),
            ("Website", "Website", "globe.svg"),
            ("Donate",  "Donate",  "paypal.svg"),   # or "heart.svg"
        ]
        for label, key, iconfile in items:
            url = (links.get(key) or "").strip()
            if not url:
                continue
            icon_path = icons_dir / iconfile
            links_row.addWidget(LinkButton(label, url, icon_path))

        links_row.addStretch(1)
        row.addLayout(links_row, 1)

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("saveButton")  # inherits your green QSS
        save_btn.clicked.connect(on_save)
        row.addWidget(save_btn, 0, Qt.AlignRight)

        root.addLayout(row)

        self.setStyleSheet("""
        #FooterBrand { color: #e0e0e0; font-size: 18px; font-weight: bold; }
        QToolButton { color: #9ec7ff; } 
        QToolButton:hover { text-decoration: underline; }
        """)
"""系统托盘 - 最小化到托盘、托盘右键菜单"""

import sys
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont


def _create_tray_icon() -> QIcon:
    """生成一个简单的托盘图标（紫色圆角方块 + ✓）"""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 圆角方块
    painter.setBrush(QColor("#6366F1"))
    painter.setPen(QColor("#6366F1"))
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 12, 12)

    # ✓ 标记
    painter.setPen(QColor("#FFFFFF"))
    family = "Segoe UI" if sys.platform == "win32" else "Helvetica Neue"
    font = QFont(family, 28, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, "✓")  # AlignCenter

    painter.end()
    return QIcon(pixmap)


class SystemTray(QObject):
    """系统托盘管理器"""

    # 信号
    show_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    add_task_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_create_tray_icon())
        self._tray.setToolTip("桌面待办")

        self._setup_menu()
        self._tray.activated.connect(self._on_activated)

    def _setup_menu(self):
        menu = QMenu()

        show_action = menu.addAction("📋 显示窗口")
        show_action.triggered.connect(self.show_requested.emit)

        add_action = menu.addAction("＋ 新建任务")
        add_action.triggered.connect(self.add_task_requested.emit)

        settings_action = menu.addAction("⚙️ 设置")
        settings_action.triggered.connect(self.settings_requested.emit)

        menu.addSeparator()

        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        """双击托盘图标显示窗口"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()

    def is_visible(self):
        return self._tray.isVisible()

    def show_message(self, title: str, message: str, duration_ms: int = 3000):
        """显示托盘气泡通知"""
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        return self._tray

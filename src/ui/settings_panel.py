"""设置面板 - 主题切换、透明度调节、窗口置顶开关"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QComboBox, QCheckBox,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from src.ui.styles.themes import get_theme_keys, get_theme, THEMES


class SettingsPanel(QDialog):
    """设置面板弹窗"""

    # 信号
    theme_changed = pyqtSignal(str)           # theme_key
    opacity_changed = pyqtSignal(float)       # 0.3 ~ 1.0
    always_on_top_changed = pyqtSignal(bool)  # on/off
    font_size_changed = pyqtSignal(int)       # 10 ~ 24

    def __init__(self, current_theme_key: str, current_opacity: float,
                 current_always_on_top: bool, current_font_size: int = 13,
                 parent=None):
        super().__init__(parent)
        self._theme_key = current_theme_key
        self._opacity = current_opacity
        self._always_on_top = current_always_on_top
        self._font_size = current_font_size

        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle("设置")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(300)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        # 主容器
        self.container = QFrame()
        self.container.setObjectName("EditorContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        # --- 标题栏 ---
        header = QHBoxLayout()
        title = QLabel("设置")
        title.setObjectName("EditorTitle")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditorCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # --- 分隔线 ---
        layout.addWidget(self._separator())

        # --- 主题选择 ---
        theme_row = QHBoxLayout()
        theme_label = QLabel("主题")
        theme_label.setObjectName("SettingsLabel")
        theme_row.addWidget(theme_label)
        theme_row.addStretch()

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("SettingsCombo")
        self.theme_combo.setFixedWidth(140)
        self.theme_combo.setCursor(Qt.PointingHandCursor)

        # 填充主题选项
        keys = get_theme_keys()
        for key in keys:
            theme = get_theme(key)
            self.theme_combo.addItem(theme.name, key)

        # 设置当前选中
        idx = keys.index(self._theme_key) if self._theme_key in keys else 0
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        layout.addLayout(theme_row)

        # --- 透明度 ---
        opacity_header = QHBoxLayout()
        opacity_label = QLabel("背景透明度")
        opacity_label.setObjectName("SettingsLabel")
        opacity_header.addWidget(opacity_label)
        opacity_header.addStretch()

        self.opacity_value_label = QLabel(f"{int(self._opacity * 100)}%")
        self.opacity_value_label.setObjectName("SettingsValueLabel")
        opacity_header.addWidget(self.opacity_value_label)
        layout.addLayout(opacity_header)

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setObjectName("SettingsSlider")
        self.opacity_slider.setMinimum(30)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(self._opacity * 100))
        self.opacity_slider.setTickInterval(5)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_slider)

        # --- 字号 ---
        font_header = QHBoxLayout()
        font_label = QLabel("字号大小")
        font_label.setObjectName("SettingsLabel")
        font_header.addWidget(font_label)
        font_header.addStretch()

        self.font_value_label = QLabel(f"{self._font_size}px")
        self.font_value_label.setObjectName("SettingsValueLabel")
        font_header.addWidget(self.font_value_label)
        layout.addLayout(font_header)

        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setObjectName("SettingsSlider")
        self.font_slider.setMinimum(10)
        self.font_slider.setMaximum(24)
        self.font_slider.setValue(self._font_size)
        self.font_slider.setTickInterval(1)
        self.font_slider.valueChanged.connect(self._on_font_changed)
        layout.addWidget(self.font_slider)

        # --- 分隔线 ---
        layout.addWidget(self._separator())

        # --- 窗口置顶 ---
        top_row = QHBoxLayout()
        top_label = QLabel("窗口置顶")
        top_label.setObjectName("SettingsLabel")
        top_row.addWidget(top_label)
        top_row.addStretch()

        self.top_check = QCheckBox()
        self.top_check.setObjectName("SettingsCheck")
        self.top_check.setChecked(self._always_on_top)
        self.top_check.stateChanged.connect(self._on_top_changed)
        top_row.addWidget(self.top_check)
        layout.addLayout(top_row)

        # --- 底部关闭按钮 ---
        layout.addWidget(self._separator())

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("EditorSaveBtn")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFixedSize(80, 36)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        outer.addWidget(self.container)

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setObjectName("SettingsSeparator")
        return line

    # ========== 回调 ==========

    def _on_theme_changed(self, index: int):
        key = self.theme_combo.itemData(index)
        if key and key != self._theme_key:
            self._theme_key = key
            self.theme_changed.emit(key)

    def _on_opacity_changed(self, value: int):
        self._opacity = value / 100.0
        self.opacity_value_label.setText(f"{value}%")
        self.opacity_changed.emit(self._opacity)

    def _on_top_changed(self, state):
        checked = self.top_check.isChecked()
        self._always_on_top = checked
        self.always_on_top_changed.emit(checked)

    def _on_font_changed(self, value: int):
        self._font_size = value
        self.font_value_label.setText(f"{value}px")
        self.font_size_changed.emit(value)

    # ========== 拖拽 ==========

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos') and self._drag_pos:
            delta = event.globalPos() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

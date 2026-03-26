"""左侧标签栏 - 智能清单与自定义标签，点击弹出动画"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSizePolicy, QMenu, QScrollArea
)
from PyQt5.QtCore import pyqtSignal, QPropertyAnimation, QEasingCurve, QSize, Qt
from PyQt5.QtGui import QFont, QCursor


# 智能清单定义
SMART_LISTS = [
    {"key": "today", "icon": "☀", "label": "今日待办"},
    {"key": "week", "icon": "▦", "label": "本周计划"},
    {"key": "long_term", "icon": "◈", "label": "长期任务"},
]

# 可选标签图标（统一风格 unicode 符号，可随主题变色）
TAG_ICONS = [
    "★", "♦", "●", "◆", "▲", "■", "◉", "✶",
    "✦", "✧", "✡", "❀", "✻", "❖", "✵", "✚",
    "❥", "❃", "☀", "☂", "☘", "♫", "✤", "❆",
]

SIDEBAR_COLLAPSED_WIDTH = 36
SIDEBAR_EXPANDED_WIDTH = 50


class TagButton(QPushButton):
    """标签栏按钮"""

    def __init__(self, key, icon_text, label, parent=None):
        super().__init__(parent)
        self.key = key
        self.icon_text = icon_text
        self.label = label
        self.is_active = False

        self.setText(icon_text)
        self.setToolTip(label)
        self.setObjectName("TagBtn")
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_active(self, active: bool):
        self.is_active = active
        if active:
            self.setObjectName("TagBtnActive")
            self.setText(f"{self.icon_text}")
        else:
            self.setObjectName("TagBtn")
            self.setText(self.icon_text)
        # 强制刷新样式
        self.style().unpolish(self)
        self.style().polish(self)


class TagSidebar(QWidget):
    """左侧标签栏"""

    # 信号: (filter_type, filter_value)
    # filter_type: "smart_list" | "tag"
    # filter_value: smart_list key 或 tag_id
    filter_changed = pyqtSignal(str, str)
    tag_delete_requested = pyqtSignal(int)      # tag_id
    tag_edit_requested = pyqtSignal(int)         # tag_id
    tag_create_requested = pyqtSignal()          # 请求新建标签
    history_requested = pyqtSignal()             # 打开待办回顾

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TagSidebar")
        self.setFixedWidth(SIDEBAR_COLLAPSED_WIDTH)
        self._buttons = []
        self._current_key = None
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(3, 10, 3, 5)
        self._layout.setSpacing(4)

        # ── 顶部固定：智能清单 ──
        for item in SMART_LISTS:
            btn = TagButton(item["key"], item["icon"], item["label"])
            btn.clicked.connect(lambda checked, k=item["key"]: self._on_click(k))
            self._layout.addWidget(btn)
            self._buttons.append(btn)

        # 分隔线
        sep1 = QWidget()
        sep1.setFixedHeight(1)
        sep1.setObjectName("SidebarSeparator")
        self._layout.addWidget(sep1)

        # ── 中间可滚动：自定义标签 ──
        self._tag_scroll = QScrollArea()
        self._tag_scroll.setWidgetResizable(True)
        self._tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._tag_scroll.setFrameShape(QScrollArea.NoFrame)
        self._tag_scroll.setContentsMargins(0, 0, 0, 0)
        self._tag_scroll.setViewportMargins(0, 0, 0, 0)
        self._tag_scroll.setObjectName("TagScrollArea")

        self._tag_container = QWidget()
        self._tag_container.setToolTip("右键新建标签")
        self._tag_layout = QVBoxLayout(self._tag_container)
        self._tag_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_layout.setSpacing(4)
        self._tag_layout.setAlignment(Qt.AlignTop)

        self._tag_scroll.setWidget(self._tag_container)
        self._tag_scroll.setToolTip("右键新建标签")
        self._layout.addWidget(self._tag_scroll, 1)

        # ── 底部固定：待办回顾 ──
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setObjectName("SidebarSeparator")
        self._layout.addWidget(sep2)

        self.history_btn = QPushButton("▤")
        self.history_btn.setToolTip("过往每日待办")
        self.history_btn.setObjectName("TagBtn")
        self.history_btn.setFixedHeight(36)
        self.history_btn.setCursor(Qt.PointingHandCursor)
        self.history_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_btn.clicked.connect(lambda: self.history_requested.emit())
        self._layout.addWidget(self.history_btn)

        # 默认选中今日
        self._select_button("today")

    def add_custom_tag(self, tag_id: int, tag_name: str, tag_color: str = "#6366F1",
                       tag_icon: str = "📌"):
        """添加自定义标签到可滚动区域"""
        key = f"tag_{tag_id}"
        icon = tag_icon or "📌"
        btn = TagButton(key, icon, f"#{tag_name}")
        btn.clicked.connect(lambda checked, k=key: self._on_click(k))

        self._tag_layout.addWidget(btn)
        self._buttons.append(btn)

    def refresh_tags(self, tags):
        """刷新自定义标签列表"""
        # 移除旧的自定义标签按钮
        to_remove = [b for b in self._buttons if b.key.startswith("tag_")]
        for btn in to_remove:
            self._buttons.remove(btn)
            self._tag_layout.removeWidget(btn)
            btn.deleteLater()

        # 添加新的
        for tag in tags:
            self.add_custom_tag(tag.id, tag.name, tag.color,
                               getattr(tag, 'icon', '📌'))

    def _on_click(self, key: str):
        self._select_button(key)
        if key.startswith("tag_"):
            tag_id = key.replace("tag_", "")
            self.filter_changed.emit("tag", tag_id)
        else:
            self.filter_changed.emit("smart_list", key)

    def _select_button(self, key: str):
        if self._current_key == key:
            return
        self._current_key = key
        for btn in self._buttons:
            btn.set_active(btn.key == key)

    def get_current_key(self):
        return self._current_key

    def contextMenuEvent(self, event):
        """右键菜单：在空白处新建标签"""
        # 检查是否点击了自定义标签按钮
        child = self.childAt(event.pos())
        if isinstance(child, TagButton) and child.key.startswith("tag_"):
            self._show_tag_context_menu(child)
            return
        # 空白区域 → 新建标签
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(self.window().styleSheet())
        add_action = menu.addAction("➕ 新建标签")
        add_action.triggered.connect(lambda: self.tag_create_requested.emit())
        menu.exec_(QCursor.pos())

    def _show_tag_context_menu(self, btn: 'TagButton'):
        """自定义标签右键菜单：编辑/删除"""
        tag_id = int(btn.key.replace("tag_", ""))
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(self.window().styleSheet())
        edit_action = menu.addAction("✏ 编辑标签")
        edit_action.triggered.connect(lambda: self.tag_edit_requested.emit(tag_id))
        menu.addSeparator()
        del_action = menu.addAction("✖ 删除标签")
        del_action.triggered.connect(lambda: self.tag_delete_requested.emit(tag_id))
        menu.exec_(QCursor.pos())

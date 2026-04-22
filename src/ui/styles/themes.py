"""主题配置 - 5种主题配色方案"""


def hex_to_rgba(hex_color: str, opacity: float) -> str:
    """将 #RRGGBB + opacity(0~1) 转为 rgba(r,g,b,a) 字符串"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{opacity})"


def _is_dark_color(hex_color: str) -> bool:
    """判断颜色是否为深色（用于 tooltip 等需要区分明暗的场景）"""
    c = hex_color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (r * 299 + g * 587 + b * 114) / 1000 < 128


class Theme:
    """单个主题定义"""

    def __init__(self, name, bg_color, bg_opacity, primary_color, text_color,
                 text_secondary, border_color, hover_color, card_bg,
                 priority_high, priority_medium, priority_low):
        self.name = name
        self.bg_color = bg_color
        self.bg_opacity = bg_opacity
        self.primary_color = primary_color
        self.text_color = text_color
        self.text_secondary = text_secondary
        self.border_color = border_color
        self.hover_color = hover_color
        self.card_bg = card_bg
        self.priority_high = priority_high
        self.priority_medium = priority_medium
        self.priority_low = priority_low


# 深色半透明
DARK_THEME = Theme(
    name="深色半透明",
    bg_color="#1E1E2E",
    bg_opacity=0.95,
    primary_color="#6366F1",
    text_color="#FFFFFF",
    text_secondary="#A0A0B8",
    border_color="#2E2E42",
    hover_color="#2A2A40",
    card_bg="#262638",
    priority_high="#EF4444",
    priority_medium="#F59E0B",
    priority_low="#10B981",
)

# 浅色半透明
LIGHT_THEME = Theme(
    name="浅色半透明",
    bg_color="#F8FAFC",
    bg_opacity=0.92,
    primary_color="#3B82F6",
    text_color="#1E293B",
    text_secondary="#64748B",
    border_color="#E2E8F0",
    hover_color="#F1F5F9",
    card_bg="#FFFFFF",
    priority_high="#DC2626",
    priority_medium="#D97706",
    priority_low="#059669",
)

# 纯黑
BLACK_THEME = Theme(
    name="纯黑",
    bg_color="#000000",
    bg_opacity=1.0,
    primary_color="#A0937D",
    text_color="#E8E0D8",
    text_secondary="#8C8279",
    border_color="#2A2520",
    hover_color="#1A1714",
    card_bg="#0D0B09",
    priority_high="#C4736E",
    priority_medium="#C9A96E",
    priority_low="#7D9C88",
)

# 莫兰迪粉
MORANDY_THEME = Theme(
    name="莫兰迪粉",
    bg_color="#F5E6E8",
    bg_opacity=0.95,
    primary_color="#D4A5A5",
    text_color="#5C4033",
    text_secondary="#8B7D6B",
    border_color="#E8D5D5",
    hover_color="#F0DADA",
    card_bg="#FAF0F0",
    priority_high="#C75050",
    priority_medium="#C49A6C",
    priority_low="#7BA88E",
)

# 莫兰迪绿
GREEN_THEME = Theme(
    name="莫兰迪绿",
    bg_color="#E8F0E8",
    bg_opacity=0.95,
    primary_color="#7A9E7E",
    text_color="#2F3E2F",
    text_secondary="#6B7D6B",
    border_color="#C5D8C5",
    hover_color="#D6E6D6",
    card_bg="#F2F8F2",
    priority_high="#B85C5C",
    priority_medium="#C4A35A",
    priority_low="#5B8A6A",
)

# 主题注册表
THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "black": BLACK_THEME,
    "morandy": MORANDY_THEME,
    "green": GREEN_THEME,
}

DEFAULT_THEME_KEY = "dark"


def get_theme(key: str) -> Theme:
    return THEMES.get(key, DARK_THEME)


def get_theme_keys():
    return list(THEMES.keys())


DEFAULT_FONT_SIZE = 13  # 默认基础字号


def build_stylesheet(theme: Theme, bg_opacity: float = None,
                     font_size: int = None) -> str:
    """
    根据主题生成 QSS 样式表。
    bg_opacity: 背景透明度覆盖(0.3~1.0)，None则使用主题默认值。
    font_size: 基础字号(10~24px)，None则使用 DEFAULT_FONT_SIZE。
    """
    op = bg_opacity if bg_opacity is not None else theme.bg_opacity
    bg_rgba = hex_to_rgba(theme.bg_color, op)
    card_rgba = hex_to_rgba(theme.card_bg, min(1.0, op + 0.05))
    border_rgba = hex_to_rgba(theme.border_color, min(1.0, op + 0.1))
    hover_rgba = hex_to_rgba(theme.hover_color, min(1.0, op + 0.1))
    fs = font_size if font_size is not None else DEFAULT_FONT_SIZE
    # QToolTip 颜色：浅色主题用米白底+黑字，深色主题用黑底+白字
    if _is_dark_color(theme.bg_color):
        _tt_bg = "#1A1A1A"
        _tt_fg = "#FFFFFF"
        _tt_bd = "#555555"
    else:
        _tt_bg = "#FFFDF5"
        _tt_fg = "#333333"
        _tt_bd = "#D5CDBA"
    return f"""
    /* ===== 全局 ===== */
    QWidget {{
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: {fs}px;
        color: {theme.text_color};
    }}
    QToolTip {{
        background-color: {_tt_bg};
        color: {_tt_fg};
        border: 1px solid {_tt_bd};
        padding: 1px 3px;
        font-size: {max(10, fs - 2)}px;
    }}
    QLineEdit {{
        color: {theme.text_color};
        background-color: {card_rgba};
        selection-background-color: {theme.primary_color};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QLineEdit:hover {{
        color: {theme.text_color};
        background-color: {card_rgba};
    }}
    QTextEdit {{
        color: {theme.text_color};
        background-color: {card_rgba};
        selection-background-color: {theme.primary_color};
        selection-color: #FFFFFF;
    }}
    QTextEdit:focus, QTextEdit:hover {{
        color: {theme.text_color};
        background-color: {card_rgba};
    }}
    QComboBox {{
        color: {theme.text_color};
    }}
    QComboBox QAbstractItemView {{
        color: {theme.text_color};
        background-color: {card_rgba};
        selection-background-color: {theme.primary_color};
        selection-color: #FFFFFF;
    }}

    /* ===== 主容器（圆角背景） ===== */
    #MainContainer {{
        background-color: {bg_rgba};
        border-radius: 12px;
        border: 1px solid {border_rgba};
    }}

    /* ===== 标题栏 ===== */
    #TitleBar {{
        background-color: transparent;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        padding: 8px 12px;
    }}
    #TitleLabel {{
        font-size: {fs + 1}px;
        font-weight: bold;
        color: {theme.text_color};
    }}
    #TitleBarBtn {{
        background: transparent;
        border: none;
        color: {theme.text_color};
        font-size: {fs + 1}px;
        padding: 4px 8px;
        border-radius: 4px;
    }}
    #TitleBarBtn:hover {{
        background-color: {theme.hover_color};
        color: {theme.text_color};
    }}
    #PinBtnActive {{
        background-color: {theme.primary_color};
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
    }}
    #PinBtnActive:hover {{
        background-color: {theme.primary_color};
        opacity: 0.85;
    }}
    #CloseBtn:hover {{
        background-color: #EF4444;
        color: #FFFFFF;
    }}

    /* ===== 左侧标签栏 ===== */
    #TagSidebar {{
        background-color: transparent;
        border-right: 1px solid {border_rgba};
    }}
    #SidebarSeparator {{
        background-color: {hex_to_rgba(theme.border_color, 0.4)};
    }}
    #TagScrollArea {{
        background: transparent;
        border: none;
    }}
    #TagScrollArea QWidget {{
        background: transparent;
    }}
    #TagScrollArea QScrollBar:vertical {{
        width: 3px;
        background: transparent;
    }}
    #TagScrollArea QScrollBar::handle:vertical {{
        background: {hex_to_rgba(theme.text_secondary, 0.3)};
        border-radius: 1px;
    }}
    #TagScrollArea QScrollBar::add-line:vertical,
    #TagScrollArea QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    #TagBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {fs + 7}px;
        padding: 10px 6px;
        border-radius: 6px;
        text-align: center;
    }}
    #TagBtn:hover {{
        background-color: {hover_rgba};
    }}
    #TagBtnActive {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
        border: none;
        font-size: {fs + 7}px;
        padding: 10px 6px;
        border-radius: 6px;
        text-align: center;
    }}
    #TagBtnCustomActive {{
        background-color: {hex_to_rgba(theme.primary_color, 0.18)};
        color: {theme.primary_color};
        border: none;
        font-size: {fs + 7}px;
        padding: 10px 6px;
        border-radius: 6px;
        text-align: center;
    }}
    #TagBtnCustomActive:hover {{
        background-color: {hex_to_rgba(theme.primary_color, 0.28)};
    }}

    /* ===== 任务卡片 ===== */
    #TaskCard {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {border_rgba};
        border-radius: 0;
        padding: 4px 2px 4px 2px;
    }}
    #TaskCard:hover {{
        background-color: {hover_rgba};
    }}
    #TaskCard[selected="true"] {{
        background-color: {hex_to_rgba(theme.hover_color, 0.5)};
    }}
    #TaskTitle {{
        font-size: {fs}px;
        font-weight: 500;
        color: {theme.text_color};
    }}
    #TaskTitleDone {{
        font-size: {fs}px;
        color: {theme.text_secondary};
        text-decoration: line-through;
    }}
    #TaskMeta {{
        font-size: {max(10, fs - 2)}px;
        color: {theme.text_secondary};
    }}
    #TaskMetaOverdue {{
        font-size: {max(10, fs - 2)}px;
        color: {theme.priority_high};
        font-weight: bold;
    }}
    #TaskLinkBadge {{
        font-size: {max(10, fs - 2)}px;
        color: {theme.primary_color};
        padding: 0 4px;
    }}

    /* ===== 状态圆圈 ===== */
    #StatusCircle {{
        border: 2px solid {theme.text_secondary};
        border-radius: 6px;
        background: transparent;
        min-width: 12px;
        max-width: 12px;
        min-height: 12px;
        max-height: 12px;
        font-size: 8px;
    }}
    #StatusCircle:hover {{
        border-color: {theme.primary_color};
    }}
    #StatusCircleDone {{
        border: 2px solid {theme.primary_color};
        border-radius: 6px;
        background-color: {theme.primary_color};
        min-width: 12px;
        max-width: 12px;
        min-height: 12px;
        max-height: 12px;
        color: #FFFFFF;
        font-size: 8px;
    }}
    #StatusCircleProgress {{
        border: 2px solid {theme.primary_color};
        border-radius: 6px;
        background: transparent;
        min-width: 12px;
        max-width: 12px;
        min-height: 12px;
        max-height: 12px;
        font-size: 8px;
    }}

    /* ===== 滚动区域 ===== */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {theme.border_color};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {theme.text_secondary};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ===== 内联快速添加输入行 ===== */
    #InlineTaskInput {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        padding: 6px 8px;
        font-size: {fs}px;
        color: {theme.text_color};
    }}
    #InlineTaskInput:focus {{
        border: 1px solid {theme.primary_color};
        color: {theme.text_color};
        background-color: {card_rgba};
    }}
    #InlineDateCombo {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        padding: 2px 4px;
        font-size: {max(10, fs - 2)}px;
        color: {theme.text_color};
    }}
    #InlineDateCombo::drop-down {{
        border: none;
        width: 16px;
    }}
    #InlineDateCombo QAbstractItemView {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        color: {theme.text_color};
        selection-background-color: {hover_rgba};
    }}

    /* ===== 分任务 ===== */
    #SubtaskItem {{
        background-color: transparent;
        border: none;
    }}
    #SubtaskItem:hover {{
        background-color: {hover_rgba};
    }}
    #SubtaskCheck {{
        border: 1px solid {hex_to_rgba(theme.text_secondary, 0.45)};
        border-radius: 2px;
        background: transparent;
        font-size: 8px;
        color: transparent;
    }}
    #SubtaskCheckDone {{
        border: 1px solid {theme.primary_color};
        border-radius: 2px;
        background: {theme.primary_color};
        font-size: 8px;
        color: #FFFFFF;
    }}
    #SubtaskTitle {{
        font-size: {max(10, fs - 1)}px;
        color: {hex_to_rgba(theme.text_color, 0.72)};
    }}
    #SubtaskTitleDone {{
        font-size: {max(10, fs - 1)}px;
        color: {theme.text_secondary};
        text-decoration: line-through;
    }}
    #SubtaskToggle {{
        font-size: {max(9, fs - 2)}px;
        color: {theme.text_secondary};
        padding: 0px 4px;
        border-radius: 4px;
        background-color: {hover_rgba};
        border: none;
    }}
    #SubtaskToggle:hover {{
        color: {theme.text_color};
        background-color: {hover_rgba};
    }}
    #SubtaskAddBtn {{
        border: none;
        background: transparent;
        font-size: {max(9, fs - 2)}px;
        color: {theme.text_secondary};
        border-radius: 3px;
        padding: 0;
    }}
    #SubtaskAddBtn:hover {{
        background-color: {hover_rgba};
        color: {theme.primary_color};
    }}
    #SubtaskInput {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {border_rgba};
        border-radius: 0;
        padding: 1px 4px;
        font-size: {max(10, fs - 1)}px;
        color: {theme.text_secondary};
    }}
    #SubtaskInput:focus {{
        border-bottom: 1px solid {theme.primary_color};
        color: {theme.text_color};
    }}

    /* ===== 添加按钮 ===== */
    #AddTaskBtn {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-size: {fs}px;
        font-weight: bold;
        padding: 10px;
    }}
    #AddTaskBtn:hover {{
        background-color: {theme.primary_color};
        opacity: 0.9;
    }}

    /* ===== 优先级标签 ===== */
    #PriorityHigh {{
        color: {theme.priority_high};
        font-size: {max(10, fs - 2)}px;
        font-weight: bold;
    }}
    #PriorityMedium {{
        color: {theme.priority_medium};
        font-size: {max(10, fs - 2)}px;
        font-weight: bold;
    }}
    #PriorityLow {{
        color: {theme.priority_low};
        font-size: {max(10, fs - 2)}px;
        font-weight: bold;
    }}

    /* ===== 标签小标记 ===== */
    #TagChip {{
        background-color: {hover_rgba};
        color: {theme.text_secondary};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: {max(10, fs - 3)}px;
    }}

    /* ===== 任务编辑弹窗 ===== */
    #EditorContainer {{
        background-color: {bg_rgba};
        border-radius: 12px;
        border: 1px solid {border_rgba};
    }}
    #EditorTitle {{
        font-size: {fs + 3}px;
        font-weight: bold;
        color: {theme.text_color};
    }}
    #EditorCloseBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {fs + 1}px;
        border-radius: 4px;
    }}
    #EditorCloseBtn:hover {{
        background-color: #EF4444;
        color: #FFFFFF;
    }}
    #EditorFieldLabel {{
        font-size: {fs}px;
        font-weight: bold;
        color: {theme.text_color};
        margin-top: 2px;
    }}
    #EditorInput {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: {fs - 1}px;
        color: {theme.text_color};
    }}
    #EditorInput:focus {{
        border-color: {theme.primary_color};
        color: {theme.text_color};
        background-color: {card_rgba};
    }}
    #EditorTextArea {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        padding: 8px 10px;
        font-size: {fs - 1}px;
        color: {theme.text_color};
    }}
    #EditorTextArea:focus {{
        border-color: {theme.primary_color};
        color: {theme.text_color};
        background-color: {card_rgba};
    }}
    #EditorRadio {{
        font-size: {fs - 1}px;
        color: {theme.text_color};
        spacing: 6px;
    }}
    #EditorRadio::indicator {{
        width: 16px;
        height: 16px;
    }}
    #EditorSaveBtn {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        font-size: {fs - 1}px;
        font-weight: bold;
    }}
    #EditorSaveBtn:hover {{
        opacity: 0.9;
    }}
    #EditorCancelBtn {{
        background-color: transparent;
        color: {theme.text_secondary};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        font-size: {fs - 1}px;
    }}
    #EditorCancelBtn:hover {{
        background-color: {hover_rgba};
        color: {theme.text_color};
    }}
    #EditorSmallBtn {{
        background-color: transparent;
        color: {theme.primary_color};
        border: 1px solid {theme.primary_color};
        border-radius: 6px;
        font-size: {max(10, fs - 2)}px;
        padding: 4px 10px;
    }}
    #EditorSmallBtn:hover {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
    }}

    /* ===== 右键菜单 ===== */
    QMenu {{
        background-color: {hex_to_rgba(theme.bg_color, 1.0)};
        border: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        border-radius: 6px;
        padding: 2px 0;
    }}
    QMenu::item {{
        padding: 2px 10px;
        min-height: 16px;
        color: {theme.text_color};
        font-size: {max(10, fs - 2)}px;
    }}
    QMenu::item:selected {{
        background-color: {hex_to_rgba(theme.hover_color, 1.0)};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {hex_to_rgba(theme.border_color, 1.0)};
        margin: 2px 6px;
    }}

    /* ===== 设置面板 ===== */
    #SettingsLabel {{
        font-size: {fs - 1}px;
        font-weight: bold;
        color: {theme.text_color};
    }}
    #SettingsValueLabel {{
        font-size: {max(10, fs - 2)}px;
        color: {theme.primary_color};
        font-weight: bold;
    }}
    #SettingsCombo {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: {fs - 1}px;
        color: {theme.text_color};
    }}
    #SettingsCombo::drop-down {{
        border: none;
        width: 24px;
    }}
    #SettingsCombo QAbstractItemView {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        color: {theme.text_color};
        selection-background-color: {hover_rgba};
    }}
    #SettingsSlider::groove:horizontal {{
        border: none;
        height: 6px;
        background-color: {border_rgba};
        border-radius: 3px;
    }}
    #SettingsSlider::handle:horizontal {{
        background-color: {theme.primary_color};
        border: none;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    #SettingsSlider::sub-page:horizontal {{
        background-color: {theme.primary_color};
        border-radius: 3px;
    }}
    #SettingsCheck {{
        spacing: 6px;
        font-size: {max(10, fs - 2)}px;
        color: {theme.text_color};
    }}
    #SettingsCheck::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 3px;
        border: 2px solid {theme.text_secondary};
    }}
    #SettingsCheck::indicator:checked {{
        background-color: {theme.primary_color};
        border-color: {theme.primary_color};
    }}
    #SettingsSeparator {{
        background-color: {hex_to_rgba(theme.border_color, 0.3)};
        border: none;
        max-height: 1px;
    }}

    /* ===== 日历弹窗（全不透明，因为是独立弹窗窗口） ===== */
    QCalendarWidget {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        border: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        border-radius: 12px;
    }}
    QCalendarWidget QWidget {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        color: {theme.text_color};
    }}
    QCalendarWidget QToolButton {{
        color: {theme.text_color};
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 4px 8px;
        font-weight: bold;
    }}
    QCalendarWidget QToolButton:hover {{
        background-color: {hex_to_rgba(theme.hover_color, 1.0)};
    }}
    QCalendarWidget QToolButton#qt_calendar_prevmonth,
    QCalendarWidget QToolButton#qt_calendar_nextmonth {{
        color: {theme.primary_color};
        font-weight: bold;
    }}
    QCalendarWidget QAbstractItemView {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        color: {theme.text_color};
        selection-background-color: {theme.primary_color};
        selection-color: #FFFFFF;
        border: none;
        outline: none;
    }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: {hex_to_rgba(theme.bg_color, 1.0)};
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        padding: 4px;
    }}
    QCalendarWidget QSpinBox {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        color: {theme.text_color};
        border: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        border-radius: 4px;
        padding: 2px 4px;
    }}
    QCalendarWidget QMenu {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        border: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        border-radius: 8px;
        color: {theme.text_color};
    }}
    QCalendarWidget QMenu::item:selected {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
    }}

    /* ===== 确认弹窗 ===== */
    #ConfirmDialog {{
        background-color: {bg_rgba};
        border-radius: 12px;
        border: 1px solid {border_rgba};
    }}
    #ConfirmMsg {{
        font-size: {fs}px;
        color: {theme.text_color};
    }}

    /* ===== 任务-便签关联弹窗 ===== */
    #LinkDialog {{
        background-color: {bg_rgba};
        border: 1px solid {border_rgba};
        border-radius: 12px;
    }}
    #LinkDialogTitle {{
        color: {theme.text_color};
        font-size: {max(10, fs - 1)}px;
        font-weight: bold;
    }}
    #LinkListWidget {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        color: {theme.text_color};
        outline: none;
    }}
    #LinkListWidget::item {{
        padding: 4px 6px;
        border-radius: 4px;
    }}
    #LinkListWidget::item:selected {{
        background-color: {hex_to_rgba(theme.hover_color, 0.72)};
        color: {theme.text_color};
    }}
    #LinkRowCard {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 6px;
    }}
    #LinkPrimaryBtn {{
        background-color: {hex_to_rgba(theme.hover_color, 0.68)};
        border: 1px solid {border_rgba};
        border-radius: 6px;
        color: {theme.text_color};
        padding: 2px 10px;
        font-size: {max(10, fs - 2)}px;
    }}
    #LinkPrimaryBtn:hover {{
        background-color: {hex_to_rgba(theme.hover_color, 0.9)};
    }}
    #LinkGhostBtn {{
        background-color: transparent;
        border: 1px solid {hex_to_rgba(theme.border_color, 0.95)};
        border-radius: 6px;
        color: {theme.text_secondary};
        padding: 1px 8px;
        font-size: {max(10, fs - 2)}px;
    }}
    #LinkGhostBtn:hover {{
        background-color: {hex_to_rgba(theme.hover_color, 0.6)};
        color: {theme.text_color};
    }}
    #LinkCloseBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {fs}px;
        border-radius: 4px;
    }}
    #LinkCloseBtn:hover {{
        background-color: {theme.priority_high};
        color: #FFFFFF;
    }}

    /* ===== 回收站按钮 ===== */
    #TrashBtn {{
        background: transparent;
        border: 1px solid {border_rgba};
        border-radius: 8px;
        font-size: {fs}px;
        color: {theme.text_secondary};
    }}
    #TrashBtn:hover {{
        background-color: {hover_rgba};
        border-color: {theme.primary_color};
        color: {theme.text_color};
    }}

    /* ===== 回收站面板 ===== */
    #TrashScroll {{
        background-color: transparent;
        border: none;
    }}
    #TrashScroll QWidget {{
        background-color: transparent;
    }}
    #TrashItem {{
        background-color: {hex_to_rgba(theme.card_bg, 1.0)};
        border: 1px solid {hex_to_rgba(theme.border_color, 1.0)};
        border-radius: 4px;
        padding: 2px 4px;
    }}
    #TrashRestoreBtn {{
        background: transparent;
        border: 1px solid {theme.primary_color};
        border-radius: 4px;
        color: {theme.primary_color};
        font-size: {max(10, fs - 2)}px;
        padding: 2px 8px;
    }}
    #TrashRestoreBtn:hover {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
    }}
    #TrashDeleteBtn {{
        background: transparent;
        border: 1px solid {theme.priority_high};
        border-radius: 4px;
        color: {theme.priority_high};
        font-size: {max(10, fs - 2)}px;
        padding: 2px 8px;
    }}
    #TrashDeleteBtn:hover {{
        background-color: {theme.priority_high};
        color: #FFFFFF;
    }}

    /* ===== 移交今日按钮 ===== */
    #CarryForwardBtn {{
        background: transparent;
        border: 1px solid {theme.primary_color};
        border-radius: 4px;
        color: {theme.primary_color};
        font-size: {max(10, fs - 2)}px;
        padding: 1px 8px;
    }}
    #CarryForwardBtn:hover {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
    }}
    #TaskTitleCarryover {{
        font-size: {fs}px;
        color: {theme.text_secondary};
        font-style: italic;
    }}

    /* ===== 待办回顾 ===== */
    #HistoryDateLabel {{
        font-size: {fs}px;
        font-weight: bold;
        color: {theme.primary_color};
        padding: 6px 0 2px 0;
    }}
    #HistoryTitle {{
        font-size: {max(10, fs - 1)}px;
        color: {theme.text_color};
    }}
    #HistoryTitleDone {{
        font-size: {max(10, fs - 1)}px;
        color: {theme.text_secondary};
        text-decoration: line-through;
    }}
    #HistoryDone {{
        font-size: {max(10, fs - 1)}px;
        color: {theme.primary_color};
    }}
    #HistoryTodo {{
        font-size: {max(10, fs - 1)}px;
        color: {theme.text_secondary};
    }}

    /* ===== Tab 切换（标题栏左侧） ===== */
    #TodoTabActive, #NoteTabActive {{
        background-color: {hover_rgba};
        border: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: {fs + 1}px;
        font-weight: bold;
        color: {theme.text_color};
        padding: 4px 10px;
    }}
    #TodoTabInactive, #NoteTabInactive {{
        background: transparent;
        border: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: {max(10, fs - 1)}px;
        font-weight: normal;
        color: {theme.text_secondary};
        padding: 4px 10px;
    }}
    #TodoTabInactive:hover, #NoteTabInactive:hover {{
        background-color: {hex_to_rgba(theme.hover_color, 0.5)};
        color: {theme.text_color};
    }}

    /* ===== 便签面板 ===== */
    #NoteFormatCard {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 8px;
        margin: 0 4px 0 0;
    }}
    #NoteFormatBtn {{
        background: transparent;
        border: none;
        border-radius: 4px;
        color: {theme.text_color};
        font-size: {fs}px;
        padding: 2px;
    }}
    #NoteFormatBtn:hover {{
        color: {theme.text_color};
        background-color: {hex_to_rgba(theme.text_secondary, 0.25)};
    }}
    #NoteFormatBtn:checked {{
        background-color: {theme.primary_color};
        color: #FFFFFF;
    }}
    #NoteFormatToggleBtn {{
        background: transparent;
        border: none;
        border-radius: 0;
        color: {theme.text_secondary};
        font-size: {max(10, fs - 1)}px;
        padding: 0;
    }}
    #NoteFormatToggleBtn:hover {{
        background-color: {hover_rgba};
        color: {theme.text_color};
    }}
    #NoteTitlePrefix {{
        background: transparent;
        border: none;
        padding: 6px 0px 2px 12px;
        font-size: {max(10, fs - 2)}px;
        color: {theme.text_secondary};
    }}
    #NoteTitleInput {{
        background: transparent;
        border: none;
        border-radius: 0;
        padding: 6px 12px 2px 12px;
        font-size: {fs + 1}px;
        font-weight: bold;
        color: {theme.text_color};
    }}
    #NoteTitleInput:focus, #NoteTitleInput:hover {{
        background: transparent;
        color: {theme.text_color};
    }}
    #NoteBodyEdit {{
        background: transparent;
        border: none;
        padding: 2px 12px 8px 12px;
        font-size: {fs}px;
        color: {theme.text_color};
    }}
    #NoteBodyEdit:focus, #NoteBodyEdit:hover {{
        background: transparent;
    }}
    #NoteBottomContainer {{
        background: transparent;
        border: none;
    }}
    #NoteListPanel {{
        background-color: {card_rgba};
        border: 1px solid {border_rgba};
        border-radius: 8px;
    }}
    #NoteListDragHandle {{
        background-color: {hex_to_rgba(theme.border_color, 0.3)};
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }}
    #NoteListDragHandle:hover {{
        background-color: {hex_to_rgba(theme.border_color, 0.5)};
    }}
    #NoteSearchContainer {{
        background: transparent;
    }}
    #NoteSearchIcon {{
        color: {theme.text_secondary};
        font-size: {fs}px;
    }}
    #NoteSearchInput {{
        background-color: {hex_to_rgba(theme.hover_color, 0.3)};
        border: 1px solid {hex_to_rgba(theme.border_color, 0.5)};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: {fs - 1}px;
        color: {theme.text_color};
    }}
    #NoteSearchInput:focus {{
        background-color: {hex_to_rgba(theme.hover_color, 0.4)};
        border-color: {theme.border_color};
    }}
    #NoteSearchCount {{
        color: {theme.text_secondary};
        font-size: {fs - 2}px;
    }}
    #NoteSearchClearBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {fs - 1}px;
        border-radius: 3px;
    }}
    #NoteSearchClearBtn:hover {{
        background-color: {hex_to_rgba(theme.priority_high, 0.8)};
        color: #FFFFFF;
    }}
    #FloatingNoteContainer {{
        background-color: {bg_rgba};
        border: 1px solid {border_rgba};
        border-radius: 12px;
    }}
    #FloatingNoteTitleBar {{
        background-color: transparent;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom: 1px solid {border_rgba};
    }}
    #FloatingNoteTitleLabel {{
        font-size: {max(10, fs - 1)}px;
        font-weight: bold;
        color: {theme.text_secondary};
        background: transparent;
    }}
    #FloatingNoteCloseBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {fs}px;
        border-radius: 4px;
    }}
    #FloatingNoteCloseBtn:hover {{
        background-color: {theme.priority_high};
        color: #FFFFFF;
    }}
    #FloatingNotePinBtn {{
        background: transparent;
        border: none;
        border-radius: 4px;
    }}
    #FloatingNotePinBtn:hover {{
        background-color: {hex_to_rgba(theme.hover_color, 0.3)};
    }}
    #FloatingNotePinBtnActive {{
        background-color: {theme.primary_color};
        border: none;
        border-radius: 4px;
    }}
    #FloatingNotePinBtnActive:hover {{
        background-color: {hex_to_rgba(theme.primary_color, 0.8)};
    }}
    #FloatingNoteTitleInput {{
        background: transparent;
        border: none;
        border-radius: 0;
        padding: 4px 12px;
        font-size: {fs}px;
        font-weight: bold;
        color: {theme.text_color};
    }}
    #FloatingNoteTitleInput:focus, #FloatingNoteTitleInput:hover {{
        background: transparent;
        color: {theme.text_color};
    }}
    #FloatingNoteTitleInput::placeholder {{
        color: {theme.text_secondary};
    }}
    #FloatingNoteBodyEdit {{
        background: transparent;
        border: none;
        padding: 2px 12px 8px 12px;
        font-size: {fs}px;
        color: {theme.text_color};
    }}
    #FloatingNoteBodyEdit:focus, #FloatingNoteBodyEdit:hover {{
        background: transparent;
    }}
    #FloatingNoteBodyEdit::placeholder {{
        color: {theme.text_secondary};
    }}
    #NoteListScroll {{
        background: transparent;
        border: none;
    }}
    #NoteListScroll > QWidget {{
        background: transparent;
    }}
    #NoteListScrollContent {{
        background: transparent;
    }}
    #NoteListHeader {{
        background: transparent;
        border-bottom: 1px solid {border_rgba};
    }}
    #NoteListHeaderLabel {{
        font-size: {max(10, fs - 1)}px;
        font-weight: bold;
        color: {theme.text_secondary};
    }}
    #NoteListItem {{
        background: transparent;
        border-bottom: 1px solid {hex_to_rgba(theme.border_color, 0.4)};
    }}
    #NoteListItem:hover {{
        background-color: {hover_rgba};
    }}
    #NoteListItem[selected="true"], #NoteListItemActive[selected="true"] {{
        background-color: {hex_to_rgba(theme.primary_color, 0.18)};
        border-left: 2px solid {theme.primary_color};
    }}
    #NoteListItemActive {{
        background-color: {hex_to_rgba(theme.primary_color, 0.12)};
        border-bottom: 1px solid {hex_to_rgba(theme.border_color, 0.4)};
    }}
    #NoteListItemLabel {{
        font-size: {fs}px;
        color: {theme.text_color};
    }}
    #NoteListItemDate {{
        font-size: {max(10, fs - 2)}px;
        color: {theme.text_secondary};
    }}
    #NoteListDelBtn {{
        background: transparent;
        border: none;
        color: {theme.text_secondary};
        font-size: {max(10, fs - 2)}px;
        border-radius: 3px;
        padding: 0;
    }}
    #NoteListDelBtn:hover {{
        color: {theme.priority_high};
        background-color: {hover_rgba};
    }}
    #NoteBottomBar {{
        background: transparent;
    }}
    #NoteAddBtn {{
        background: transparent;
        border: 1px solid {border_rgba};
        border-radius: 6px;
        color: {theme.primary_color};
        font-size: {fs + 2}px;
        font-weight: bold;
    }}
    #NoteAddBtn:hover {{
        background-color: {theme.primary_color};
        border-color: {theme.primary_color};
        color: #FFFFFF;
    }}
    #NoteCurrentBtn {{
        background: transparent;
        border: 1px solid {border_rgba};
        border-radius: 6px;
        color: {theme.text_secondary};
        font-size: {max(10, fs - 1)}px;
        text-align: left;
        padding: 4px 10px;
    }}
    #NoteCurrentBtn:hover {{
        background-color: {hover_rgba};
        color: {theme.text_color};
    }}
    #NoteDelBtn {{
        background: transparent;
        border: 1px solid {border_rgba};
        border-radius: 6px;
        color: {theme.text_secondary};
        font-size: {fs}px;
    }}
    #NoteDelBtn:hover {{
        background-color: {hover_rgba};
        border-color: {theme.priority_high};
        color: {theme.priority_high};
    }}
    """

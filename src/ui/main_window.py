"""主悬浮窗口 - 无边框、透明、可拖拽、可缩放"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGraphicsDropShadowEffect, QSizePolicy,
    QApplication, QDialog, QFrame, QScrollArea,
)
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal, QEvent
from PyQt5.QtGui import QColor, QCursor, QIcon, QPalette, QPen, QPainter, QPixmap

from src.models.database import init_db, get_session
from src.models.task import Task
from src.services.task_service import TaskService
from src.services.tag_service import TagService
from src.services.filter_service import FilterService
from src.utils.config_manager import ConfigManager
from src.ui.styles.themes import get_theme, build_stylesheet, DEFAULT_THEME_KEY, DEFAULT_FONT_SIZE
from src.ui.tag_sidebar import TagSidebar
from src.ui.task_list import TaskListWidget
from src.ui.task_editor import TaskEditorDialog
from src.ui.settings_panel import SettingsPanel
from src.ui.system_tray import SystemTray

RESIZE_MARGIN = 6
CORNER_MARGIN = 16
MIN_WIDTH = 300
MIN_HEIGHT = 450


class MainWindow(QMainWindow):
    """桌面待办主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化后端
        init_db()
        self._session = get_session()
        self.task_service = TaskService(self._session)
        self.tag_service = TagService(self._session)
        self.filter_service = FilterService(self._session)
        self.config = ConfigManager()

        # 窗口状态
        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geo = None

        # 加载主题
        theme_key = self.config.get("theme.mode", DEFAULT_THEME_KEY)
        self.current_theme = get_theme(theme_key)

        self._setup_window()
        self._setup_ui()
        self._apply_theme()
        self._load_position()
        # 设置初始内联输入模式（默认今日待办）
        self.task_list.set_input_mode("today")
        self._refresh_tasks()

        # 全局鼠标跟踪 + 事件过滤器（用于边缘缩放）
        self._enable_mouse_tracking(self)
        QApplication.instance().installEventFilter(self)

    # ========== 窗口配置 ==========

    def _setup_window(self):
        self._always_on_top = self.config.get("window.always_on_top", True)
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        # 设置窗口图标
        from src.utils.paths import get_app_root
        import os
        icon_path = os.path.join(str(get_app_root()), "app图标.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 从配置恢复大小
        w = self.config.get("window.width", 380)
        h = self.config.get("window.height", 680)
        self.resize(w, h)

        # 背景透明度由 QSS rgba 控制，不用 setWindowOpacity（那会让文字也变透明）
        self._bg_opacity = self.config.get("window.opacity", 0.95)
        self._font_size = self.config.get("window.font_size", DEFAULT_FONT_SIZE)

    # ========== UI 构建 ==========

    def _setup_ui(self):
        # 中央 widget（透明背景）
        central = QWidget()
        central.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)  # 阴影留白
        root_layout.setSpacing(0)

        # 主容器（圆角背景）
        self.main_container = QWidget()
        self.main_container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.main_container.setGraphicsEffect(shadow)

        # --- 标题栏 ---
        title_bar = self._build_title_bar()
        container_layout.addWidget(title_bar)

        # --- 内容区（左侧标签栏 + 右侧任务列表） ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 左侧标签栏
        self.sidebar = TagSidebar()
        self.sidebar.filter_changed.connect(self._on_filter_changed)
        self.sidebar.tag_delete_requested.connect(self._on_tag_delete)
        self.sidebar.tag_edit_requested.connect(self._on_tag_edit)
        self.sidebar.tag_create_requested.connect(self._on_tag_create)
        self.sidebar.history_requested.connect(self._on_open_history)
        content_layout.addWidget(self.sidebar)

        # 右侧内容
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 4, 0, 4)
        right_layout.setSpacing(4)

        # 筛选标题行（标题 + 副标题同行）
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(8, 2, 8, 0)
        title_row_layout.setSpacing(6)

        self.filter_title = QLabel("今日待办")
        self.filter_title.setObjectName("TitleLabel")
        title_row_layout.addWidget(self.filter_title)

        self.filter_subtitle = QLabel("未来10天计划")
        self.filter_subtitle.setObjectName("TaskMeta")
        self.filter_subtitle.setVisible(False)
        title_row_layout.addWidget(self.filter_subtitle)

        title_row_layout.addStretch()
        right_layout.addWidget(title_row)

        # 任务列表
        self.task_list = TaskListWidget()
        self.task_list.status_changed.connect(self._on_task_status_changed)
        self.task_list.edit_requested.connect(self._on_task_edit)
        self.task_list.delete_requested.connect(self._on_task_delete)
        self.task_list.carry_forward_requested.connect(self._on_carry_forward)
        self.task_list.reschedule_requested.connect(self._on_reschedule_weekly)
        self.task_list.create_requested.connect(self._on_add_task)
        self.task_list.quick_create.connect(self._on_quick_create)
        self.task_list.subtask_status_changed.connect(self._on_subtask_status_changed)
        self.task_list.subtask_create_requested.connect(self._on_subtask_create)
        self.task_list.subtask_delete_requested.connect(self._on_subtask_delete)
        right_layout.addWidget(self.task_list, 1)

        # 底部栏：添加按钮 + 回收站按钮
        btn_wrapper = QWidget()
        btn_layout = QHBoxLayout(btn_wrapper)
        btn_layout.setContentsMargins(8, 4, 8, 8)
        btn_layout.setSpacing(6)

        self.add_btn = QPushButton("＋ 添加")
        self.add_btn.setObjectName("AddTaskBtn")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedHeight(36)
        self.add_btn.clicked.connect(self._on_add_task)
        btn_layout.addWidget(self.add_btn, 1)

        self.trash_btn = QPushButton("🗑")
        self.trash_btn.setObjectName("TrashBtn")
        self.trash_btn.setCursor(Qt.PointingHandCursor)
        self.trash_btn.setFixedSize(36, 36)
        self.trash_btn.setToolTip("回收站")
        self.trash_btn.clicked.connect(self._on_open_trash)
        btn_layout.addWidget(self.trash_btn, 0)

        right_layout.addWidget(btn_wrapper)

        content_layout.addWidget(right, 1)
        container_layout.addWidget(content, 1)

        root_layout.addWidget(self.main_container)

        # 刷新标签栏
        self._refresh_sidebar_tags()

        # 系统托盘
        self._setup_tray()

    def _build_title_bar(self):
        bar = QWidget()
        bar.setObjectName("TitleBar")
        bar.setFixedHeight(40)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(6)

        title = QLabel("桌面待办")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)
        layout.addStretch()

        # 置顶图钉按钮
        self.pin_btn = QPushButton()
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setToolTip("窗口置顶")
        self.pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_style()
        layout.addWidget(self.pin_btn)

        # 设置按钮
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("TitleBarBtn")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.clicked.connect(self._on_open_settings)
        layout.addWidget(settings_btn)

        # 最小化按钮
        min_btn = QPushButton("─")
        min_btn.setObjectName("TitleBarBtn")
        min_btn.setFixedSize(28, 28)
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.clicked.connect(self._on_minimize)
        layout.addWidget(min_btn)

        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setObjectName("TitleBarBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return bar

    # ========== 图钉按钮 ==========

    def _create_pin_icon(self, color_str: str, size: int = 18) -> QIcon:
        """用 QPainter 绘制图钉（thumbtack）图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color_str))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        s = size
        # 顶部横杠（钉帽）
        p.drawLine(int(s * 0.2), int(s * 0.18), int(s * 0.8), int(s * 0.18))
        # 两条斜线向下汇聚（钉身）
        p.drawLine(int(s * 0.28), int(s * 0.18), int(s * 0.5), int(s * 0.55))
        p.drawLine(int(s * 0.72), int(s * 0.18), int(s * 0.5), int(s * 0.55))
        # 竖线（钉尖）
        p.drawLine(int(s * 0.5), int(s * 0.55), int(s * 0.5), int(s * 0.85))
        p.end()
        return QIcon(pixmap)

    def _toggle_pin(self):
        self.set_always_on_top(not self._always_on_top)

    def _update_pin_style(self):
        """根据置顶状态更新图钉按钮外观"""
        if self._always_on_top:
            self.pin_btn.setObjectName("PinBtnActive")
            icon = self._create_pin_icon("#FFFFFF")
        else:
            self.pin_btn.setObjectName("TitleBarBtn")
            icon = self._create_pin_icon(self.current_theme.text_secondary)
        self.pin_btn.setIcon(icon)
        self.pin_btn.style().unpolish(self.pin_btn)
        self.pin_btn.style().polish(self.pin_btn)

    # ========== 主题 ==========

    def _apply_theme(self):
        qss = build_stylesheet(self.current_theme, self._bg_opacity, self._font_size)
        try:
            self.setStyleSheet(qss)
        except Exception:
            pass
        # 强制设置 QPalette，防止 Active/Inactive 调色板组的默认颜色覆盖 QSS
        self._apply_theme_palette()
        # 刷新图钉按钮图标颜色
        if hasattr(self, 'pin_btn'):
            self._update_pin_style()
        # QSS 重刷可能导致 QGraphicsDropShadowEffect 失效，重建阴影
        self._rebuild_shadow()

    def _apply_theme_palette(self):
        """根据当前主题设置 QPalette，确保 Active/Inactive/Disabled 三组颜色一致"""
        t = self.current_theme
        palette = QPalette()
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            palette.setColor(group, QPalette.WindowText, QColor(t.text_color))
            palette.setColor(group, QPalette.Text, QColor(t.text_color))
            palette.setColor(group, QPalette.Base, QColor(t.card_bg))
            palette.setColor(group, QPalette.Window, QColor(t.bg_color))
            palette.setColor(group, QPalette.Button, QColor(t.card_bg))
            palette.setColor(group, QPalette.ButtonText, QColor(t.text_color))
            palette.setColor(group, QPalette.Highlight, QColor(t.primary_color))
            palette.setColor(group, QPalette.HighlightedText, QColor("#FFFFFF"))
            palette.setColor(group, QPalette.BrightText, QColor(t.text_color))
            palette.setColor(group, QPalette.ToolTipBase, QColor(t.card_bg))
            palette.setColor(group, QPalette.ToolTipText, QColor(t.text_color))
        # PlaceholderText 在 Qt 5.12+ 可用
        try:
            for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                palette.setColor(group, QPalette.PlaceholderText, QColor(t.text_secondary))
        except AttributeError:
            pass
        QApplication.instance().setPalette(palette)

    def _rebuild_shadow(self):
        """QSS 重刷后重建阴影效果，防止 QGraphicsDropShadowEffect 失效"""
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(16)
            shadow.setOffset(0, 2)
            shadow.setColor(QColor(0, 0, 0, 80))
            self.main_container.setGraphicsEffect(shadow)
        except Exception:
            pass

    def switch_theme(self, theme_key: str):
        self.current_theme = get_theme(theme_key)
        self._apply_theme()
        self.config.set("theme.mode", theme_key)

    def set_bg_opacity(self, opacity: float):
        """设置背景透明度 (0.3 ~ 1.0)，文字不受影响"""
        self._bg_opacity = max(0.3, min(1.0, opacity))
        self._apply_theme()
        self.config.set("window.opacity", self._bg_opacity)

    def set_font_size(self, size: int):
        """设置基础字号 (10 ~ 24px)"""
        self._font_size = max(10, min(24, size))
        self._apply_theme()
        self.config.set("window.font_size", self._font_size)

    # ========== 数据刷新 ==========

    def _refresh_tasks(self):
        """根据当前筛选条件刷新任务列表"""
        from datetime import date as _date
        key = self.sidebar.get_current_key() or "today"
        carryover_ids = set()

        week_overdue_ids = set()

        if key == "today":
            tasks = self.filter_service.get_today_tasks()
            today = _date.today()
            carryover_ids = {
                t.id for t in tasks
                if t.task_date is None or t.task_date < today
            }
        elif key == "week":
            tasks = self.filter_service.get_week_tasks()
            today = _date.today()
            week_overdue_ids = {
                t.id for t in tasks
                if t.due_date and t.due_date < today
                and t.status not in ("done", "cancelled")
            }
        elif key == "long_term":
            tasks = self.filter_service.get_long_term_tasks()
        elif key.startswith("tag_"):
            tag_id = int(key.replace("tag_", ""))
            tasks = self.filter_service.get_tasks_by_tag(tag_id)
        else:
            tasks = self.filter_service.get_active_tasks()

        subtasks_map = {}
        for task in tasks:
            subs = self.task_service.get_subtasks(task.id)
            if subs:
                subtasks_map[task.id] = subs
        self.task_list.set_tasks(tasks, carryover_ids=carryover_ids,
                                 week_overdue_ids=week_overdue_ids,
                                 subtasks_map=subtasks_map)
        # 新创建的任务项控件需要启用鼠标跟踪
        self._enable_mouse_tracking(self.task_list)

    def _refresh_sidebar_tags(self):
        tags = self.tag_service.get_all_tags()
        self.sidebar.refresh_tags(tags)

    # ========== 信号处理 ==========

    def _on_filter_changed(self, filter_type: str, filter_value: str):
        titles = {
            "today": "今日待办",
            "week": "本周计划",
            "long_term": "长期任务",
        }
        if filter_type == "smart_list":
            self.filter_title.setText(titles.get(filter_value, "全部任务"))
            self.filter_subtitle.setVisible(filter_value == "week")
            # 设置内联输入行模式（今日/本周显示，其他隐藏）
            self.task_list.set_input_mode(filter_value)
        else:
            tag = self.tag_service.get_tag(int(filter_value))
            if tag:
                self.filter_title.setText(f"# {tag.name}")
            self.filter_subtitle.setVisible(False)
            self.task_list.set_input_mode("tag")
        self._refresh_tasks()

    def _on_task_status_changed(self, task_id: int, new_status: str):
        self.task_service.update_status(task_id, new_status)
        self._refresh_tasks()

    def _on_task_edit(self, task_id: int):
        """打开编辑弹窗（编辑已有任务）"""
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        tags = self.tag_service.get_all_tags()
        dialog = TaskEditorDialog(tags, task=task, parent=self)
        dialog.set_add_tag_callback(self._create_tag_from_editor)
        dialog.setStyleSheet(self.styleSheet())

        if dialog.exec_():
            data = dialog.get_data()
            self.task_service.update_task(task_id, **data)
            self._refresh_tasks()
            self._refresh_sidebar_tags()

    def _get_current_default_type(self) -> str:
        """根据当前侧栏选中项返回默认任务类型"""
        key = self.sidebar.get_current_key() or "today"
        type_map = {
            "today": Task.TYPE_SHORT_TERM,
            "week": Task.TYPE_WEEKLY,
            "long_term": Task.TYPE_LONG_TERM,
        }
        return type_map.get(key, Task.TYPE_SHORT_TERM)

    def _on_add_task(self):
        """打开编辑弹窗（新建任务），自动对应当前列表类型"""
        tags = self.tag_service.get_all_tags()
        default_type = self._get_current_default_type()

        # 自定义标签视图下：自动选中该标签 + 默认长期任务
        default_tag_ids = None
        key = self.sidebar.get_current_key() or "today"
        if key.startswith("tag_"):
            try:
                tag_id = int(key.replace("tag_", ""))
                default_tag_ids = [tag_id]
                default_type = Task.TYPE_LONG_TERM
            except (ValueError, TypeError):
                pass

        dialog = TaskEditorDialog(tags, parent=self, default_type=default_type,
                                  default_tag_ids=default_tag_ids)
        dialog.set_add_tag_callback(self._create_tag_from_editor)
        dialog.setStyleSheet(self.styleSheet())

        if dialog.exec_():
            data = dialog.get_data()
            self.task_service.create_task(**data)
            self._refresh_tasks()
            self._refresh_sidebar_tags()

    def _on_quick_create(self, title: str, due_date):
        """内联输入行快速创建任务（默认参数）"""
        key = self.sidebar.get_current_key() or "today"
        if key == "today":
            self.task_service.create_task(
                title=title,
                task_type=Task.TYPE_SHORT_TERM,
                priority="medium",
            )
        elif key == "week":
            self.task_service.create_task(
                title=title,
                task_type=Task.TYPE_WEEKLY,
                due_date=due_date,
                priority="medium",
            )
        elif key == "long_term":
            self.task_service.create_task(
                title=title,
                task_type=Task.TYPE_LONG_TERM,
                priority="medium",
            )
        elif key.startswith("tag_"):
            try:
                tag_id = int(key.replace("tag_", ""))
            except ValueError:
                tag_id = None
            self.task_service.create_task(
                title=title,
                task_type=Task.TYPE_LONG_TERM,
                priority="medium",
                tag_ids=[tag_id] if tag_id else None,
            )
        self._refresh_tasks()

    def _on_subtask_status_changed(self, subtask_id: int, new_status: str):
        """分任务状态变化（UI已乐观更新，只持久化）"""
        self.task_service.update_status(subtask_id, new_status)

    def _on_subtask_create(self, parent_id: int, title: str):
        """内联添加分任务"""
        try:
            self.task_service.create_subtask(parent_id, title)
        except ValueError:
            pass
        self._refresh_tasks()

    def _on_subtask_delete(self, subtask_id: int):
        """删除分任务"""
        self.task_service.delete_task(subtask_id)
        self._refresh_tasks()

    def _on_carry_forward(self, task_id: int):
        """将遗留任务移交到今日"""
        self.task_service.carry_forward(task_id)
        self._refresh_tasks()

    def _on_reschedule_weekly(self, task_id: int):
        """重新编辑周计划过期任务的日期"""
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        tags = self.tag_service.get_all_tags()
        dialog = TaskEditorDialog(tags, task=task, parent=self)
        dialog.set_add_tag_callback(self._create_tag_from_editor)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec_():
            data = dialog.get_data()
            self.task_service.update_task(task_id, **data)
            self._refresh_tasks()
            self._refresh_sidebar_tags()

    def _on_task_delete(self, task_id: int):
        """删除任务（自定义确认弹窗）"""
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        if self._show_confirm(f"确定要删除任务「{task.title}」吗？\n删除后可在回收站恢复。"):
            self.task_service.delete_task(task_id)
            self._refresh_tasks()

    def _show_confirm(self, message: str) -> bool:
        """显示自定义主题确认弹窗"""
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setFixedWidth(340)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("ConfirmDialog")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        title = QLabel("⚠ 确认操作")
        title.setObjectName("EditorTitle")
        layout.addWidget(title)

        msg = QLabel(message)
        msg.setObjectName("ConfirmMsg")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("EditorCancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedSize(80, 34)
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("确认")
        ok_btn.setObjectName("EditorSaveBtn")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFixedSize(80, 34)
        ok_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)
        outer.addWidget(container)

        dialog.setStyleSheet(self.styleSheet())
        return dialog.exec_() == QDialog.Accepted

    # ========== 回收站 ==========

    def _on_open_trash(self):
        """打开回收站弹窗"""
        deleted = self.task_service.get_deleted_tasks()

        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setFixedWidth(400)
        dialog.setMinimumHeight(300)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("EditorContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("🗑 回收站")
        title.setObjectName("EditorTitle")
        header.addWidget(title)
        header.addStretch()
        if deleted:
            clear_btn = QPushButton("清空")
            clear_btn.setObjectName("TrashDeleteBtn")
            clear_btn.setCursor(Qt.PointingHandCursor)
            clear_btn.setFixedHeight(24)
            clear_btn.clicked.connect(
                lambda: self._trash_clear_all(dialog)
            )
            header.addWidget(clear_btn)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditorCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 滚动列表
        scroll = QScrollArea()
        scroll.setObjectName("TrashScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(4)
        list_layout.setAlignment(Qt.AlignTop)

        if not deleted:
            empty = QLabel("回收站为空")
            empty.setObjectName("TaskMeta")
            empty.setAlignment(Qt.AlignCenter)
            list_layout.addWidget(empty)
        else:
            for task in deleted:
                item = QFrame()
                item.setObjectName("TrashItem")
                row = QHBoxLayout(item)
                row.setContentsMargins(4, 1, 4, 1)
                row.setSpacing(4)

                text_col = QVBoxLayout()
                text_col.setSpacing(0)
                text_col.setContentsMargins(0, 0, 0, 0)
                lbl = QLabel(task.title)
                lbl.setObjectName("TaskTitle")
                lbl.setWordWrap(False)
                text_col.addWidget(lbl)
                if task.parent_id is not None:
                    parent_task = self.task_service.get_task_any(task.parent_id)
                    if parent_task:
                        parent_lbl = QLabel(f"↑ {parent_task.title}")
                        parent_lbl.setObjectName("TaskMeta")
                        text_col.addWidget(parent_lbl)
                row.addLayout(text_col, 1)

                restore_btn = QPushButton("恢复")
                restore_btn.setObjectName("TrashRestoreBtn")
                restore_btn.setCursor(Qt.PointingHandCursor)
                restore_btn.setFixedHeight(20)
                restore_btn.clicked.connect(
                    lambda checked, tid=task.id, d=dialog: self._trash_restore(tid, d)
                )
                row.addWidget(restore_btn)

                perm_btn = QPushButton("删除")
                perm_btn.setObjectName("TrashDeleteBtn")
                perm_btn.setCursor(Qt.PointingHandCursor)
                perm_btn.setFixedHeight(20)
                perm_btn.clicked.connect(
                    lambda checked, tid=task.id, d=dialog: self._trash_permanent_delete(tid, d)
                )
                row.addWidget(perm_btn)

                list_layout.addWidget(item)

        scroll.setWidget(list_widget)
        layout.addWidget(scroll, 1)

        outer.addWidget(container)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec_()

    # ========== 待办回顾 ==========

    def _on_open_history(self):
        """打开待办回顾弹窗：按日期分组显示过去的今日任务"""
        from datetime import date as _date, timedelta as _td
        grouped = self.task_service.get_history_tasks()
        yesterday = _date.today() - _td(days=1)
        if yesterday not in grouped:
            grouped[yesterday] = []

        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setFixedWidth(400)
        dialog.setMinimumHeight(350)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("EditorContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(6)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("待办回顾")
        title.setObjectName("EditorTitle")
        header.addWidget(title)
        header.addStretch()
        if grouped:
            clear_btn = QPushButton("清空")
            clear_btn.setObjectName("TrashDeleteBtn")
            clear_btn.setCursor(Qt.PointingHandCursor)
            clear_btn.setFixedHeight(24)
            clear_btn.clicked.connect(
                lambda: self._history_clear_all(dialog)
            )
            header.addWidget(clear_btn)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditorCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 滚动列表
        scroll = QScrollArea()
        scroll.setObjectName("TrashScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(2)
        list_layout.setAlignment(Qt.AlignTop)

        if not grouped:
            empty = QLabel("暂无历史记录")
            empty.setObjectName("TaskMeta")
            empty.setAlignment(Qt.AlignCenter)
            list_layout.addWidget(empty)
        else:
            WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for task_date in sorted(grouped.keys(), reverse=True):
                tasks = grouped[task_date]
                wd = WEEKDAYS[task_date.weekday()]
                date_label = QLabel(f"{task_date.strftime('%m月%d日')}  {wd}")
                date_label.setObjectName("HistoryDateLabel")
                list_layout.addWidget(date_label)

                if not tasks:
                    none_label = QLabel("无")
                    none_label.setObjectName("TaskMeta")
                    none_label.setContentsMargins(12, 0, 4, 0)
                    list_layout.addWidget(none_label)
                else:
                    for task in tasks:
                        row = QHBoxLayout()
                        row.setContentsMargins(12, 0, 4, 0)
                        row.setSpacing(4)
                        # 状态标记
                        if task.status in ("done", "cancelled"):
                            mark = QLabel("✓")
                            mark.setObjectName("HistoryDone")
                        else:
                            mark = QLabel("○")
                            mark.setObjectName("HistoryTodo")
                        mark.setFixedWidth(16)
                        row.addWidget(mark)
                        # 标题
                        tlbl = QLabel(task.title)
                        tlbl.setWordWrap(False)
                        if task.status in ("done", "cancelled"):
                            tlbl.setObjectName("HistoryTitleDone")
                        else:
                            tlbl.setObjectName("HistoryTitle")
                        row.addWidget(tlbl, 1)
                        wrapper = QWidget()
                        wrapper.setLayout(row)
                        list_layout.addWidget(wrapper)

        scroll.setWidget(list_widget)
        layout.addWidget(scroll, 1)

        outer.addWidget(container)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec_()

    def _history_clear_all(self, dialog: QDialog):
        """清空待办回顾：永久删除所有过去的短期任务"""
        if self._show_confirm("确定要清空所有待办回顾吗？\n历史任务将被永久删除且无法恢复。"):
            self.task_service.clear_history_tasks()
            dialog.reject()
            self._on_open_history()

    def _trash_restore(self, task_id: int, dialog: QDialog):
        """从回收站恢复任务"""
        self.task_service.restore_task(task_id)
        self._refresh_tasks()
        dialog.reject()
        self._on_open_trash()  # 重新打开以刷新列表

    def _trash_permanent_delete(self, task_id: int, dialog: QDialog):
        """永久删除任务"""
        if self._show_confirm("彻底删除后将无法恢复，确定吗？"):
            self.task_service.permanent_delete_task(task_id)
            dialog.reject()
            self._on_open_trash()

    def _trash_clear_all(self, dialog: QDialog):
        """清空回收站：永久删除所有已删除任务"""
        if self._show_confirm("确定要清空回收站吗？\n所有任务将被永久删除且无法恢复。"):
            deleted = self.task_service.get_deleted_tasks()
            for task in deleted:
                self.task_service.permanent_delete_task(task.id)
            dialog.reject()
            self._on_open_trash()

    def _create_tag_from_editor(self, name: str):
        """在编辑弹窗中创建新标签的回调"""
        try:
            tag = self.tag_service.create_tag(name)
            return tag
        except ValueError:
            return None

    # ========== 标签管理 ==========

    def _on_tag_delete(self, tag_id: int):
        """删除自定义标签"""
        tag = self.tag_service.get_tag(tag_id)
        if tag is None:
            return
        if self._show_confirm(f"确定要删除标签「{tag.name}」吗？"):
            self.tag_service.delete_tag(tag_id)
            self._refresh_sidebar_tags()
            # 如果正在查看被删标签，切回今日
            key = self.sidebar.get_current_key()
            if key == f"tag_{tag_id}":
                self.sidebar._on_click("today")

    def _on_tag_create(self):
        """侧栏右键新建标签"""
        result = self._show_tag_dialog("新建标签", "创建")
        if result:
            name, icon = result
            try:
                self.tag_service.create_tag(name, icon=icon)
                self._refresh_sidebar_tags()
            except ValueError:
                pass

    def _on_tag_edit(self, tag_id: int):
        """侧栏右键编辑标签"""
        tag = self.tag_service.get_tag(tag_id)
        if tag is None:
            return
        result = self._show_tag_dialog(
            "编辑标签", "保存",
            init_name=tag.name,
            init_icon=getattr(tag, 'icon', '★'),
        )
        if result:
            name, icon = result
            try:
                self.tag_service.update_tag(tag_id, name=name)
                # update icon directly
                tag_obj = self.tag_service.get_tag(tag_id)
                if tag_obj:
                    tag_obj.icon = icon
                    self.tag_service._session.commit()
                self._refresh_sidebar_tags()
            except ValueError:
                pass

    def _show_tag_dialog(self, title_text: str, ok_text: str,
                         init_name: str = "", init_icon: str = "★"):
        """显示标签创建/编辑弹窗，返回 (name, icon) 或 None"""
        from PyQt5.QtWidgets import QLineEdit, QGridLayout
        from src.ui.tag_sidebar import TAG_ICONS

        theme = self._current_theme()

        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setFixedWidth(340)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("EditorContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("EditorTitle")
        layout.addWidget(title)

        # 标签名输入
        name_label = QLabel("标签名称")
        name_label.setObjectName("EditorFieldLabel")
        layout.addWidget(name_label)
        name_input = QLineEdit()
        name_input.setObjectName("EditorInput")
        name_input.setPlaceholderText("输入标签名...")
        name_input.setMaxLength(20)
        name_input.setText(init_name)
        layout.addWidget(name_input)

        # 图标选择
        icon_label = QLabel("选择图标")
        icon_label.setObjectName("EditorFieldLabel")
        layout.addWidget(icon_label)

        icon_grid = QWidget()
        grid_layout = QGridLayout(icon_grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(3)

        selected_icon = {"value": init_icon}
        icon_buttons = []
        primary = theme.primary_color
        icon_color = theme.text_secondary
        sel_style = f"border: 2px solid {primary}; border-radius: 6px; color: {primary}; font-size: 15px;"
        norm_style = f"border: 1px solid transparent; border-radius: 6px; color: {icon_color}; font-size: 15px;"

        def on_icon_click(ic, btn):
            selected_icon["value"] = ic
            for b in icon_buttons:
                b.setStyleSheet(norm_style)
            btn.setStyleSheet(sel_style)

        for i, ic in enumerate(TAG_ICONS):
            btn = QPushButton(ic)
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.PointingHandCursor)
            is_sel = (ic == init_icon)
            btn.setStyleSheet(sel_style if is_sel else norm_style)
            btn.clicked.connect(lambda checked, ic=ic, b=btn: on_icon_click(ic, b))
            icon_buttons.append(btn)
            grid_layout.addWidget(btn, i // 8, i % 8)

        layout.addWidget(icon_grid)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("EditorCancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedSize(70, 32)
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_text)
        ok_btn.setObjectName("EditorSaveBtn")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFixedSize(70, 32)
        ok_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)
        outer.addWidget(container)
        dialog.setStyleSheet(self.styleSheet())

        if dialog.exec_() == QDialog.Accepted:
            name = name_input.text().strip()
            if name:
                return (name, selected_icon["value"])
        return None

    def _current_theme(self):
        """获取当前主题对象"""
        from src.ui.styles.themes import get_theme
        theme_key = self.config.get("theme.mode", DEFAULT_THEME_KEY)
        return get_theme(theme_key)

    # ========== 设置面板 ==========

    def _on_open_settings(self):
        """打开设置面板"""
        theme_key = self.config.get("theme.mode", DEFAULT_THEME_KEY)
        opacity = self._bg_opacity
        on_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)

        font_size = self._font_size
        dialog = SettingsPanel(theme_key, opacity, on_top, font_size, parent=self)
        dialog.setStyleSheet(self.styleSheet())

        # 实时预览
        dialog.theme_changed.connect(self._on_settings_theme_changed)
        dialog.opacity_changed.connect(self._on_settings_opacity_changed)
        dialog.always_on_top_changed.connect(self._on_settings_top_changed)
        dialog.font_size_changed.connect(self._on_settings_font_changed)

        dialog.exec_()

    def _on_settings_theme_changed(self, theme_key: str):
        self.switch_theme(theme_key)
        # 同步更新设置面板自身的样式
        sender = self.sender()
        if isinstance(sender, SettingsPanel):
            try:
                sender.setStyleSheet(self.styleSheet())
            except Exception:
                pass

    def _on_settings_opacity_changed(self, opacity: float):
        self.set_bg_opacity(opacity)

    def _on_settings_top_changed(self, on_top: bool):
        self.set_always_on_top(on_top)

    def _on_settings_font_changed(self, size: int):
        self.set_font_size(size)

    def set_always_on_top(self, on_top: bool):
        """切换窗口置顶状态"""
        self._always_on_top = on_top
        flags = self.windowFlags()
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()  # setWindowFlags 后需要重新 show
        self.config.set("window.always_on_top", on_top)
        if hasattr(self, 'pin_btn'):
            self._update_pin_style()

    # ========== 系统托盘 ==========

    def _setup_tray(self):
        self.tray = SystemTray(self)
        self.tray.show_requested.connect(self._tray_show_window)
        self.tray.quit_requested.connect(self._tray_quit)
        self.tray.settings_requested.connect(self._on_open_settings)
        self.tray.add_task_requested.connect(self._on_add_task)
        self.tray.show()

    def _on_minimize(self):
        """最小化到托盘"""
        if self.config.get("behavior.minimize_to_tray", True):
            self.hide()
        else:
            self.showMinimized()

    def _tray_show_window(self):
        """从托盘恢复窗口"""
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        """从托盘退出"""
        self.tray.hide()
        self._save_position()
        self._session.close()
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()

    # ========== 鼠标跟踪 ==========

    def _enable_mouse_tracking(self, widget):
        """递归启用鼠标跟踪，使 MouseMove 事件无需按住按钮也能触发"""
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    # ========== 边缘检测 ==========

    def _detect_edge(self, pos):
        """检测鼠标是否在窗口边缘（返回边名或 None）"""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN
        cm = CORNER_MARGIN

        # 角落用更大的检测区域（16px），便于拖拽对角缩放
        if x < cm and y < cm:
            return "top_left"
        if x > w - cm and y < cm:
            return "top_right"
        if x < cm and y > h - cm:
            return "bottom_left"
        if x > w - cm and y > h - cm:
            return "bottom_right"
        # 边缘用较小的检测区域（6px）
        if x < m:
            return "left"
        if x > w - m:
            return "right"
        if y < m:
            return "top"
        if y > h - m:
            return "bottom"
        return None

    def _edge_cursor(self, edge):
        """根据边缘名返回对应光标"""
        if edge in ("left", "right"):
            return Qt.SizeHorCursor
        if edge in ("top", "bottom"):
            return Qt.SizeVerCursor
        if edge in ("top_left", "bottom_right"):
            return Qt.SizeFDiagCursor
        if edge in ("top_right", "bottom_left"):
            return Qt.SizeBDiagCursor
        return Qt.ArrowCursor

    def _do_resize(self, global_pos):
        """执行窗口缩放"""
        delta = global_pos - self._resize_start_pos
        geo = QRect(self._resize_start_geo)
        edge = self._resize_edge

        if "right" in edge:
            geo.setWidth(max(MIN_WIDTH, geo.width() + delta.x()))
        if "bottom" in edge:
            geo.setHeight(max(MIN_HEIGHT, geo.height() + delta.y()))
        if "left" in edge:
            new_w = max(MIN_WIDTH, geo.width() - delta.x())
            if new_w != geo.width():
                geo.setLeft(geo.right() - new_w)
        if "top" in edge:
            new_h = max(MIN_HEIGHT, geo.height() - delta.y())
            if new_h != geo.height():
                geo.setTop(geo.bottom() - new_h)

        self.setGeometry(geo)

    # ========== 全局事件过滤器（缩放 + 拖拽） ==========

    def eventFilter(self, obj, event):
        # 只处理 QWidget 类型且属于本窗口的事件
        if not isinstance(obj, QWidget):
            return super().eventFilter(obj, event)
        if obj is not self and not self.isAncestorOf(obj):
            return super().eventFilter(obj, event)

        et = event.type()

        # ---------- 鼠标移动 ----------
        if et == QEvent.MouseMove:
            # 正在缩放
            if self._resizing:
                self._do_resize(event.globalPos())
                return True
            # 正在拖拽标题栏
            if self._drag_pos:
                delta = event.globalPos() - self._drag_pos
                self.move(self.pos() + delta)
                self._drag_pos = event.globalPos()
                return True
            # 检测边缘，更新光标
            local = self.mapFromGlobal(event.globalPos())
            edge = self._detect_edge(local)
            if edge:
                self.setCursor(self._edge_cursor(edge))
            else:
                self.unsetCursor()
            return False  # 不吞掉事件，让子控件正常工作

        # ---------- 鼠标按下 ----------
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            local = self.mapFromGlobal(event.globalPos())
            edge = self._detect_edge(local)
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geo = QRect(self.geometry())
                return True  # 吞掉，开始缩放
            # 标题栏拖拽 — 排除按钮点击
            if not isinstance(obj, QPushButton) and local.y() < 48:
                self._drag_pos = event.globalPos()
                return True
            return False

        # ---------- 鼠标释放 ----------
        if et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_edge = None
                self.unsetCursor()
                self._save_position()
                return True
            if self._drag_pos:
                self._drag_pos = None
                self._save_position()
                return True

        return super().eventFilter(obj, event)

    # ========== 位置记忆 ==========

    def _save_position(self):
        geo = self.geometry()
        self.config.set("window.x", geo.x())
        self.config.set("window.y", geo.y())
        self.config.set("window.width", geo.width())
        self.config.set("window.height", geo.height())

    def _load_position(self):
        x = self.config.get("window.x", 100)
        y = self.config.get("window.y", 100)
        self.move(x, y)

    def bring_to_front(self):
        """将窗口从隐藏/最小化/托盘状态恢复并置于前台"""
        import ctypes
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        # 使用 Windows API 强制前台显示（绕过前台窗口限制）
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭窗口时最小化到托盘而不是退出"""
        if hasattr(self, 'tray') and self.tray.is_visible():
            self.hide()
            event.ignore()
        else:
            self._save_position()
            self._session.close()
            event.accept()

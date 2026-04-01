"""任务列表组件 - 可滚动的任务列表容器，支持拖拽排序"""

from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QSizePolicy, QFrame, QMenu, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QPainter, QColor, QCursor

from src.models.task import Task
from src.ui.task_item import TaskItemWidget

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class InlineTaskInput(QWidget):
    """内联快速添加任务输入行"""

    submitted = pyqtSignal(str, object)  # title, due_date (date or None)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "today"
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # 日期下拉（仅本周计划模式可见）
        self.date_combo = QComboBox()
        self.date_combo.setObjectName("InlineDateCombo")
        self.date_combo.setFixedWidth(58)
        self.date_combo.setVisible(False)
        layout.addWidget(self.date_combo)

        # 文本输入
        self.input = QLineEdit()
        self.input.setObjectName("InlineTaskInput")
        self.input.setPlaceholderText("输入内容，回车添加")
        self.input.setAcceptDrops(False)
        self.input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.input)

    def set_mode(self, mode: str):
        """设置输入模式: 'today'/'week'/'long_term'/'tag' 显示输入行；其他隐藏"""
        self._mode = mode
        if mode == "today":
            self.input.setPlaceholderText("输入内容，回车添加")
            self.date_combo.setVisible(False)
            self.setVisible(True)
        elif mode == "week":
            self.input.setPlaceholderText("输入内容，回车添加")
            self.date_combo.setVisible(True)
            self._populate_dates()
            self.setVisible(True)
        elif mode in ("long_term", "tag"):
            self.input.setPlaceholderText("输入内容，回车添加")
            self.date_combo.setVisible(False)
            self.setVisible(True)
        else:
            self.setVisible(False)

    def _populate_dates(self):
        """填充未来10天日期到下拉列表"""
        self.date_combo.clear()
        today = date.today()
        for i in range(10):
            d = today + timedelta(days=i)
            self.date_combo.addItem(f"{d.month}/{d.day}", d)
        self.date_combo.setCurrentIndex(min(1, 9))

    def _on_submit(self):
        title = self.input.text().strip()
        if not title:
            return
        due_date = None
        if self._mode == "week":
            due_date = self.date_combo.currentData()
        self.submitted.emit(title, due_date)
        self.input.clear()


class TaskListWidget(QWidget):
    """任务列表：可滚动容器，内含多个 TaskItemWidget，支持拖拽排序"""

    status_changed = pyqtSignal(int, str)   # task_id, new_status
    edit_requested = pyqtSignal(int)         # task_id
    delete_requested = pyqtSignal(int)       # task_id
    carry_forward_requested = pyqtSignal(int)  # task_id
    reschedule_requested = pyqtSignal(int)     # task_id (周计划过期)
    create_requested = pyqtSignal()          # 右键新建任务
    quick_create = pyqtSignal(str, object)   # title, due_date (内联快速创建)
    subtask_status_changed = pyqtSignal(int, str)    # subtask_id, new_status
    subtask_create_requested = pyqtSignal(int, str)  # parent_id, title
    subtask_delete_requested = pyqtSignal(int)        # subtask_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_widgets = {}  # task_id -> TaskItemWidget
        self._task_order = []    # 有序的 task_id 列表
        self._is_empty = True
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 内联快速添加输入行（固定在顶部，不随列表滚动）
        self.inline_input = InlineTaskInput()
        self.inline_input.submitted.connect(self._on_quick_create)
        self.inline_input.setVisible(False)  # 默认隐藏，由 set_input_mode 控制
        outer_layout.addWidget(self.inline_input)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        # 滚动区域内的容器
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container.setAcceptDrops(True)
        self.container.dragEnterEvent = self._drag_enter
        self.container.dragMoveEvent = self._drag_move
        self.container.dropEvent = self._drop
        self._list_layout = QVBoxLayout(self.container)
        self._list_layout.setContentsMargins(4, 0, 4, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.setAlignment(Qt.AlignTop)

        # 空状态提示
        self.empty_label = QLabel("暂无任务")
        self.empty_label.setObjectName("TaskMeta")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self._list_layout.addWidget(self.empty_label)

        self.scroll_area.setWidget(self.container)
        outer_layout.addWidget(self.scroll_area)

    def set_tasks(self, tasks: list, carryover_ids: set = None,
                  week_overdue_ids: set = None, subtasks_map: dict = None):
        """设置任务列表（全量刷新）"""
        self._carryover_ids = carryover_ids or set()
        self._week_overdue_ids = week_overdue_ids or set()
        subtasks_map = subtasks_map or {}
        self._clear()

        if not tasks:
            self._is_empty = True
            self.empty_label.setVisible(True)
            self._list_layout.addWidget(self.empty_label)
            return

        self._is_empty = False
        self.empty_label.setVisible(False)

        for task in tasks:
            is_carry = task.id in self._carryover_ids
            is_wk_overdue = task.id in self._week_overdue_ids
            subs = subtasks_map.get(task.id, [])
            item = TaskItemWidget(task, subtasks=subs,
                                  is_carryover=is_carry,
                                  is_week_overdue=is_wk_overdue)
            item.status_changed.connect(self._on_status_changed)
            item.edit_requested.connect(self._on_edit_requested)
            item.delete_requested.connect(self._on_delete_requested)
            item.carry_forward_requested.connect(self._on_carry_forward)
            item.reschedule_requested.connect(self._on_reschedule)
            item.subtask_status_changed.connect(self._on_subtask_status_changed)
            item.subtask_create_requested.connect(self._on_subtask_create)
            item.subtask_delete_requested.connect(self._on_subtask_delete)
            self._list_layout.addWidget(item)
            self._task_widgets[task.id] = item
            self._task_order.append(task.id)

    def _clear(self):
        """移除所有任务项"""
        for widget in self._task_widgets.values():
            self._list_layout.removeWidget(widget)
            widget.deleteLater()
        self._task_widgets.clear()
        self._task_order.clear()
        self._list_layout.removeWidget(self.empty_label)

    # ========== 拖拽排序 ==========

    def _drag_enter(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _drag_move(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _drop(self, event):
        if not event.mimeData().hasText():
            return
        try:
            dragged_id = int(event.mimeData().text())
        except ValueError:
            return

        if dragged_id not in self._task_widgets:
            return

        # 找到放置位置
        drop_pos = event.pos()
        target_index = len(self._task_order)
        for i, tid in enumerate(self._task_order):
            w = self._task_widgets.get(tid)
            if w and drop_pos.y() < w.pos().y() + w.height() // 2:
                target_index = i
                break

        # 重新排列
        if dragged_id in self._task_order:
            old_index = self._task_order.index(dragged_id)
            self._task_order.pop(old_index)
            if target_index > old_index:
                target_index -= 1
            self._task_order.insert(target_index, dragged_id)

        # 重新布局
        for tid in self._task_order:
            w = self._task_widgets.get(tid)
            if w:
                self._list_layout.removeWidget(w)
        for tid in self._task_order:
            w = self._task_widgets.get(tid)
            if w:
                self._list_layout.addWidget(w)

        event.acceptProposedAction()

    # ========== 信号转发 ==========

    def _on_status_changed(self, task_id, new_status):
        self.status_changed.emit(task_id, new_status)

    def _on_edit_requested(self, task_id):
        self.edit_requested.emit(task_id)

    def _on_delete_requested(self, task_id):
        self.delete_requested.emit(task_id)

    def _on_carry_forward(self, task_id):
        self.carry_forward_requested.emit(task_id)

    def _on_reschedule(self, task_id):
        self.reschedule_requested.emit(task_id)

    def _on_subtask_status_changed(self, subtask_id, new_status):
        self.subtask_status_changed.emit(subtask_id, new_status)

    def _on_subtask_create(self, parent_id, title):
        self.subtask_create_requested.emit(parent_id, title)

    def _on_subtask_delete(self, subtask_id):
        self.subtask_delete_requested.emit(subtask_id)

    def _on_quick_create(self, title: str, due_date):
        self.quick_create.emit(title, due_date)

    def set_input_mode(self, mode: str):
        """设置内联输入行模式: 'today'/'week' 显示，其他隐藏"""
        self.inline_input.set_mode(mode)

    def get_task_count(self):
        return len(self._task_widgets)

    def is_empty(self):
        return self._is_empty

    def contextMenuEvent(self, event):
        """右键空白处新建任务"""
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(self.window().styleSheet())
        add_action = menu.addAction("➕ 新建任务")
        add_action.triggered.connect(lambda: self.create_requested.emit())
        menu.exec_(QCursor.pos())

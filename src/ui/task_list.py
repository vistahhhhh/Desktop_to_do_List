"""任务列表组件 - 可滚动的任务列表容器，支持拖拽排序"""

from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QSizePolicy, QFrame, QMenu, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt, QPoint, QVariant
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
    batch_delete_requested = pyqtSignal(list)  # [task_id, ...]
    carry_forward_requested = pyqtSignal(int)  # task_id
    reschedule_requested = pyqtSignal(int)     # task_id (周计划过期)
    create_requested = pyqtSignal()          # 右键新建任务
    quick_create = pyqtSignal(str, object)   # title, due_date (内联快速创建)
    subtask_status_changed = pyqtSignal(int, str)    # subtask_id, new_status
    subtask_create_requested = pyqtSignal(int, str)  # parent_id, title
    subtask_delete_requested = pyqtSignal(int)        # subtask_id
    subtask_title_changed = pyqtSignal(int, str)      # subtask_id, new_title
    create_linked_note_requested = pyqtSignal(int)    # task_id
    link_existing_note_requested = pyqtSignal(int)    # task_id
    view_linked_notes_requested = pyqtSignal(int)     # task_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_widgets = {}  # task_id -> TaskItemWidget
        self._task_order = []    # 有序的 task_id 列表
        self._is_empty = True
        self._selected_task_ids = set()    # 多选
        self._last_clicked_task_id = None  # Shift范围选用
        self._setup_ui()
        self.setFocusPolicy(Qt.StrongFocus)

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

        # 点击空白处取消选中
        self.container.mousePressEvent = self._on_container_click
        self.scroll_area.viewport().mousePressEvent = self._on_container_click

    def set_tasks(self, tasks: list, carryover_ids: set = None,
                  week_overdue_ids: set = None, subtasks_map: dict = None,
                  link_count_map: dict = None):
        """设置任务列表（全量刷新）"""
        self._carryover_ids = carryover_ids or set()
        self._week_overdue_ids = week_overdue_ids or set()
        subtasks_map = subtasks_map or {}
        link_count_map = link_count_map or {}
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
            link_count = int(link_count_map.get(task.id, 0) or 0)
            item = TaskItemWidget(task, subtasks=subs,
                                  is_carryover=is_carry,
                                  is_week_overdue=is_wk_overdue,
                                  link_count=link_count)
            item.status_changed.connect(self._on_status_changed)
            item.edit_requested.connect(self._on_edit_requested)
            item.delete_requested.connect(self._on_delete_requested)
            item.carry_forward_requested.connect(self._on_carry_forward)
            item.reschedule_requested.connect(self._on_reschedule)
            item.subtask_status_changed.connect(self._on_subtask_status_changed)
            item.subtask_create_requested.connect(self._on_subtask_create)
            item.subtask_delete_requested.connect(self._on_subtask_delete)
            item.subtask_title_changed.connect(self._on_subtask_title_changed)
            item.create_linked_note_requested.connect(self._on_create_linked_note)
            item.link_existing_note_requested.connect(self._on_link_existing_note)
            item.view_linked_notes_requested.connect(self._on_view_linked_notes)
            item.installEventFilter(self)
            for child in item.findChildren(QWidget):
                child.installEventFilter(self)
            self._list_layout.addWidget(item)
            self._task_widgets[task.id] = item
            self._task_order.append(task.id)

    def _clear(self):
        """移除所有任务项"""
        self._selected_task_ids.clear()
        self._last_clicked_task_id = None
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

    def _on_subtask_title_changed(self, subtask_id, new_title):
        self.subtask_title_changed.emit(subtask_id, new_title)

    def _on_create_linked_note(self, task_id):
        self.create_linked_note_requested.emit(task_id)

    def _on_link_existing_note(self, task_id):
        self.link_existing_note_requested.emit(task_id)

    def _on_view_linked_notes(self, task_id):
        self.view_linked_notes_requested.emit(task_id)

    def _on_quick_create(self, title: str, due_date):
        self.quick_create.emit(title, due_date)

    def set_input_mode(self, mode: str):
        """设置内联输入行模式: 'today'/'week' 显示，其他隐藏"""
        self.inline_input.set_mode(mode)

    def get_task_count(self):
        return len(self._task_widgets)

    def is_empty(self):
        return self._is_empty

    def update_task_link_count(self, task_id: int, count: int):
        """仅更新指定任务的关联便签徽标，不刷新整个列表"""
        widget = self._task_widgets.get(task_id)
        if widget:
            widget.set_link_count(count)

    def get_all_task_ids(self) -> list:
        """返回当前列表中所有任务 ID"""
        return list(self._task_widgets.keys())

    def _on_container_click(self, event):
        """点击列表空白处取消选中"""
        self._deselect_all()

    # ========== 多选 / Delete键 / 右键删除 ==========

    def _update_row_selection(self):
        """根据 _selected_task_ids 刷新所有行的选中样式"""
        for tid, w in self._task_widgets.items():
            val = "true" if tid in self._selected_task_ids else "false"
            w.setProperty("selected", val)
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()

    def _on_task_click(self, task_id, modifiers):
        if modifiers & Qt.ControlModifier:
            # Ctrl+点击：切换选中
            if task_id in self._selected_task_ids:
                self._selected_task_ids.discard(task_id)
            else:
                self._selected_task_ids.add(task_id)
            self._last_clicked_task_id = task_id
        elif modifiers & Qt.ShiftModifier:
            # Shift+点击：范围选中
            if self._last_clicked_task_id is not None and self._last_clicked_task_id in self._task_order:
                idx_a = self._task_order.index(self._last_clicked_task_id)
                idx_b = self._task_order.index(task_id) if task_id in self._task_order else idx_a
                lo, hi = min(idx_a, idx_b), max(idx_a, idx_b)
                self._selected_task_ids = set(self._task_order[lo:hi + 1])
            else:
                self._selected_task_ids = {task_id}
                self._last_clicked_task_id = task_id
        else:
            # 普通单击：单选
            self._selected_task_ids = {task_id}
            self._last_clicked_task_id = task_id
        self._update_row_selection()
        self.setFocus()

    def _deselect_all(self):
        if self._selected_task_ids:
            self._selected_task_ids.clear()
            self._last_clicked_task_id = None
            self._update_row_selection()

    def eventFilter(self, obj, event):
        if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
            # 向上查找是否属于某个 TaskItemWidget
            w = obj
            task_item = None
            while w is not None:
                if isinstance(w, TaskItemWidget):
                    task_item = w
                    break
                w = w.parentWidget()
            if task_item is not None:
                from PyQt5.QtWidgets import QApplication
                self._on_task_click(task_item.task.id, QApplication.keyboardModifiers())
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self._selected_task_ids:
            ids = list(self._selected_task_ids)
            if len(ids) == 1:
                self.delete_requested.emit(ids[0])
            else:
                self.batch_delete_requested.emit(ids)
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(self.window().styleSheet())
        menu.setStyleSheet(
            menu.styleSheet() +
            "\nQMenu::item { padding: 2px 10px; min-height: 16px; }"
        )
        if len(self._selected_task_ids) > 1:
            # 多选时只显示删除选项
            count = len(self._selected_task_ids)
            del_action = menu.addAction(f"删除选中 ({count})")
            ids = list(self._selected_task_ids)
            del_action.triggered.connect(lambda _, _ids=ids: self.batch_delete_requested.emit(_ids))
        else:
            add_action = menu.addAction("新建任务")
            add_action.triggered.connect(lambda: self.create_requested.emit())
        menu.exec_(QCursor.pos())

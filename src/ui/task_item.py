"""任务项组件 - 显示单个任务，支持状态切换和分任务"""

from datetime import date

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget,
    QMenu, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import pyqtSignal, Qt, QMimeData
from PyQt5.QtGui import QCursor, QDrag, QPixmap, QPainter

from src.models.task import Task


# 状态流转映射：点击按钮直接切换 todo⇄done
STATUS_FLOW = {
    "todo": "done",
    "in_progress": "done",
    "done": "todo",
    "cancelled": "todo",
}

# 优先级显示
PRIORITY_LABELS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 全局折叠状态缓存：task_id -> bool (True=展开)，跨刷新保持用户最后操作状态
_SUBTASK_EXPAND_STATE: dict = {}


# ============================================================
# 带 Escape 的内联输入框
# ============================================================

class _InlineSubtaskInput(QLineEdit):
    """带 Escape 取消的内联输入框"""
    cancelled = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)


# ============================================================
# 分任务单项
# ============================================================

class SubtaskItemWidget(QWidget):
    """单个分任务行：缩进 + 小复选框 + 标题 + ＋按钮（仅最后一条显示）"""

    status_changed = pyqtSignal(int, str)    # subtask_id, new_status
    delete_requested = pyqtSignal(int)        # subtask_id
    add_after_requested = pyqtSignal(int)     # subtask_id：在该行后插入输入框

    def __init__(self, subtask: Task, parent=None):
        super().__init__(parent)
        self.subtask = subtask
        self.setObjectName("SubtaskItem")
        self._drag_start = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 1, 4, 1)
        layout.setSpacing(5)

        self.check_btn = QPushButton()
        self.check_btn.setFixedSize(13, 13)
        self.check_btn.setCursor(Qt.PointingHandCursor)
        self.check_btn.clicked.connect(self._toggle_status)
        self._update_check_style()
        layout.addWidget(self.check_btn, 0, Qt.AlignVCenter)

        self.title_label = QLabel(self.subtask.title)
        self.title_label.setWordWrap(False)
        self._update_title_style()
        layout.addWidget(self.title_label, 1)

        self.add_btn = QPushButton("＋")
        self.add_btn.setObjectName("SubtaskAddBtn")
        self.add_btn.setFixedSize(16, 16)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setVisible(False)
        self.add_btn.clicked.connect(
            lambda: self.add_after_requested.emit(self.subtask.id))
        layout.addWidget(self.add_btn, 0, Qt.AlignVCenter)

    def set_add_btn_visible(self, visible: bool):
        self.add_btn.setVisible(visible)

    def _update_check_style(self):
        if self.subtask.status in ("done", "cancelled"):
            self.check_btn.setObjectName("SubtaskCheckDone")
            self.check_btn.setText("✓")
        else:
            self.check_btn.setObjectName("SubtaskCheck")
            self.check_btn.setText("")
        self.check_btn.style().unpolish(self.check_btn)
        self.check_btn.style().polish(self.check_btn)

    def _update_title_style(self):
        if self.subtask.status in ("done", "cancelled"):
            self.title_label.setObjectName("SubtaskTitleDone")
        else:
            self.title_label.setObjectName("SubtaskTitle")
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)

    def _toggle_status(self):
        new_status = "done" if self.subtask.status != "done" else "todo"
        self.subtask.status = new_status
        self._update_check_style()
        self._update_title_style()
        self.status_changed.emit(self.subtask.id, new_status)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setWindowFlags(
            menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        try:
            menu.setStyleSheet(self.window().styleSheet())
        except Exception:
            pass
        del_action = menu.addAction("🗑️ 删除分任务")
        del_action.triggered.connect(
            lambda: self.delete_requested.emit(self.subtask.id))
        menu.exec_(QCursor.pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_start is not None and
                (event.pos() - self._drag_start).manhattanLength() > 10):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(f"subtask:{self.subtask.id}")
            drag.setMimeData(mime)
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setOpacity(0.6)
            self.render(painter)
            painter.end()
            drag.setPixmap(pixmap)
            drag.setHotSpot(self._drag_start)
            drag.exec_(Qt.MoveAction)
            self._drag_start = None
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        super().mouseReleaseEvent(event)


# ============================================================
# 分任务区块（列表 + 按需内联输入）
# ============================================================

class SubtaskSection(QWidget):
    """分任务区块：分任务列表 + 按需弹出内联输入框"""

    subtask_status_changed = pyqtSignal(int, str)    # subtask_id, new_status
    subtask_create_requested = pyqtSignal(int, str)  # parent_task_id, title
    subtask_delete_requested = pyqtSignal(int)        # subtask_id

    def __init__(self, parent_task_id: int, subtasks: list, parent=None):
        super().__init__(parent)
        self._parent_task_id = parent_task_id
        self._subtasks = subtasks
        self._item_widgets: list = []
        self._inline_wrapper = None
        self._inline_input: _InlineSubtaskInput = None
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(0)

        for subtask in self._subtasks:
            item = self._make_item(subtask)
            self._item_widgets.append(item)
            layout.addWidget(item)

        self._update_add_btn_visibility()

    def _make_item(self, subtask: Task) -> SubtaskItemWidget:
        item = SubtaskItemWidget(subtask)
        item.status_changed.connect(self.subtask_status_changed)
        item.delete_requested.connect(self.subtask_delete_requested)
        item.add_after_requested.connect(self._show_input_after)
        return item

    def _update_add_btn_visibility(self):
        """仅最后一条分任务显示 ＋ 按钮"""
        for i, w in enumerate(self._item_widgets):
            w.set_add_btn_visible(i == len(self._item_widgets) - 1)

    # ---- 拖拽排序 ----

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("subtask:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("subtask:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        text = event.mimeData().text()
        if not text.startswith("subtask:"):
            return
        try:
            subtask_id = int(text.split(":")[1])
        except (ValueError, IndexError):
            return

        dragged_widget = None
        dragged_index = -1
        for i, w in enumerate(self._item_widgets):
            if w.subtask.id == subtask_id:
                dragged_widget = w
                dragged_index = i
                break
        if dragged_widget is None:
            return

        self._remove_inline_input()

        drop_pos = event.pos()
        target_index = len(self._item_widgets)
        for i, w in enumerate(self._item_widgets):
            if drop_pos.y() < w.pos().y() + w.height() // 2:
                target_index = i
                break

        self._item_widgets.pop(dragged_index)
        if target_index > dragged_index:
            target_index -= 1
        self._item_widgets.insert(target_index, dragged_widget)

        for w in self._item_widgets:
            self.layout().removeWidget(w)
        for w in self._item_widgets:
            self.layout().addWidget(w)

        self._update_add_btn_visibility()
        event.acceptProposedAction()

    def _show_input_after(self, after_subtask_id: int):
        """点击某分任务的"＋"按钮：在该行后方插入输入框"""
        self._remove_inline_input()
        insert_pos = len(self._item_widgets)
        for i, w in enumerate(self._item_widgets):
            if w.subtask.id == after_subtask_id:
                insert_pos = i + 1
                break
        self._create_inline_input(insert_pos)

    def _create_inline_input(self, pos: int):
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(20, 1, 4, 1)
        row.setSpacing(0)

        inp = _InlineSubtaskInput()
        inp.setObjectName("SubtaskInput")
        inp.setPlaceholderText("添加分任务…")
        inp.returnPressed.connect(lambda: self._confirm_input(inp))
        inp.cancelled.connect(self._remove_inline_input)
        row.addWidget(inp)

        self._inline_wrapper = wrapper
        self._inline_input = inp
        self.layout().insertWidget(pos, wrapper)
        inp.setFocus()

    def _confirm_input(self, inp: _InlineSubtaskInput):
        title = inp.text().strip()
        self._remove_inline_input()
        if title:
            self.subtask_create_requested.emit(self._parent_task_id, title)

    def _remove_inline_input(self):
        if self._inline_wrapper is not None:
            self.layout().removeWidget(self._inline_wrapper)
            self._inline_wrapper.deleteLater()
            self._inline_wrapper = None
            self._inline_input = None

    def focus_input(self):
        """外部触发（右键"添加分任务"），在列表末尾显示输入框"""
        self._remove_inline_input()
        self._create_inline_input(len(self._item_widgets))


# ============================================================
# 主任务项
# ============================================================

class TaskItemWidget(QFrame):
    """单个任务项（含可折叠分任务区块）"""

    status_changed = pyqtSignal(int, str)
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    carry_forward_requested = pyqtSignal(int)
    reschedule_requested = pyqtSignal(int)
    subtask_status_changed = pyqtSignal(int, str)    # subtask_id, new_status
    subtask_create_requested = pyqtSignal(int, str)  # parent_id, title
    subtask_delete_requested = pyqtSignal(int)        # subtask_id

    def __init__(self, task: Task, subtasks: list = None,
                 is_carryover: bool = False, is_week_overdue: bool = False,
                 parent=None):
        super().__init__(parent)
        self.task = task
        self._subtasks = subtasks or []
        self._is_carryover = is_carryover
        self._is_week_overdue = is_week_overdue
        self._subtask_section = None
        self._toggle_btn: QPushButton = None
        self._subtasks_expanded = _SUBTASK_EXPAND_STATE.get(task.id, True)
        self.setObjectName("TaskCard")
        self.setCursor(Qt.PointingHandCursor)
        self._drag_start = None
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- 主任务行 ----
        main_row = QWidget()
        layout = QHBoxLayout(main_row)
        layout.setContentsMargins(2, 2, 4, 2)
        layout.setSpacing(4)

        if self._is_carryover:
            self.status_btn = None
            self.title_label = QLabel(self.task.title)
            self.title_label.setWordWrap(True)
            self.title_label.setObjectName("TaskTitleCarryover")
            layout.addWidget(self.title_label, 1)

            carry_btn = QPushButton("移交今日")
            carry_btn.setObjectName("CarryForwardBtn")
            carry_btn.setCursor(Qt.PointingHandCursor)
            carry_btn.setFixedHeight(20)
            carry_btn.clicked.connect(
                lambda: self.carry_forward_requested.emit(self.task.id))
            layout.addWidget(carry_btn, 0)

        elif self._is_week_overdue:
            self.status_btn = None
            self.title_label = QLabel(self.task.title)
            self.title_label.setWordWrap(True)
            self.title_label.setObjectName("TaskTitleCarryover")
            layout.addWidget(self.title_label, 1)

            resched_btn = QPushButton("重新编辑日期")
            resched_btn.setObjectName("CarryForwardBtn")
            resched_btn.setCursor(Qt.PointingHandCursor)
            resched_btn.setFixedHeight(20)
            resched_btn.clicked.connect(
                lambda: self.reschedule_requested.emit(self.task.id))
            layout.addWidget(resched_btn, 0)

        else:
            self.status_btn = QPushButton()
            self.status_btn.setFixedSize(16, 16)
            self.status_btn.setCursor(Qt.PointingHandCursor)
            self.status_btn.clicked.connect(self._toggle_status)
            self._update_status_style()
            layout.addWidget(self.status_btn, 0, Qt.AlignVCenter)

            self.title_label = QLabel(self.task.title)
            self.title_label.setWordWrap(True)
            self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self._update_title_style()
            layout.addWidget(self.title_label, 1)

            # 折叠/展开切换按钮（有分任务时才显示，兼作进度提示）
            if self._subtasks:
                self._toggle_btn = QPushButton(self._progress_text())
                self._toggle_btn.setObjectName("SubtaskToggle")
                self._toggle_btn.setCursor(Qt.PointingHandCursor)
                self._toggle_btn.setFlat(True)
                self._toggle_btn.clicked.connect(self._toggle_subtask_section)
                layout.addWidget(self._toggle_btn, 0, Qt.AlignTop)

            self.date_label = QLabel("")
            self.date_label.setObjectName("TaskMeta")
            self.date_label.setWordWrap(False)
            self._update_date_label()
            layout.addWidget(self.date_label, 0, Qt.AlignTop)

            priority_text = PRIORITY_LABELS.get(self.task.priority, "")
            if priority_text:
                priority_label = QLabel(priority_text)
                obj_name = {
                    "high": "PriorityHigh",
                    "medium": "PriorityMedium",
                    "low": "PriorityLow",
                }.get(self.task.priority, "PriorityMedium")
                priority_label.setObjectName(obj_name)
                layout.addWidget(priority_label, 0, Qt.AlignTop)

        desc = getattr(self.task, 'description', None)
        if desc and desc.strip():
            preview = desc.strip()[:20]
            if len(desc.strip()) > 20:
                preview += "…"
            self.setToolTip(preview)

        outer.addWidget(main_row)

        # ---- 分任务区块 ----
        if self._subtasks:
            self._build_subtask_section()

    # ---- 进度 / 折叠 ----

    def _progress_text(self, expanded=None) -> str:
        if expanded is None:
            expanded = self._subtasks_expanded
        done = sum(1 for s in self._subtasks if s.status in ("done", "cancelled"))
        total = len(self._subtasks)
        arrow = "▼" if expanded else "▶"
        return f"{arrow} {done}/{total}"

    def _toggle_subtask_section(self):
        self._subtasks_expanded = not self._subtasks_expanded
        _SUBTASK_EXPAND_STATE[self.task.id] = self._subtasks_expanded
        if self._subtask_section:
            self._subtask_section.setVisible(self._subtasks_expanded)
        if self._toggle_btn:
            self._toggle_btn.setText(self._progress_text())

    def _update_progress(self):
        if self._toggle_btn:
            self._toggle_btn.setText(self._progress_text())

    def _on_subtask_status_for_progress(self, subtask_id: int, new_status: str):
        """分任务状态变化时：更新进度标签 + 向上转发信号"""
        for sub in self._subtasks:
            if sub.id == subtask_id:
                sub.status = new_status
                break
        self._update_progress()
        self.subtask_status_changed.emit(subtask_id, new_status)

    def _build_subtask_section(self):
        self._subtask_section = SubtaskSection(self.task.id, self._subtasks)
        self._subtask_section.subtask_status_changed.connect(
            self._on_subtask_status_for_progress)
        self._subtask_section.subtask_create_requested.connect(
            self.subtask_create_requested)
        self._subtask_section.subtask_delete_requested.connect(
            self.subtask_delete_requested)
        self.layout().addWidget(self._subtask_section)
        if not self._subtasks_expanded:
            self._subtask_section.setVisible(False)

    def _show_subtask_input(self):
        """右键"添加分任务"：展开区块并聚焦输入框"""
        if self._subtask_section is None:
            self._subtask_section = SubtaskSection(self.task.id, [])
            self._subtask_section.subtask_status_changed.connect(
                self._on_subtask_status_for_progress)
            self._subtask_section.subtask_create_requested.connect(
                self.subtask_create_requested)
            self._subtask_section.subtask_delete_requested.connect(
                self.subtask_delete_requested)
            self.layout().addWidget(self._subtask_section)
        self._subtask_section.setVisible(True)
        self._subtasks_expanded = True
        if self._toggle_btn:
            self._toggle_btn.setText(self._progress_text())
        self._subtask_section.focus_input()

    # ---- 日期 / 状态 / 样式 ----

    def _update_date_label(self):
        if not self.task.due_date:
            self.date_label.setText("")
            self.date_label.setObjectName("TaskMeta")
            return

        today = date.today()
        d = self.task.due_date

        if self.task.task_type == Task.TYPE_WEEKLY:
            wd = d.weekday()
            wd_name = WEEKDAY_NAMES[wd] if wd < len(WEEKDAY_NAMES) else ""
            text = f"{wd_name} {d.month}/{d.day}"
        elif d.day == 1 and self.task.task_type == Task.TYPE_LONG_TERM:
            text = d.strftime("%Y-%m")
        else:
            text = f"{d.month}/{d.day}"

        is_overdue = (self.task.task_type == Task.TYPE_LONG_TERM
                      and d < today
                      and self.task.status not in ("done", "cancelled"))
        if is_overdue:
            self.date_label.setText(f"⚠ {text}")
            self.date_label.setObjectName("TaskMetaOverdue")
        else:
            self.date_label.setText(text)
            self.date_label.setObjectName("TaskMeta")

        self.date_label.style().unpolish(self.date_label)
        self.date_label.style().polish(self.date_label)

    def _update_status_style(self):
        status = self.task.status
        if status == "done":
            self.status_btn.setObjectName("StatusCircleDone")
            self.status_btn.setText("✓")
        elif status == "in_progress":
            self.status_btn.setObjectName("StatusCircleProgress")
            self.status_btn.setText("◐")
        elif status == "cancelled":
            self.status_btn.setObjectName("StatusCircleDone")
            self.status_btn.setText("✕")
        else:
            self.status_btn.setObjectName("StatusCircle")
            self.status_btn.setText("")
        self.status_btn.setStyleSheet(self.status_btn.styleSheet())

    def _update_title_style(self):
        if self.task.status in ("done", "cancelled"):
            self.title_label.setObjectName("TaskTitleDone")
        else:
            self.title_label.setObjectName("TaskTitle")

    def _toggle_status(self):
        new_status = STATUS_FLOW.get(self.task.status, "todo")
        self.task.status = new_status
        self._update_status_style()
        self._update_title_style()
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self._update_date_label()
        self.status_changed.emit(self.task.id, new_status)

    # ---- 鼠标事件 ----

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.task.id)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start and (event.pos() - self._drag_start).manhattanLength() > 20:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.task.id))
            drag.setMimeData(mime)

            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setOpacity(0.6)
            self.render(painter)
            painter.end()
            drag.setPixmap(pixmap)
            drag.setHotSpot(self._drag_start)

            drag.exec_(Qt.MoveAction)
            self._drag_start = None
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单：编辑、添加分任务、删除"""
        menu = QMenu(self)
        menu.setWindowFlags(
            menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(self.window().styleSheet())

        edit_action = menu.addAction("✏️ 编辑任务")
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.task.id))

        add_sub_action = menu.addAction("➕ 添加分任务")
        add_sub_action.triggered.connect(self._show_subtask_input)

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ 删除任务")
        delete_action.triggered.connect(
            lambda: self.delete_requested.emit(self.task.id))

        menu.exec_(QCursor.pos())

    def _set_status(self, new_status: str):
        self.task.status = new_status
        self._update_status_style()
        self._update_title_style()
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self._update_date_label()
        self.status_changed.emit(self.task.id, new_status)

    def update_task(self, task: Task):
        """更新任务数据并刷新显示"""
        self.task = task
        self.title_label.setText(task.title)
        self._update_status_style()
        self._update_title_style()
        self._update_date_label()
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)

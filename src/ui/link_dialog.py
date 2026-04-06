"""任务-便签关联弹窗"""

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRectF
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QWidget,
    QFrame,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPen, QIcon


def make_link_pixmap(size=16, color="#999999"):
    """绘制一个简单的链接图标（两个交叉的链环）"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    lw = max(1.4, size * 0.11)
    pen = QPen(QColor(color), lw)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.translate(size / 2, size / 2)
    p.rotate(45)
    w = size * 0.24
    h = size * 0.52
    gap = size * 0.03
    p.drawRoundedRect(QRectF(-w - gap, -h / 2, w, h), w / 2, w / 2)
    p.drawRoundedRect(QRectF(gap, -h / 2, w, h), w / 2, w / 2)
    p.end()
    return pixmap


class LinkExistingNotesDialog(QDialog):
    """任务侧：选择已有便签并建立关联"""

    def __init__(self, task_title: str, all_notes: list, parent=None):
        super().__init__(parent)
        self._all_notes = all_notes
        self._selected_id = None
        self._drag_pos = None
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("关联已有便签")
        self.setMinimumSize(360, 280)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self._container = QFrame()
        self._container.setObjectName("LinkDialog")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self._container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 标题行（可拖动）
        self._title_bar = QWidget()
        title_row = QHBoxLayout(self._title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"关联到任务：{task_title}")
        title.setObjectName("LinkDialogTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("LinkCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        title_row.addWidget(close_btn)
        self._title_bar.mousePressEvent = self._tb_press
        self._title_bar.mouseMoveEvent = self._tb_move
        self._title_bar.mouseReleaseEvent = self._tb_release
        root.addWidget(self._title_bar)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索便签...")
        self.search.textChanged.connect(self._refresh_list)
        root.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("LinkListWidget")
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        root.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("LinkGhostBtn")
        cancel_btn.setFixedHeight(26)
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("确认关联")
        ok_btn.setObjectName("LinkPrimaryBtn")
        ok_btn.setFixedHeight(26)
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

        outer.addWidget(self._container)
        self._refresh_list()

    # ---- 标题栏拖动 ----
    def _tb_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
    def _tb_move(self, event):
        if self._drag_pos:
            self.move(self.pos() + event.globalPos() - self._drag_pos)
            self._drag_pos = event.globalPos()
    def _tb_release(self, event):
        self._drag_pos = None

    def _refresh_list(self):
        q = self.search.text().strip().lower()
        self.list_widget.clear()
        for note in self._all_notes:
            title = note.display_name()
            if q and q not in title.lower():
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, note.id)
            self.list_widget.addItem(item)

    def _on_accept(self):
        item = self.list_widget.currentItem()
        self._selected_id = item.data(Qt.UserRole) if item is not None else None
        self.accept()

    def selected_note_id(self) -> int | None:
        return self._selected_id


class NoteLinkedTasksDialog(QDialog):
    """便签侧：查看/解除已关联任务"""

    jump_task_requested = pyqtSignal(int)
    note_unlinked = pyqtSignal(int)  # note_id
    note_linked = pyqtSignal(int, int)  # note_id, task_id

    def __init__(self, note_id: int, link_service, all_tasks: list | None = None, parent=None):
        super().__init__(parent)
        self._note_id = note_id
        self._link_service = link_service
        self._all_tasks = all_tasks or []
        self._drag_pos = None
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setWindowTitle("关联任务")
        self.setMinimumSize(380, 300)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self._container = QFrame()
        self._container.setObjectName("LinkDialog")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self._container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 标题行：左侧标题 + 右侧 X 关闭（可拖动）
        self._title_bar = QWidget()
        title_row = QHBoxLayout(self._title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("已关联任务")
        title.setObjectName("LinkDialogTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("LinkCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        title_row.addWidget(close_btn)
        self._title_bar.mousePressEvent = self._tb_press
        self._title_bar.mouseMoveEvent = self._tb_move
        self._title_bar.mouseReleaseEvent = self._tb_release
        root.addWidget(self._title_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(32)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(6)
        self.body_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll)

        section_lbl = QLabel("可关联任务")
        section_lbl.setObjectName("LinkDialogTitle")
        root.addWidget(section_lbl)
        self.add_search = QLineEdit()
        self.add_search.setPlaceholderText("搜索任务并关联...")
        self.add_search.textChanged.connect(self._refresh_candidates)
        root.addWidget(self.add_search)

        self.candidate_list = QListWidget()
        self.candidate_list.setObjectName("LinkListWidget")
        self.candidate_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.candidate_list.setMaximumHeight(96)
        root.addWidget(self.candidate_list)

        add_btn = QPushButton("关联选中任务")
        add_btn.setObjectName("LinkPrimaryBtn")
        add_btn.setFixedHeight(26)
        add_btn.clicked.connect(self._link_selected_task)
        root.addWidget(add_btn, 0, Qt.AlignLeft)

        outer.addWidget(self._container)
        self._refresh_rows()
        self._refresh_candidates()

    # ---- 标题栏拖动 ----
    def _tb_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
    def _tb_move(self, event):
        if self._drag_pos:
            self.move(self.pos() + event.globalPos() - self._drag_pos)
            self._drag_pos = event.globalPos()
    def _tb_release(self, event):
        self._drag_pos = None

    def _clear_rows(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_rows(self):
        self._clear_rows()
        task = self._link_service.get_task_for_note(self._note_id)

        shown = 0
        if task is not None:
            row = QFrame()
            row.setObjectName("LinkRowCard")
            hl = QHBoxLayout(row)
            hl.setContentsMargins(8, 3, 8, 3)
            hl.setSpacing(6)

            lbl = QLabel(task.title)
            hl.addWidget(lbl, 1)

            jump_btn = QPushButton("跳转")
            jump_btn.setObjectName("LinkGhostBtn")
            jump_btn.setFixedSize(44, 22)
            jump_btn.clicked.connect(lambda _, tid=task.id: self._on_jump(tid))
            hl.addWidget(jump_btn)

            unlink_btn = QPushButton("解除")
            unlink_btn.setObjectName("LinkGhostBtn")
            unlink_btn.setFixedSize(44, 22)
            unlink_btn.clicked.connect(lambda _, tid=task.id: self._unlink_task(tid))
            hl.addWidget(unlink_btn)

            self.body_layout.addWidget(row)
            shown += 1

        if shown == 0:
            empty = QLabel("暂无关联任务")
            empty.setObjectName("TaskMeta")
            empty.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            empty.setFixedHeight(26)
            self.body_layout.addWidget(empty)

    def _on_jump(self, task_id: int):
        self.jump_task_requested.emit(task_id)
        self.accept()

    def _unlink_task(self, task_id: int):
        win = self.parent()
        if hasattr(win, "_show_confirm"):
            if not win._show_confirm("确定要解除与该任务的关联吗？"):
                return
        self._link_service.unlink(task_id, self._note_id)
        self.note_unlinked.emit(self._note_id)
        self._refresh_rows()
        self._refresh_candidates()

    def _refresh_candidates(self):
        query = self.add_search.text().strip().lower()
        linked_task = self._link_service.get_task_for_note(self._note_id)
        linked_ids = {linked_task.id} if linked_task is not None else set()
        self.candidate_list.clear()

        for task in self._all_tasks:
            if task.id in linked_ids:
                continue
            if getattr(task, 'is_deleted', 0) == 1:
                continue
            title = task.title or ""
            if query and query not in title.lower():
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, task.id)
            self.candidate_list.addItem(item)

    def _link_selected_task(self):
        item = self.candidate_list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.UserRole)
        win = self.parent()
        replace = False

        # 检查当前便签是否已关联其他任务
        current_task = self._link_service.get_task_for_note(self._note_id)
        if current_task is not None and current_task.id != task_id:
            if hasattr(win, "_show_confirm"):
                ok = win._show_confirm("当前便签已关联任务，是否替换？")
            else:
                ok = False
            if not ok:
                return
            replace = True

        # 检查目标任务是否已关联其他便签
        existing_note = self._link_service.get_note_for_task(task_id)
        if existing_note is not None and existing_note.id != self._note_id:
            if hasattr(win, "_show_confirm"):
                ok = win._show_confirm("该任务已关联其他便签，是否替换？")
            else:
                ok = False
            if not ok:
                return
            replace = True

        ok = self._link_service.link(task_id, self._note_id, replace=replace)
        if ok:
            # 清除被挤掉的旧便签的 [] 前缀
            if existing_note is not None and existing_note.id != self._note_id:
                self.note_unlinked.emit(existing_note.id)
            self.note_linked.emit(self._note_id, task_id)
        self.accept()

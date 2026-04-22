"""独立便签悬浮窗口 - 从主窗口拖出后展示单个便签"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QTextCharFormat, QTextBlockFormat, QTextCursor,
    QPixmap, QPainter, QPen, QIcon
)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette
from src.ui.link_dialog import make_link_pixmap

RESIZE_MARGIN = 6
CORNER_MARGIN = 14
MIN_W = 250
MIN_H = 300


class FloatingNoteWindow(QWidget):
    """可以单独弹出的便签悬浮小窗口，从主窗口"便签"标签拖出生成"""

    closed = pyqtSignal(int)  # 关闭时发送便签ID
    linked_note_saved = pyqtSignal(int, int)  # task_id, note_id
    manage_links_requested = pyqtSignal(int)  # note_id

    def __init__(
        self,
        note_service,
        note_id: int,
        stylesheet: str = "",
        task_id: int | None = None,
        task_title: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._svc = note_service
        self._note_id = note_id
        self._note = self._svc.get_by_id(note_id)
        self._task_id = task_id
        self._task_title = (task_title or "").strip()
        self._linked_emitted = False
        self._loading = False
        self._fmt_visible = False

        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_geo = None
        self._is_pinned = False  # 置顶状态

        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(1000)
        self._auto_save_timer.timeout.connect(self._auto_save)

        # 默认不置顶
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(300, 400)

        self._setup_ui()
        if stylesheet:
            self.setStyleSheet(stylesheet)
        self._load_note()
        self.setMouseTracking(True)
        self._enable_tracking(self)

    # ========== UI 构建 ==========

    def _enable_tracking(self, widget):
        widget.setMouseTracking(True)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._container = QFrame()
        self._container.setObjectName("FloatingNoteContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(self._container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        # --- 标题栏（可拖动） ---
        self._title_bar = QWidget()
        self._title_bar.setObjectName("FloatingNoteTitleBar")
        self._title_bar.setFixedHeight(34)
        tb_hl = QHBoxLayout(self._title_bar)
        tb_hl.setContentsMargins(10, 0, 6, 0)
        tb_hl.setSpacing(4)

        title_lbl = QLabel("便签")
        title_lbl.setObjectName("FloatingNoteTitleLabel")
        tb_hl.addWidget(title_lbl)
        tb_hl.addStretch()

        # 关联任务按钮
        self._link_btn = QPushButton()
        self._link_btn.setObjectName("NoteFormatBtn")
        self._link_btn.setIcon(QIcon(make_link_pixmap(14)))
        self._link_btn.setFixedSize(22, 22)
        self._link_btn.setCursor(Qt.PointingHandCursor)
        self._link_btn.setToolTip("关联任务")
        self._link_btn.clicked.connect(lambda: self.manage_links_requested.emit(self._note_id))
        tb_hl.addWidget(self._link_btn)

        # 置顶按钮
        self.pin_btn = QPushButton()
        self.pin_btn.setFixedSize(22, 22)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setToolTip("窗口置顶")
        self.pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_button()
        tb_hl.addWidget(self.pin_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("FloatingNoteCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._on_close)
        tb_hl.addWidget(close_btn)

        # 标题栏拖动支持
        self._title_bar.mousePressEvent = self._tb_mouse_press
        self._title_bar.mouseMoveEvent = self._tb_mouse_move
        self._title_bar.mouseReleaseEvent = self._tb_mouse_release
        c_layout.addWidget(self._title_bar)

        # --- 标题输入（前缀标签 + 输入框） ---
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(0)
        self._prefix_label = QLabel()
        self._prefix_label.setObjectName("NoteTitlePrefix")
        self._prefix_label.setVisible(False)
        title_row.addWidget(self._prefix_label)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("FloatingNoteTitleInput")
        self.title_edit.setPlaceholderText("标题（可选）")
        self.title_edit.textChanged.connect(self._on_content_changed)
        title_row.addWidget(self.title_edit, 1)
        c_layout.addLayout(title_row)

        # --- 正文编辑区（水平：body_edit + 右侧格式面板） ---
        mid = QWidget()
        mid_hl = QHBoxLayout(mid)
        mid_hl.setContentsMargins(0, 0, 0, 0)
        mid_hl.setSpacing(0)

        self.body_edit = QTextEdit()
        self.body_edit.setObjectName("FloatingNoteBodyEdit")
        self.body_edit.setPlaceholderText("开始记录…")
        self.body_edit.setAcceptRichText(False)
        self.body_edit.textChanged.connect(self._on_content_changed)
        self.body_edit.cursorPositionChanged.connect(self._sync_fmt_btns)
        self.body_edit.setFrameShape(QFrame.NoFrame)
        self.body_edit.viewport().setAutoFillBackground(False)
        mid_hl.addWidget(self.body_edit, 1)

        # 右侧格式面板（与主窗口便签页完全相同的设计）
        self._fmt_panel = self._build_format_panel()
        mid_hl.addWidget(self._fmt_panel, 0, Qt.AlignVCenter)

        c_layout.addWidget(mid, 1)
        outer.addWidget(self._container)

    def _build_format_panel(self):
        """与主窗口 NotePanel 完全相同的右侧格式面板：收起时只显示窄箭头"""
        panel = QFrame()
        panel.setObjectName("NoteFormatCard")
        hl = QHBoxLayout(panel)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        self._fmt_btns = QWidget()
        btns_vl = QVBoxLayout(self._fmt_btns)
        btns_vl.setContentsMargins(6, 6, 2, 6)
        btns_vl.setSpacing(6)

        self.bold_btn = self._make_fmt_btn("B", bold=True)
        self.bold_btn.clicked.connect(self._toggle_bold)
        btns_vl.addWidget(self.bold_btn, 0, Qt.AlignHCenter)

        self.italic_btn = self._make_fmt_btn("I", italic=True)
        self.italic_btn.clicked.connect(self._toggle_italic)
        btns_vl.addWidget(self.italic_btn, 0, Qt.AlignHCenter)

        self.underline_btn = self._make_fmt_btn("U", underline=True)
        self.underline_btn.clicked.connect(self._toggle_underline)
        btns_vl.addWidget(self.underline_btn, 0, Qt.AlignHCenter)

        self._fmt_btns.setVisible(False)
        hl.addWidget(self._fmt_btns)

        self.fmt_toggle_btn = QPushButton("‹")
        self.fmt_toggle_btn.setObjectName("NoteFormatToggleBtn")
        self.fmt_toggle_btn.setFixedWidth(14)
        self.fmt_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.fmt_toggle_btn.setToolTip("展开格式")
        self.fmt_toggle_btn.clicked.connect(self._toggle_fmt_card)
        hl.addWidget(self.fmt_toggle_btn)

        return panel

    def _make_fmt_btn(self, text, bold=False, italic=False, underline=False):
        btn = QPushButton(text)
        btn.setObjectName("NoteFormatBtn")
        btn.setCheckable(True)
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.PointingHandCursor)
        f = btn.font()
        if bold:
            f.setBold(True)
        if italic:
            f.setItalic(True)
        if underline:
            f.setUnderline(True)
        btn.setFont(f)
        return btn

    def _toggle_fmt_card(self):
        self._fmt_visible = not self._fmt_visible
        self._fmt_btns.setVisible(self._fmt_visible)
        self.fmt_toggle_btn.setText("›" if self._fmt_visible else "‹")
        self.fmt_toggle_btn.setToolTip("收起格式" if self._fmt_visible else "展开格式")

    # ========== 数据加载 / 保存 ==========

    def set_title_prefix(self, prefix: str):
        """设置标题前的 [任务名] 前缀标签"""
        if prefix:
            self._prefix_label.setText(prefix)
            self._prefix_label.setVisible(True)
            self.title_edit.setStyleSheet("padding-left: 2px;")
        else:
            self._prefix_label.setText("")
            self._prefix_label.setVisible(False)
            self.title_edit.setStyleSheet("")

    def _get_full_title(self) -> str:
        """获取完整标题（前缀 + 用户输入）"""
        prefix = self._prefix_label.text().strip()
        user_title = self.title_edit.text().strip()
        if prefix:
            return f"{prefix} {user_title}" if user_title else prefix
        return user_title

    def _load_note(self):
        if not self._note:
            return
        self._loading = True
        import re
        title = self._note.title or ""
        if not title.strip() and self._task_title:
            title = f"[{self._task_title}]"
        m = re.match(r'^(\[.*?\])\s*(.*)', title)
        if m:
            self.set_title_prefix(m.group(1))
            self.title_edit.setText(m.group(2))
        else:
            self.set_title_prefix("")
            self.title_edit.setText(title)
        if self._note.body_html and self._note.body_html.strip():
            self.body_edit.setHtml(self._note.body_html)
        else:
            self.body_edit.clear()
        self._apply_line_height()
        self._loading = False

    def _apply_line_height(self):
        cursor = self.body_edit.textCursor()
        cursor.select(QTextCursor.Document)
        bf = QTextBlockFormat()
        bf.setLineHeight(130, QTextBlockFormat.ProportionalHeight)
        cursor.mergeBlockFormat(bf)
        cursor.clearSelection()
        self.body_edit.setTextCursor(cursor)

    def _on_content_changed(self):
        if self._loading:
            return
        self._auto_save_timer.start()

    def _auto_save(self):
        # 检查是否有内容
        user_title = self.title_edit.text().strip()
        full_title = self._get_full_title()
        body_html = self.body_edit.toHtml()
        import re
        plain = re.sub(r'<[^>]+>', '', body_html).strip()
        plain = re.sub(r'&[a-zA-Z]+;', '', plain).strip()
        # 仅有 [任务名] 前缀而无实际内容时，视为无内容
        has_content = bool(user_title) or bool(plain)

        if not has_content:
            # 无内容：不存储，若已有note则永久删除并进入"未创建"状态
            if self._note_id is not None:
                try:
                    self._svc.permanent_delete(self._note_id)
                except Exception:
                    pass
            self._note_id = None
            self._note = None
            return

        # 有内容：确保存在note
        if self._note_id is None:
            new_note = self._svc.create()
            self._note_id = new_note.id
            self._note = new_note

        fresh = self._svc.get_by_id(self._note_id)
        if fresh is None or getattr(fresh, 'deleted', False):
            return

        self._svc.save(fresh, full_title, body_html)
        self._note = fresh

        if self._task_id is not None and self._note_id is not None and not self._linked_emitted:
            self._linked_emitted = True
            self.linked_note_saved.emit(self._task_id, self._note_id)

    def _on_close(self):
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
        self._auto_save()
        self.close()

    def closeEvent(self, event):
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
        # 保存关闭前的 note_id（_auto_save 可能因空内容将其置 None）
        orig_note_id = self._note_id
        self._auto_save()
        # 始终发送关闭信号，通知主窗口刷新任务列表
        if orig_note_id is not None:
            self.closed.emit(orig_note_id)
        event.accept()

    # ========== 置顶功能 ==========

    def set_pinned(self, pinned: bool):
        """设置窗口置顶状态（供主窗口拖出时调用）"""
        if bool(pinned) == bool(self._is_pinned):
            return
        self._is_pinned = bool(pinned)

        # 保存当前位置和大小
        geo = self.geometry()

        # 修改窗口 flags
        if self._is_pinned:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)

        # 恢复位置和大小（修改 flags 会导致窗口隐藏）
        self.setGeometry(geo)
        self.show()

        # 更新按钮样式
        self._update_pin_button()

    def _toggle_pin(self):
        """切换窗口置顶状态"""
        self._is_pinned = not self._is_pinned
        
        # 保存当前位置和大小
        geo = self.geometry()
        
        # 修改窗口 flags
        if self._is_pinned:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        
        # 恢复位置和大小（修改 flags 会导致窗口隐藏）
        self.setGeometry(geo)
        self.show()
        
        # 更新按钮样式
        self._update_pin_button()

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

    def _update_pin_button(self):
        """更新置顶按钮的图标和提示"""
        if self._is_pinned:
            self.pin_btn.setObjectName("FloatingNotePinBtnActive")
            self.pin_btn.setIcon(self._create_pin_icon("#FFFFFF"))
            self.pin_btn.setToolTip("取消置顶")
        else:
            self.pin_btn.setObjectName("FloatingNotePinBtn")
            color_str = "#888888"
            try:
                pal = QApplication.instance().palette()
                try:
                    c = pal.color(QPalette.PlaceholderText)
                except Exception:
                    c = pal.color(QPalette.WindowText)
                color_str = c.name()
            except Exception:
                pass
            self.pin_btn.setIcon(self._create_pin_icon(color_str))
            self.pin_btn.setToolTip("窗口置顶")
        # 刷新样式
        self.pin_btn.style().unpolish(self.pin_btn)
        self.pin_btn.style().polish(self.pin_btn)

    # ========== 富文本格式 ==========

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        cursor = self.body_edit.textCursor()
        fmt.setFontWeight(
            QFont.Normal if cursor.charFormat().fontWeight() >= QFont.Bold else QFont.Bold
        )
        cursor.mergeCharFormat(fmt)
        self.body_edit.setTextCursor(cursor)
        self.body_edit.setFocus()

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        cursor = self.body_edit.textCursor()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        cursor.mergeCharFormat(fmt)
        self.body_edit.setTextCursor(cursor)
        self.body_edit.setFocus()

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        cursor = self.body_edit.textCursor()
        fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(fmt)
        self.body_edit.setTextCursor(cursor)
        self.body_edit.setFocus()

    def _sync_fmt_btns(self):
        fmt = self.body_edit.textCursor().charFormat()
        self.bold_btn.setChecked(fmt.fontWeight() >= QFont.Bold)
        self.italic_btn.setChecked(fmt.fontItalic())
        self.underline_btn.setChecked(fmt.fontUnderline())

    # ========== 标题栏拖动 ==========

    def _tb_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
        event.accept()

    def _tb_mouse_move(self, event):
        if self._drag_pos:
            delta = event.globalPos() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPos()
        event.accept()

    def _tb_mouse_release(self, event):
        self._drag_pos = None
        event.accept()

    # ========== 窗口边缘缩放 ==========

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._detect_edge(event.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.globalPos()
                self._resize_start_geo = QRect(self.geometry())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_start_pos:
            self._do_resize(event.globalPos())
            event.accept()
            return
        edge = self._detect_edge(event.pos())
        if edge:
            self.setCursor(self._edge_cursor(edge))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_edge = None
            self._resize_start_pos = None
            self._resize_start_geo = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _detect_edge(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m, c = RESIZE_MARGIN, CORNER_MARGIN
        if x < c and y < c:        return "top_left"
        if x > w - c and y < c:    return "top_right"
        if x < c and y > h - c:    return "bottom_left"
        if x > w - c and y > h - c: return "bottom_right"
        if x < m:   return "left"
        if x > w - m: return "right"
        if y < m:   return "top"
        if y > h - m: return "bottom"
        return None

    def _edge_cursor(self, edge):
        if edge in ("left", "right"):            return Qt.SizeHorCursor
        if edge in ("top", "bottom"):            return Qt.SizeVerCursor
        if edge in ("top_left", "bottom_right"): return Qt.SizeFDiagCursor
        if edge in ("top_right", "bottom_left"): return Qt.SizeBDiagCursor
        return Qt.ArrowCursor

    def _do_resize(self, global_pos):
        if not self._resize_start_geo:
            return
        delta = global_pos - self._resize_start_pos
        geo = QRect(self._resize_start_geo)
        edge = self._resize_edge
        if "right" in edge:
            geo.setWidth(max(MIN_W, geo.width() + delta.x()))
        if "bottom" in edge:
            geo.setHeight(max(MIN_H, geo.height() + delta.y()))
        if "left" in edge:
            new_w = max(MIN_W, geo.width() - delta.x())
            if new_w != geo.width():
                geo.setLeft(geo.right() - new_w)
        if "top" in edge:
            new_h = max(MIN_H, geo.height() - delta.y())
            if new_h != geo.height():
                geo.setTop(geo.bottom() - new_h)
        self.setGeometry(geo)

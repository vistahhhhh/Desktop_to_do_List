"""便签面板 - 便签编辑、列表、自动保存"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QApplication, QGraphicsDropShadowEffect, QMenu,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QPoint, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QTextCharFormat, QTextBlockFormat, QTextCursor, QIcon
from src.ui.link_dialog import make_link_pixmap
from src.ui.task_item import _breakable


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text or ""
        super().setText(self._full_text)

    def setText(self, text: str):
        self._full_text = text or ""
        self._update_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self):
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.ElideRight, max(0, self.width()))
        super().setText(elided)


class NotePanel(QWidget):
    """便签主面板"""

    manage_links_requested = pyqtSignal(int)  # note_id

    def __init__(self, note_service, parent=None):
        super().__init__(parent)
        self._svc = note_service
        self._current_note = None
        self._loading = False

        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(1000)
        self._auto_save_timer.timeout.connect(self._auto_save)

        self._list_visible = False
        self._fmt_visible = False
        self._selected_note_ids = set()   # 多选便签 ID
        self._last_clicked_note_id = None  # Shift选择键用
        self._note_id_order = []           # 当前列表顺序
        self._search_query = ""  # 搜索关键词
        self._search_timer = QTimer(self)  # 搜索防抖定时器
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()
        self._load_or_create()  # 必须在_setup_ui之后，因为需要访问current_btn等UI组件

    # ========== UI 构建 ==========

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- 标题行：前缀标签 + 标题输入 + 关联按钮 ---
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 4, 0)
        title_row.setSpacing(0)
        self._prefix_label = QLabel()
        self._prefix_label.setObjectName("NoteTitlePrefix")
        self._prefix_label.setVisible(False)
        title_row.addWidget(self._prefix_label)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("NoteTitleInput")
        self.title_edit.setPlaceholderText("标题（可选）")
        self.title_edit.setAcceptDrops(False)
        self.title_edit.textChanged.connect(self._on_content_changed)
        title_row.addWidget(self.title_edit, 1)

        self.link_btn = self._make_fmt_btn("")
        self.link_btn.setIcon(QIcon(make_link_pixmap(16)))
        self.link_btn.setToolTip("关联任务")
        self.link_btn.clicked.connect(self._on_link_tasks_clicked)
        title_row.addWidget(self.link_btn, 0, Qt.AlignVCenter)
        root.addLayout(title_row)

        # --- 中间区域：正文 + 右侧格式面板 ---
        mid = QWidget()
        mid_layout = QHBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        self.body_edit = QTextEdit()
        self.body_edit.setObjectName("NoteBodyEdit")
        self.body_edit.setPlaceholderText("开始记录…")
        self.body_edit.setAcceptRichText(False)
        self.body_edit.textChanged.connect(self._on_content_changed)
        self.body_edit.cursorPositionChanged.connect(self._sync_format_buttons)
        self.body_edit.setFrameShape(QFrame.NoFrame)
        self.body_edit.viewport().setAutoFillBackground(False)
        self._apply_line_height()
        mid_layout.addWidget(self.body_edit, 1)

        # 右侧格式面板（展开/收起一体，垂直居中）
        self._fmt_panel = self._build_format_panel()
        mid_layout.addWidget(self._fmt_panel, 0, Qt.AlignVCenter)

        root.addWidget(mid, 1)

        # --- 底部栏（透明容器，只含三个按钮） ---
        bottom_container = QWidget()
        bottom_container.setObjectName("NoteBottomContainer")
        bottom_vl = QVBoxLayout(bottom_container)
        bottom_vl.setContentsMargins(0, 0, 0, 0)
        bottom_vl.setSpacing(0)

        bottom_bar = self._build_bottom_bar()
        bottom_vl.addWidget(bottom_bar)

        root.addWidget(bottom_container)

        # --- 悬浮列表面板（直接作为 NotePanel 子控件，绝对定位，不加入任何布局） ---
        self._list_panel = self._build_list_panel()
        self._list_panel.setVisible(False)

    # ---------- 格式工具面板 ----------

    def _build_format_panel(self):
        """右侧格式面板：收起时只显示窄箭头，展开时显示 B/I/U + 箭头"""
        panel = QFrame()
        panel.setObjectName("NoteFormatCard")
        hl = QHBoxLayout(panel)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        # 按钮区域（展开时可见）
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

        # 展开/收起箭头
        self.fmt_toggle_btn = QPushButton("‹")
        self.fmt_toggle_btn.setObjectName("NoteFormatToggleBtn")
        self.fmt_toggle_btn.setFixedWidth(14)
        self.fmt_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.fmt_toggle_btn.setToolTip("展开格式")
        self.fmt_toggle_btn.clicked.connect(self._toggle_format_card)
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

    def _toggle_format_card(self):
        self._fmt_visible = not self._fmt_visible
        self._fmt_btns.setVisible(self._fmt_visible)
        self._update_fmt_toggle_text()

    def _update_fmt_toggle_text(self):
        self.fmt_toggle_btn.setText("›" if self._fmt_visible else "‹")
        self.fmt_toggle_btn.setToolTip("收起格式" if self._fmt_visible else "展开格式")

    # ---------- 列表面板（悬浮卡片，绝对定位，不在任何布局中） ----------

    def _build_list_panel(self):
        panel = QFrame(self)          # parent=self，使其作为 NotePanel 的悬浮子控件
        panel.setObjectName("NoteListPanel")
        panel.setFrameShape(QFrame.NoFrame)
        panel.setFocusPolicy(Qt.StrongFocus)
        panel.keyPressEvent = self._list_key_press
        panel.contextMenuEvent = self._list_context_menu

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        panel.setGraphicsEffect(shadow)

        vl = QVBoxLayout(panel)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # 顶部拖动手柄（用于调节列表高度）
        self._list_drag_handle = QWidget()
        self._list_drag_handle.setObjectName("NoteListDragHandle")
        self._list_drag_handle.setFixedHeight(3)
        self._list_drag_handle.setCursor(Qt.SizeVerCursor)
        self._list_drag_handle.mousePressEvent = self._list_drag_press
        self._list_drag_handle.mouseMoveEvent = self._list_drag_move
        self._list_drag_handle.mouseReleaseEvent = self._list_drag_release
        vl.addWidget(self._list_drag_handle)

        # 搜索框
        search_container = QWidget()
        search_container.setObjectName("NoteSearchContainer")
        search_hl = QHBoxLayout(search_container)
        search_hl.setContentsMargins(8, 4, 8, 4)
        search_hl.setSpacing(4)

        search_icon = QLabel("⌕")
        search_icon.setObjectName("NoteSearchIcon")
        search_hl.addWidget(search_icon)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("NoteSearchInput")
        self._search_input.setPlaceholderText("搜索便签...")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_hl.addWidget(self._search_input, 1)

        self._search_count_lbl = QLabel()
        self._search_count_lbl.setObjectName("NoteSearchCount")
        self._search_count_lbl.setVisible(False)
        search_hl.addWidget(self._search_count_lbl)

        self._search_clear_btn = QPushButton("✕")
        self._search_clear_btn.setObjectName("NoteSearchClearBtn")
        self._search_clear_btn.setFixedSize(20, 20)
        self._search_clear_btn.setCursor(Qt.PointingHandCursor)
        self._search_clear_btn.setVisible(False)
        self._search_clear_btn.clicked.connect(self._clear_search)
        search_hl.addWidget(self._search_clear_btn)

        vl.addWidget(search_container)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("NoteListScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)

        self._list_container = QWidget()
        self._list_container.setObjectName("NoteListScrollContent")
        self._list_container.setAutoFillBackground(False)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(4, 0, 4, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._list_container)
        vl.addWidget(self._scroll)

        return panel

    def _position_list_panel(self):
        """将列表卡片定位在 current_btn 正上方，与按钮同宽同水平位置"""
        btn_pos = self.current_btn.mapTo(self, QPoint(0, 0))
        btn_w = self.current_btn.width()
        panel_h = getattr(self, '_list_panel_height', 180)
        panel_x = btn_pos.x()
        panel_y = btn_pos.y() - panel_h - 4   # 4px 间隙
        panel_y = max(0, panel_y)              # 不超出顶部
        self._list_panel.setGeometry(panel_x, panel_y, btn_w, panel_h)

    # ---------- 列表高度拖动 ----------

    def _list_drag_press(self, event):
        if event.button() == Qt.LeftButton:
            self._list_drag_start_y = event.globalPos().y()
            self._list_drag_start_h = self._list_panel.height()
        event.accept()

    def _list_drag_move(self, event):
        if not hasattr(self, '_list_drag_start_y') or self._list_drag_start_y is None:
            event.accept()
            return
        delta = self._list_drag_start_y - event.globalPos().y()  # 往上拉为正
        new_h = max(100, min(400, self._list_drag_start_h + delta))
        self._list_panel_height = new_h
        self._position_list_panel()
        event.accept()

    def _list_drag_release(self, event):
        self._list_drag_start_y = None
        self._list_drag_start_h = None
        event.accept()

    # ---------- 搜索功能 ----------

    def _on_search_changed(self, text):
        """搜索输入变化，启动防抖定时器"""
        self._search_query = text.strip()
        self._search_clear_btn.setVisible(bool(text))
        self._search_timer.start()  # 300ms后触发搜索

    def _do_search(self):
        """执行搜索过滤"""
        self._refresh_list()

    def _clear_search(self):
        """清空搜索"""
        self._search_input.clear()
        self._search_query = ""
        self._search_count_lbl.setVisible(False)
        self._refresh_list()

    def _filter_notes(self, notes):
        """根据搜索关键词过滤便签"""
        if not self._search_query:
            return notes
        
        query_lower = self._search_query.lower()
        filtered = []
        
        for note in notes:
            # 搜索标题
            if note.title and query_lower in note.title.lower():
                filtered.append(note)
                continue
            
            # 搜索正文（去除HTML标签，只搜索前500字符）
            plain_text = self._extract_plain_text(note.body_html)
            if query_lower in plain_text[:500].lower():
                filtered.append(note)
        
        return filtered

    def _extract_plain_text(self, html):
        """从HTML中提取纯文本"""
        if not html:
            return ""
        import re
        # 移除 style/script 块
        text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # 移除所有HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除HTML实体
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        return text.strip()

    # ---------- 底部栏 ----------

    def _build_bottom_bar(self):
        bar = QWidget()
        bar.setObjectName("NoteBottomBar")
        bar.setFixedHeight(44)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(8, 4, 8, 4)
        hl.setSpacing(6)

        self.add_btn = QPushButton("＋")
        self.add_btn.setObjectName("NoteAddBtn")
        self.add_btn.setFixedSize(32, 32)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("新建便签")
        self.add_btn.clicked.connect(self._new_note)
        hl.addWidget(self.add_btn)

        self.current_btn = QPushButton("▲  新便签")
        self.current_btn.setObjectName("NoteCurrentBtn")
        self.current_btn.setCursor(Qt.PointingHandCursor)
        self.current_btn.clicked.connect(self._toggle_list)
        hl.addWidget(self.current_btn, 1)

        self.trash_btn = QPushButton("🗑")
        self.trash_btn.setObjectName("NoteDelBtn")
        self.trash_btn.setFixedSize(32, 32)
        self.trash_btn.setCursor(Qt.PointingHandCursor)
        self.trash_btn.setToolTip("回收站")
        self.trash_btn.clicked.connect(self._open_trash)
        hl.addWidget(self.trash_btn)

        return bar

    # ========== 便签加载 / 新建 ==========

    # ========== 前缀标签管理 ==========

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

    def _load_or_create(self):
        notes = self._svc.get_all()
        if notes:
            self._load_note(notes[0])
        else:
            # 不立即创建空便签，只清空UI，等用户输入内容后再创建
            self._current_note = None
            self._loading = True
            self.set_title_prefix("")
            self.title_edit.clear()
            self.body_edit.clear()
            self._loading = False
            self._update_current_btn()

    def _load_note(self, note):
        import re
        self._loading = True
        self._current_note = note
        title = note.title or ""
        m = re.match(r'^(\[.*?\])\s*(.*)', title)
        if m:
            self.set_title_prefix(m.group(1))
            self.title_edit.setText(m.group(2))
        else:
            self.set_title_prefix("")
            self.title_edit.setText(title)
        if note.body_html and note.body_html.strip():
            self.body_edit.setHtml(note.body_html)
        else:
            self.body_edit.clear()
        self._apply_line_height()
        self._loading = False
        self._update_current_btn()

    def _new_note(self):
        self._flush_save()
        # 不立即创建空便签，只清空UI，等用户输入内容后再创建
        self._current_note = None
        self._loading = True
        self.set_title_prefix("")
        self.title_edit.clear()
        self.body_edit.clear()
        self._loading = False
        self._update_current_btn()
        if self._list_visible:
            self._toggle_list()
        self.title_edit.setFocus()

    def _update_current_btn(self):
        # 保护：UI未完全初始化时不更新
        if not hasattr(self, 'current_btn'):
            return
        if self._current_note:
            name = self._current_note.display_name()
            arrow = "▼" if self._list_visible else "▲"
            self.current_btn.setText(f"{arrow}  {name}")
        else:
            self.current_btn.setText("▲  新便签")

    # ========== 便签列表 ==========

    def _toggle_list(self):
        self._list_visible = not self._list_visible
        if self._list_visible:
            self._refresh_list()
            self._position_list_panel()
            self._list_panel.raise_()
            QApplication.instance().installEventFilter(self)
        else:
            QApplication.instance().removeEventFilter(self)
        self._list_panel.setVisible(self._list_visible)
        self._update_current_btn()

    def eventFilter(self, obj, event):
        """当列表展开时，点击列表外任意区域则收起列表"""
        if self._list_visible and event.type() == QEvent.MouseButtonPress:
            if isinstance(obj, QWidget):
                # 检查点击是否在列表面板内部（包括子控件）
                w = obj
                while w is not None:
                    if w is self._list_panel:
                        return False   # 在列表内，不拦截
                    if w is self.current_btn:
                        return False   # 点击的是展开/收起按钮，让其正常处理
                    w = w.parentWidget()
                # 点击在列表外，收起列表
                self._toggle_list()
        return False   # 不消耗事件

    def _refresh_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._selected_note_ids.clear()
        self._note_id_order.clear()

        all_notes = self._svc.get_all()
        filtered_notes = self._filter_notes(all_notes)
        
        # 更新匹配数量显示
        if self._search_query:
            count_text = f"({len(filtered_notes)}/{len(all_notes)})"
            self._search_count_lbl.setText(count_text)
            self._search_count_lbl.setVisible(True)
        else:
            self._search_count_lbl.setVisible(False)
        
        # 显示过滤后的便签
        if filtered_notes:
            for note in filtered_notes:
                self._note_id_order.append(note.id)
                row = self._make_list_row(note)
                self._list_layout.addWidget(row)
            # 确保标题在当前宽度下正确省略
            QTimer.singleShot(0, self._update_row_elisions)
        elif self._search_query:
            # 搜索无结果时显示提示
            empty_lbl = QLabel("无匹配便签")
            empty_lbl.setObjectName("NoteListEmpty")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: gray; padding: 20px;")
            self._list_layout.addWidget(empty_lbl)

    def _update_row_elisions(self):
        """遍历列表行，触发每个 ElidedLabel 重新计算省略号（用于列表宽度变化后）"""
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            row = item.widget() if item else None
            if not row:
                continue
            # 查找行内的 ElidedLabel
            elided = row.findChild(ElidedLabel)
            if elided:
                elided._update_elide()

    def _make_list_row(self, note):
        row = QWidget()
        obj_name = "NoteListItemActive" if (
            self._current_note and note.id == self._current_note.id
        ) else "NoteListItem"
        row.setObjectName(obj_name)
        row.setProperty("note_id", note.id)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.setMinimumWidth(80)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(6, 2, 6, 2)
        hl.setSpacing(1)

        lbl = ElidedLabel(note.display_name())
        lbl.setObjectName("NoteListItemLabel")
        lbl.setWordWrap(False)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl.setMinimumWidth(0)
        hl.addWidget(lbl, 1)

        date_lbl = QLabel(note.updated_at.strftime("%m-%d") if note.updated_at else "")
        date_lbl.setObjectName("NoteListItemDate")
        date_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        date_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        date_lbl.setFixedWidth(40)
        hl.addWidget(date_lbl)
        hl.addSpacing(0)

        del_btn = QPushButton("🗑")
        del_btn.setObjectName("NoteListDelBtn")
        del_btn.setFixedSize(22, 22)
        del_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        del_btn.setCursor(Qt.PointingHandCursor)
        note_id = note.id
        del_btn.clicked.connect(lambda _, nid=note_id: self._delete_from_list(nid))
        hl.addWidget(del_btn)

        row.mousePressEvent = lambda e, nid=note.id: self._on_list_row_click(e, nid)
        row.setCursor(Qt.PointingHandCursor)
        return row

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 列表面板可见时，宽度变化后重新计算省略号
        if self._list_visible:
            QTimer.singleShot(0, self._update_row_elisions)

    # ========== 便签列表多选 / 删除 ==========

    def _on_list_row_click(self, event, note_id):
        """Ctrl=切换选中  Shift=范围选中  单击=单选并加载"""
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.ControlModifier:
            # Ctrl+点击：切换选中状态
            if note_id in self._selected_note_ids:
                self._selected_note_ids.discard(note_id)
            else:
                self._selected_note_ids.add(note_id)
            self._last_clicked_note_id = note_id
            self._update_row_selection()
            self._list_panel.setFocus()
        elif modifiers & Qt.ShiftModifier:
            # Shift+点击：范围选中
            if self._last_clicked_note_id is not None and self._last_clicked_note_id in self._note_id_order:
                idx_a = self._note_id_order.index(self._last_clicked_note_id)
                idx_b = self._note_id_order.index(note_id) if note_id in self._note_id_order else idx_a
                lo, hi = min(idx_a, idx_b), max(idx_a, idx_b)
                self._selected_note_ids = set(self._note_id_order[lo:hi + 1])
            else:
                self._selected_note_ids = {note_id}
                self._last_clicked_note_id = note_id
            self._update_row_selection()
            self._list_panel.setFocus()
        else:
            # 普通单击：加载便签
            self._selected_note_ids.clear()
            self._last_clicked_note_id = note_id
            note = self._svc.get_by_id(note_id)
            if note:
                self._flush_save()
                self._load_note(note)
                self._toggle_list()

    def _update_row_selection(self):
        """根据 _selected_note_ids 刷新行的高亮状态"""
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            row = item.widget() if item else None
            if row is None:
                continue
            nid = row.property("note_id")
            if nid is None:
                continue
            val = "true" if nid in self._selected_note_ids else "false"
            row.setProperty("selected", val)
            row.style().unpolish(row)
            row.style().polish(row)
            row.update()

    def _delete_selected_notes(self):
        """批量删除选中的便签"""
        ids = list(self._selected_note_ids)
        if not ids:
            return
        count = len(ids)
        msg = f"确定要删除选中的 {count} 条便签吗？\n删除后可在回收站恢复。"
        if not self._confirm(msg):
            return
        need_reload = False
        for nid in ids:
            if self._current_note and self._current_note.id == nid:
                need_reload = True
            self._svc.delete(nid)
        self._selected_note_ids.clear()
        if need_reload:
            self._load_or_create()
        self._refresh_list()

    def _list_key_press(self, event):
        """列表面板按键处理：Delete 删除选中便签"""
        if event.key() == Qt.Key_Delete and self._selected_note_ids:
            self._delete_selected_notes()
            return
        QFrame.keyPressEvent(self._list_panel, event)

    def _list_context_menu(self, event):
        """列表面板右键菜单"""
        if not self._selected_note_ids:
            return
        from PyQt5.QtGui import QCursor
        menu = QMenu(self._list_panel)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet(
            self.window().styleSheet() +
            "\nQMenu::item { padding: 2px 10px; min-height: 16px; }"
        )
        count = len(self._selected_note_ids)
        del_action = menu.addAction(f"删除选中 ({count})")
        del_action.triggered.connect(self._delete_selected_notes)
        menu.exec_(QCursor.pos())

    # ========== 确认弹窗 ==========

    def _confirm(self, message: str) -> bool:
        win = self.window()
        if hasattr(win, '_show_confirm'):
            return win._show_confirm(message)
        return QMessageBox.question(
            self, "确认", message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes

    def _delete_from_list(self, note_id: int):
        if not self._confirm("确定要删除这条便签吗？\n删除后可在回收站恢复。"):
            return
        is_current = (self._current_note and self._current_note.id == note_id)
        self._svc.delete(note_id)
        if is_current:
            self._load_or_create()
        self._refresh_list()

    # ========== 回收站弹窗 ==========

    def _open_trash(self):
        """打开便签回收站弹窗（样式与桌面待办回收站相同）"""
        from PyQt5.QtWidgets import QDialog, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor

        deleted = self._svc.get_deleted()
        win = self.window()

        dialog = QDialog(win)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        if hasattr(win, '_make_dialog_draggable'):
            win._make_dialog_draggable(dialog)
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
        title = QLabel("🗑 便签回收站")
        title.setObjectName("EditorTitle")
        header.addWidget(title)
        header.addStretch()
        if deleted:
            clear_btn = QPushButton("清空")
            clear_btn.setObjectName("TrashDeleteBtn")
            clear_btn.setCursor(Qt.PointingHandCursor)
            clear_btn.setFixedHeight(24)
            clear_btn.clicked.connect(lambda: self._trash_clear_all(dialog))
            header.addWidget(clear_btn)
        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditorCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 列表
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
            for note in deleted:
                item = QFrame()
                item.setObjectName("TrashItem")
                row = QHBoxLayout(item)
                row.setContentsMargins(4, 1, 4, 1)
                row.setSpacing(4)

                lbl = QLabel(_breakable(note.display_name()))
                lbl.setObjectName("TaskTitle")
                lbl.setWordWrap(True)
                lbl.setMinimumWidth(0)
                row.addWidget(lbl, 1)

                restore_btn = QPushButton("恢复")
                restore_btn.setObjectName("TrashRestoreBtn")
                restore_btn.setCursor(Qt.PointingHandCursor)
                restore_btn.setFixedHeight(20)
                nid = note.id
                restore_btn.clicked.connect(
                    lambda _, nid=nid, d=dialog: self._trash_restore(nid, d))
                row.addWidget(restore_btn)

                perm_btn = QPushButton("删除")
                perm_btn.setObjectName("TrashDeleteBtn")
                perm_btn.setCursor(Qt.PointingHandCursor)
                perm_btn.setFixedHeight(20)
                perm_btn.clicked.connect(
                    lambda _, nid=nid, d=dialog: self._trash_perm_delete(nid, d))
                row.addWidget(perm_btn)

                list_layout.addWidget(item)

        scroll.setWidget(list_widget)
        layout.addWidget(scroll, 1)
        outer.addWidget(container)
        dialog.setStyleSheet(win.styleSheet())
        dialog.exec_()

    def _trash_restore(self, note_id, dialog):
        self._svc.restore(note_id)
        dialog.reject()
        self._open_trash()

    def _trash_perm_delete(self, note_id, dialog):
        if self._confirm("彻底删除后将无法恢复，确定吗？"):
            self._svc.permanent_delete(note_id)
            dialog.reject()
            self._open_trash()

    def _trash_clear_all(self, dialog):
        if self._confirm("确定要清空回收站吗？\n所有便签将被永久删除且无法恢复。"):
            self._svc.clear_deleted()
            dialog.reject()
            self._open_trash()

    # ========== 自动保存 ==========

    def _on_content_changed(self):
        if self._loading:
            return
        self._auto_save_timer.start()
        self._update_current_btn()

    def _auto_save(self):
        full_title = self._get_full_title()
        body_html = self.body_edit.toHtml()
        # 检查正文是否有实际内容（去除HTML标签后）
        import re
        plain = re.sub(r'<[^>]+>', '', body_html).strip()
        plain = re.sub(r'&[a-zA-Z]+;', '', plain).strip()
        
        has_content = bool(full_title) or bool(plain)

        if self._current_note is None:
            # 当前无便签，只有有内容时才创建
            if has_content:
                self._current_note = self._svc.create()
                self._svc.save(self._current_note, full_title, body_html)
        else:
            if has_content:
                # 已有便签，正常保存
                self._svc.save(self._current_note, full_title, body_html)
            else:
                # 已有便签被清空：不再存储，直接永久删除并回到未创建状态
                try:
                    self._svc.permanent_delete(self._current_note.id)
                except Exception:
                    pass
                self._current_note = None
                if self._list_visible:
                    self._refresh_list()
        self._update_current_btn()

    def _flush_save(self):
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
        self._auto_save()

    # ========== 富文本格式 ==========

    def _apply_line_height(self):
        cursor = self.body_edit.textCursor()
        cursor.select(QTextCursor.Document)
        bf = QTextBlockFormat()
        bf.setLineHeight(130, QTextBlockFormat.ProportionalHeight)
        cursor.mergeBlockFormat(bf)
        cursor.clearSelection()
        self.body_edit.setTextCursor(cursor)

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        cursor = self.body_edit.textCursor()
        current = cursor.charFormat()
        fmt.setFontWeight(QFont.Normal if current.fontWeight() >= QFont.Bold else QFont.Bold)
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

    def _sync_format_buttons(self):
        fmt = self.body_edit.textCursor().charFormat()
        self.bold_btn.setChecked(fmt.fontWeight() >= QFont.Bold)
        self.italic_btn.setChecked(fmt.fontItalic())
        self.underline_btn.setChecked(fmt.fontUnderline())

    def _on_link_tasks_clicked(self):
        note_id = self.get_current_note_id()
        if note_id is None:
            QMessageBox.information(self, "提示", "请先输入便签内容后再关联任务。")
            return
        self.manage_links_requested.emit(note_id)

    # ========== 公开接口（供 main_window 调用） ==========

    def get_current_note_id(self) -> int | None:
        """返回当前正在编辑的便签 ID，拖出功能使用"""
        return self._current_note.id if self._current_note else None

    def start_new_note(self):
        """拖出当前便签后，主面板自动切换到新空白便签"""
        self._new_note()

    def ensure_note_for_detach(self) -> int:
        """确保当前有一个可拖出的便签ID；空白便签也允许拖出"""
        if self._current_note is None:
            self._current_note = self._svc.create()
            self._update_current_btn()
        return self._current_note.id

    def load_note_by_id(self, note_id: int) -> bool:
        """加载指定ID的便签（浮动便签关闭时使用）"""
        note = self._svc.get_by_id(note_id)
        if note:
            self._load_note(note)
            return True
        return False

    # ========== 面板切换 ==========

    def on_show(self):
        pass

    def flush_on_hide(self):
        self._flush_save()

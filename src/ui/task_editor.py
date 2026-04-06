"""任务编辑弹窗 - 新建/编辑任务，含日期选择器、标签选择器"""

from datetime import date, timedelta
from typing import Optional, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QButtonGroup, QRadioButton,
    QDateEdit, QWidget, QFrame, QMessageBox, QSizePolicy,
    QGraphicsDropShadowEffect, QScrollArea, QComboBox, QCheckBox,
    QCalendarWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QColor, QTextCharFormat, QFont

from src.models.task import Task
from src.models.tag import Tag


# 预定义标签颜色
TAG_COLORS = [
    "#6366F1", "#EF4444", "#10B981", "#F59E0B",
    "#3B82F6", "#EC4899", "#8B5CF6", "#14B8A6",
]

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class TagChip(QPushButton):
    """可选中的标签小标记"""

    toggled_tag = pyqtSignal(int, bool)  # tag_id, selected

    def __init__(self, tag: Tag, selected: bool = False, parent=None):
        super().__init__(parent)
        self.tag = tag
        self._selected = selected
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(selected)
        self.clicked.connect(self._on_clicked)
        self._update_style()

    def _on_clicked(self):
        self._selected = self.isChecked()
        self._update_style()
        self.toggled_tag.emit(self.tag.id, self._selected)

    def _update_style(self):
        color = self.tag.color or "#6366F1"
        if self._selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 10px;
                    padding: 4px 12px;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {color};
                    border: 1px solid {color};
                    border-radius: 10px;
                    padding: 4px 12px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: #FFFFFF;
                }}
            """)
        self.setText(f"#{self.tag.name}")

    def is_selected(self):
        return self._selected


class TaskEditorDialog(QDialog):
    """任务编辑弹窗：支持新建和编辑模式"""

    task_saved = pyqtSignal(int)

    def __init__(self, tags: List[Tag], task: Optional[Task] = None,
                 parent=None, default_type: Optional[str] = None,
                 default_tag_ids: Optional[List[int]] = None):
        super().__init__(parent)
        self._tags = tags
        self._task = task
        self._is_edit = task is not None
        self._default_type = default_type
        self._selected_tag_ids = set()
        self._tag_chips = []

        if self._is_edit and task.tags:
            self._selected_tag_ids = {t.id for t in task.tags}
        elif default_tag_ids:
            self._selected_tag_ids = set(default_tag_ids)

        self._setup_window()
        self._setup_ui()
        self._load_task_data()

    def _setup_window(self):
        self.setWindowTitle("编辑任务" if self._is_edit else "新建任务")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(400)
        self.setMaximumWidth(500)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.container = QFrame()
        self.container.setObjectName("EditorContainer")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 16, 20, 20)
        container_layout.setSpacing(12)

        # --- 标题栏 ---
        header = QHBoxLayout()
        title_text = "编辑任务" if self._is_edit else "新建任务"
        header_label = QLabel(title_text)
        header_label.setObjectName("EditorTitle")
        header.addWidget(header_label)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("EditorCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        container_layout.addLayout(header)

        # --- 标题输入 ---
        container_layout.addWidget(self._make_field_label("标题 *"))
        self.title_input = QLineEdit()
        self.title_input.setObjectName("EditorInput")
        self.title_input.setPlaceholderText("输入任务标题...")
        self.title_input.setMaxLength(200)
        container_layout.addWidget(self.title_input)

        # --- 任务类型（三种） ---
        container_layout.addWidget(self._make_field_label("任务类型"))
        type_row = QHBoxLayout()
        type_row.setSpacing(12)
        self.type_group = QButtonGroup(self)
        self.radio_short = QRadioButton("当日任务")
        self.radio_weekly = QRadioButton("本周计划")
        self.radio_long = QRadioButton("长期任务")
        self.radio_short.setObjectName("EditorRadio")
        self.radio_weekly.setObjectName("EditorRadio")
        self.radio_long.setObjectName("EditorRadio")
        self.type_group.addButton(self.radio_short, 0)
        self.type_group.addButton(self.radio_weekly, 1)
        self.type_group.addButton(self.radio_long, 2)
        self.radio_short.setChecked(True)
        type_row.addWidget(self.radio_short)
        type_row.addWidget(self.radio_weekly)
        type_row.addWidget(self.radio_long)
        type_row.addStretch()
        container_layout.addLayout(type_row)

        # --- 本周计划：选择周几（显示实际日期） ---
        self.weekday_label = self._make_field_label("完成日期")
        container_layout.addWidget(self.weekday_label)
        self.weekday_combo = QComboBox()
        self.weekday_combo.setObjectName("SettingsCombo")
        self._populate_weekday_combo()
        container_layout.addWidget(self.weekday_combo)

        # --- 长期任务：截止日期（可选） ---
        self.date_label = self._make_field_label("截止日期（可选）")
        container_layout.addWidget(self.date_label)

        self.no_date_check = QCheckBox("不设截止日期")
        self.no_date_check.setObjectName("SettingsCheck")
        self.no_date_check.setChecked(True)  # 默认不设日期
        self.no_date_check.toggled.connect(self._on_no_date_changed)
        container_layout.addWidget(self.no_date_check)

        date_row = QHBoxLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setObjectName("EditorInput")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate().addMonths(1))
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        # 自定义日历样式
        cal = self.date_edit.calendarWidget()
        if cal:
            cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
            # 日历弹窗是独立窗口，需要透明背景才能实现真圆角
            popup = cal.window()
            if popup and popup is not self:
                popup.setWindowFlags(popup.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
                popup.setAttribute(Qt.WA_TranslucentBackground)
        # 日历弹窗需要在显示时应用样式
        self.date_edit.installEventFilter(self)
        date_row.addWidget(self.date_edit, 1)

        self.month_only_check = QCheckBox("只选月份")
        self.month_only_check.setObjectName("SettingsCheck")
        self.month_only_check.toggled.connect(self._on_month_only_changed)
        date_row.addWidget(self.month_only_check)
        self.date_row_widget = QWidget()
        self.date_row_widget.setLayout(date_row)
        container_layout.addWidget(self.date_row_widget)

        # 类型切换联动
        self.type_group.buttonClicked.connect(self._on_type_changed)
        self._on_type_changed()

        # --- 优先级 ---
        container_layout.addWidget(self._make_field_label("优先级"))
        prio_row = QHBoxLayout()
        prio_row.setSpacing(8)
        self.prio_group = QButtonGroup(self)

        prio_configs = [
            ("高", "high", "#C4736E"),
            ("中", "medium", "#C9A96E"),
            ("低", "low", "#7D9C88"),
        ]
        self._prio_buttons = {}
        for label, value, color in prio_configs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setFixedWidth(42)
            btn.setProperty("prio_value", value)
            btn.setProperty("prio_color", color)
            self.prio_group.addButton(btn)
            self._prio_buttons[value] = btn
            prio_row.addWidget(btn)

        prio_row.addStretch()
        container_layout.addLayout(prio_row)

        self._prio_buttons["medium"].setChecked(True)
        self.prio_group.buttonClicked.connect(self._update_prio_styles)
        self._update_prio_styles()

        # --- 标签选择器 ---
        container_layout.addWidget(self._make_field_label("标签"))
        self.tag_flow = QWidget()
        self.tag_flow_layout = QHBoxLayout(self.tag_flow)
        self.tag_flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_flow_layout.setSpacing(6)
        self._build_tag_chips()
        self.tag_flow_layout.addStretch()
        container_layout.addWidget(self.tag_flow)

        # 标签只在侧栏右键新建，编辑器仅选择已有标签

        # --- 描述 ---
        container_layout.addWidget(self._make_field_label("详细描述"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setObjectName("EditorTextArea")
        self.desc_edit.setPlaceholderText("请输入项目详细描述")
        self.desc_edit.setFixedHeight(60)
        container_layout.addWidget(self.desc_edit)

        # --- 底部按钮 ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("EditorCancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("EditorSaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedSize(80, 36)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        container_layout.addLayout(btn_row)

        outer.addWidget(self.container)

    # ========== 辅助构建 ==========

    def _make_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("EditorFieldLabel")
        return label

    def _build_tag_chips(self):
        for chip in self._tag_chips:
            self.tag_flow_layout.removeWidget(chip)
            chip.deleteLater()
        self._tag_chips.clear()

        for tag in self._tags:
            selected = tag.id in self._selected_tag_ids
            chip = TagChip(tag, selected=selected)
            chip.toggled_tag.connect(self._on_tag_toggled)
            self.tag_flow_layout.insertWidget(self.tag_flow_layout.count() - 1, chip)
            self._tag_chips.append(chip)

    def _on_tag_toggled(self, tag_id: int, selected: bool):
        if selected:
            self._selected_tag_ids.add(tag_id)
        else:
            self._selected_tag_ids.discard(tag_id)

    def _on_type_changed(self):
        is_weekly = self.radio_weekly.isChecked()
        is_long = self.radio_long.isChecked()

        # 本周计划 → 显示周几选择
        self.weekday_label.setVisible(is_weekly)
        self.weekday_combo.setVisible(is_weekly)

        # 长期任务 → 显示日期选择（可选）
        self.date_label.setVisible(is_long)
        self.no_date_check.setVisible(is_long)
        has_date = is_long and not self.no_date_check.isChecked()
        self.date_row_widget.setVisible(has_date)

    def _on_no_date_changed(self, checked):
        """切换是否设置截止日期"""
        self.date_row_widget.setVisible(not checked)

    def _on_month_only_changed(self, checked):
        if checked:
            self.date_edit.setDisplayFormat("yyyy-MM")
        else:
            self.date_edit.setDisplayFormat("yyyy-MM-dd")

    def _populate_weekday_combo(self):
        """填充日期选择（从今天起未来10天）"""
        today = date.today()
        default_idx = min(1, 9)  # 默认选明天
        for i in range(10):
            d = today + timedelta(days=i)
            wd_name = WEEKDAY_NAMES[d.weekday()]
            label = f"{wd_name}  {d.month}/{d.day}"
            self.weekday_combo.addItem(label, d)
        self.weekday_combo.setCurrentIndex(default_idx)

    def _get_weekday_date(self) -> date:
        """获取选择的具体日期"""
        return self.weekday_combo.currentData()

    def _update_prio_styles(self):
        for value, btn in self._prio_buttons.items():
            color = btn.property("prio_color")
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 4px;
                        font-size: 11px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {color};
                        border: 1px solid {color};
                        border-radius: 4px;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        background-color: {color};
                        color: #FFFFFF;
                    }}
                """)

    # ========== 数据加载 ==========

    def _load_task_data(self):
        if not self._is_edit and self._default_type:
            type_radio = {
                Task.TYPE_SHORT_TERM: self.radio_short,
                Task.TYPE_WEEKLY: self.radio_weekly,
                Task.TYPE_LONG_TERM: self.radio_long,
            }
            radio = type_radio.get(self._default_type, self.radio_short)
            radio.setChecked(True)
            self._on_type_changed()

        if not self._is_edit or self._task is None:
            return

        task = self._task
        self.title_input.setText(task.title)

        if task.task_type == Task.TYPE_WEEKLY:
            self.radio_weekly.setChecked(True)
            if task.due_date:
                # 在combo中查找匹配的日期
                for i in range(self.weekday_combo.count()):
                    if self.weekday_combo.itemData(i) == task.due_date:
                        self.weekday_combo.setCurrentIndex(i)
                        break
        elif task.task_type == Task.TYPE_LONG_TERM:
            self.radio_long.setChecked(True)
            if task.due_date:
                self.no_date_check.setChecked(False)
                self.date_edit.setDate(QDate(
                    task.due_date.year,
                    task.due_date.month,
                    task.due_date.day,
                ))
                if task.due_date.day == 1:
                    self.month_only_check.setChecked(True)
            else:
                self.no_date_check.setChecked(True)
        else:
            self.radio_short.setChecked(True)

        self._on_type_changed()

        if task.priority in self._prio_buttons:
            self._prio_buttons[task.priority].setChecked(True)
            self._update_prio_styles()

        if task.description:
            self.desc_edit.setPlainText(task.description)

    # ========== 保存 ==========

    def _on_save(self):
        title = self.title_input.text().strip()
        if not title:
            self._show_warning("请输入任务标题")
            self.title_input.setFocus()
            return
        self.accept()

    def _show_warning(self, message: str):
        """显示主题适配的警告提示"""
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(280)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(10, 10, 10, 10)

        box = QFrame()
        box.setObjectName("ConfirmDialog")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 80))
        box.setGraphicsEffect(shadow)

        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)

        msg = QLabel(message)
        msg.setObjectName("ConfirmMsg")
        msg.setAlignment(Qt.AlignCenter)
        lay.addWidget(msg)

        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("EditorSaveBtn")
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFixedHeight(30)
        ok_btn.clicked.connect(dlg.accept)
        lay.addWidget(ok_btn)

        outer.addWidget(box)
        dlg.setStyleSheet(self.styleSheet())
        dlg.exec_()

    # ========== 数据获取 ==========

    def get_data(self) -> dict:
        if self.radio_weekly.isChecked():
            task_type = Task.TYPE_WEEKLY
            due_date = self._get_weekday_date()
        elif self.radio_long.isChecked():
            task_type = Task.TYPE_LONG_TERM
            if self.no_date_check.isChecked():
                due_date = None
            else:
                qdate = self.date_edit.date()
                if self.month_only_check.isChecked():
                    due_date = date(qdate.year(), qdate.month(), 1)
                else:
                    due_date = date(qdate.year(), qdate.month(), qdate.day())
        else:
            task_type = Task.TYPE_SHORT_TERM
            due_date = None

        priority = "medium"
        checked_btn = self.prio_group.checkedButton()
        if checked_btn:
            priority = checked_btn.property("prio_value")

        return {
            "title": self.title_input.text().strip(),
            "task_type": task_type,
            "due_date": due_date,
            "priority": priority,
            "description": self.desc_edit.toPlainText().strip() or None,
            "tag_ids": list(self._selected_tag_ids),
        }

    def get_new_tag_name(self) -> Optional[str]:
        return None

    def _on_add_new_tag(self):
        name = self.new_tag_input.text().strip().lstrip("#").strip()
        if not name:
            return
        if hasattr(self, "_add_tag_callback") and self._add_tag_callback:
            new_tag = self._add_tag_callback(name)
            if new_tag:
                self._tags.append(new_tag)
                self._selected_tag_ids.add(new_tag.id)
                self._rebuild_tag_chips()
                self.new_tag_input.clear()

    def set_add_tag_callback(self, callback):
        self._add_tag_callback = callback

    def _rebuild_tag_chips(self):
        for i in range(self.tag_flow_layout.count()):
            item = self.tag_flow_layout.itemAt(i)
            if item and item.widget() is None:
                self.tag_flow_layout.removeItem(item)
                break

        for chip in self._tag_chips:
            self.tag_flow_layout.removeWidget(chip)
            chip.deleteLater()
        self._tag_chips.clear()

        for tag in self._tags:
            selected = tag.id in self._selected_tag_ids
            chip = TagChip(tag, selected=selected)
            chip.toggled_tag.connect(self._on_tag_toggled)
            self.tag_flow_layout.addWidget(chip)
            self._tag_chips.append(chip)

        self.tag_flow_layout.addStretch()

    # ========== 事件过滤：日历弹窗样式 ==========

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self.date_edit and event.type() == QEvent.MouseButtonPress:
            cal = self.date_edit.calendarWidget()
            if cal:
                cal.setStyleSheet(self.styleSheet())
                popup = cal.window()
                if popup and popup is not self:
                    popup.setWindowFlags(
                        popup.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
                    )
                    popup.setAttribute(Qt.WA_TranslucentBackground)
        return super().eventFilter(obj, event)

    # ========== 键盘事件 ==========

    def keyPressEvent(self, event):
        """Enter/Return 视为保存（当焦点不在多行文本框中时）"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 如果焦点在多行描述框，允许换行
            if self.desc_edit.hasFocus():
                return super().keyPressEvent(event)
            # 其他情况下，视为保存
            self._on_save()
            return
        super().keyPressEvent(event)

    # ========== 拖拽移动弹窗 ==========

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

"""第四阶段测试 - 任务编辑弹窗、右键菜单、状态流转"""

import sys
from pathlib import Path
from datetime import date, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QDate

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.models.tag import Tag
from src.services.task_service import TaskService
from src.services.tag_service import TagService
from src.ui.task_editor import TaskEditorDialog, TagChip
from src.ui.task_item import TaskItemWidget, STATUS_FLOW

# 需要 QApplication 实例才能创建 QWidget
app = QApplication.instance() or QApplication(sys.argv)


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _make_tags(session):
    svc = TagService(session)
    t1 = svc.create_tag("论文", "#EF4444")
    t2 = svc.create_tag("生活", "#10B981")
    t3 = svc.create_tag("助教", "#3B82F6")
    return [t1, t2, t3]


def _make_task(session, tags):
    svc = TaskService(session)
    task = svc.create_task(
        "完成论文初稿",
        task_type=Task.TYPE_LONG_TERM,
        due_date=date.today() + timedelta(days=5),
        priority="high",
        description="写第一章和第二章",
        tag_ids=[tags[0].id],
    )
    return task


# ============================================================
# 1. TaskEditorDialog 测试 - 新建模式
# ============================================================
def test_editor_new_mode():
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)
    assert dialog.windowTitle() == "新建任务"
    assert dialog.title_input.text() == ""
    assert dialog.radio_short.isChecked()
    assert not dialog.radio_long.isChecked()
    assert dialog.desc_edit.toPlainText() == ""
    session.close()
    print("[PASS] test_editor_new_mode - 新建模式初始化正确")


def test_editor_edit_mode():
    session = _make_session()
    tags = _make_tags(session)
    task = _make_task(session, tags)

    dialog = TaskEditorDialog(tags, task=task)
    assert dialog.windowTitle() == "编辑任务"
    assert dialog.title_input.text() == "完成论文初稿"
    assert dialog.radio_long.isChecked()
    assert dialog.desc_edit.toPlainText() == "写第一章和第二章"

    # 检查优先级
    checked = dialog.prio_group.checkedButton()
    assert checked is not None
    assert checked.property("prio_value") == "high"

    # 检查日期
    qdate = dialog.date_edit.date()
    expected = date.today() + timedelta(days=5)
    assert qdate.year() == expected.year
    assert qdate.month() == expected.month
    assert qdate.day() == expected.day

    session.close()
    print("[PASS] test_editor_edit_mode - 编辑模式加载任务数据正确")


def test_editor_tag_selection():
    session = _make_session()
    tags = _make_tags(session)
    task = _make_task(session, tags)  # 有标签 "论文"

    dialog = TaskEditorDialog(tags, task=task)

    # 论文标签应该被选中
    assert tags[0].id in dialog._selected_tag_ids
    # 其他标签未选中
    assert tags[1].id not in dialog._selected_tag_ids

    # 检查 TagChip 数量
    assert len(dialog._tag_chips) == 3

    session.close()
    print("[PASS] test_editor_tag_selection - 标签选择状态正确")


def test_editor_tag_toggle():
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)
    assert len(dialog._selected_tag_ids) == 0

    # 模拟选中标签
    dialog._on_tag_toggled(tags[0].id, True)
    assert tags[0].id in dialog._selected_tag_ids

    dialog._on_tag_toggled(tags[1].id, True)
    assert tags[1].id in dialog._selected_tag_ids
    assert len(dialog._selected_tag_ids) == 2

    # 取消选中
    dialog._on_tag_toggled(tags[0].id, False)
    assert tags[0].id not in dialog._selected_tag_ids
    assert len(dialog._selected_tag_ids) == 1

    session.close()
    print("[PASS] test_editor_tag_toggle - 标签切换逻辑正确")


def test_editor_get_data_short_term():
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)
    dialog.title_input.setText("买咖啡")
    dialog.radio_short.setChecked(True)
    dialog._prio_buttons["low"].setChecked(True)
    dialog._on_tag_toggled(tags[1].id, True)
    dialog.desc_edit.setPlainText("星巴克")

    data = dialog.get_data()
    assert data["title"] == "买咖啡"
    assert data["task_type"] == Task.TYPE_SHORT_TERM
    assert data["due_date"] is None
    assert data["priority"] == "low"
    assert data["description"] == "星巴克"
    assert tags[1].id in data["tag_ids"]

    session.close()
    print("[PASS] test_editor_get_data_short_term - 短期任务数据获取正确")


def test_editor_get_data_long_term():
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)
    dialog.title_input.setText("提交论文")
    dialog.radio_long.setChecked(True)
    target_date = date.today() + timedelta(days=10)
    dialog.date_edit.setDate(QDate(target_date.year, target_date.month, target_date.day))
    dialog._prio_buttons["high"].setChecked(True)

    data = dialog.get_data()
    assert data["title"] == "提交论文"
    assert data["task_type"] == Task.TYPE_LONG_TERM
    assert data["due_date"] == target_date
    assert data["priority"] == "high"

    session.close()
    print("[PASS] test_editor_get_data_long_term - 长期任务数据获取正确")


def test_editor_date_visibility():
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)
    dialog.show()

    # 短期任务时日期和周几都不可见
    dialog.radio_short.setChecked(True)
    dialog._on_type_changed()
    app.processEvents()
    assert not dialog.date_edit.isVisible()
    assert not dialog.date_label.isVisible()
    assert not dialog.weekday_combo.isVisible()

    # 本周计划时周几可见，日期不可见
    dialog.radio_weekly.setChecked(True)
    dialog._on_type_changed()
    app.processEvents()
    assert dialog.weekday_combo.isVisible()
    assert not dialog.date_edit.isVisible()

    # 长期任务时日期可见，周几不可见
    dialog.radio_long.setChecked(True)
    dialog._on_type_changed()
    app.processEvents()
    assert dialog.date_edit.isVisible()
    assert dialog.date_label.isVisible()
    assert not dialog.weekday_combo.isVisible()

    dialog.close()
    session.close()
    print("[PASS] test_editor_date_visibility - 日期选择器可见性切换正确")


# ============================================================
# 2. TagChip 测试
# ============================================================
def test_tag_chip_creation():
    session = _make_session()
    tags = _make_tags(session)

    chip = TagChip(tags[0], selected=False)
    assert chip.text() == "#论文"
    assert not chip.is_selected()

    chip2 = TagChip(tags[1], selected=True)
    assert chip2.text() == "#生活"
    assert chip2.is_selected()

    session.close()
    print("[PASS] test_tag_chip_creation - 标签Chip创建正确")


def test_tag_chip_toggle():
    session = _make_session()
    tags = _make_tags(session)

    chip = TagChip(tags[0], selected=False)
    received = []
    chip.toggled_tag.connect(lambda tid, sel: received.append((tid, sel)))

    # 模拟点击选中
    chip.setChecked(True)
    chip._on_clicked()
    assert chip.is_selected()
    assert received[-1] == (tags[0].id, True)

    # 模拟取消选中
    chip.setChecked(False)
    chip._on_clicked()
    assert not chip.is_selected()
    assert received[-1] == (tags[0].id, False)

    session.close()
    print("[PASS] test_tag_chip_toggle - 标签Chip切换正确")


# ============================================================
# 3. 右键菜单测试（TaskItemWidget）
# ============================================================
def test_task_item_context_menu_exists():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("菜单测试", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    # 验证 contextMenuEvent 方法存在
    assert hasattr(item, 'contextMenuEvent')
    assert callable(item.contextMenuEvent)
    session.close()
    print("[PASS] test_task_item_context_menu_exists - 右键菜单方法存在")


def test_task_item_set_status():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("状态测试", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    received = []
    item.status_changed.connect(lambda tid, s: received.append((tid, s)))

    # 通过右键菜单的 _set_status 直接设置状态
    item._set_status("done")
    assert received[-1] == (task.id, "done")
    assert item.task.status == "done"
    assert item.status_btn.objectName() == "StatusCircleDone"
    assert item.title_label.objectName() == "TaskTitleDone"

    item._set_status("cancelled")
    assert received[-1] == (task.id, "cancelled")
    assert item.task.status == "cancelled"

    item._set_status("todo")
    assert received[-1] == (task.id, "todo")
    assert item.task.status == "todo"
    assert item.status_btn.objectName() == "StatusCircle"
    assert item.title_label.objectName() == "TaskTitle"

    session.close()
    print("[PASS] test_task_item_set_status - 右键菜单状态切换正确")


def test_task_item_delete_signal():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("删除测试", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    received = []
    item.delete_requested.connect(lambda tid: received.append(tid))

    # 模拟发射删除信号
    item.delete_requested.emit(task.id)
    assert len(received) == 1
    assert received[0] == task.id

    session.close()
    print("[PASS] test_task_item_delete_signal - 删除信号正确")


# ============================================================
# 4. 完整工作流测试
# ============================================================
def test_full_create_workflow():
    """模拟完整的创建任务流程"""
    session = _make_session()
    tags = _make_tags(session)
    task_svc = TaskService(session)

    # 打开新建对话框
    dialog = TaskEditorDialog(tags, task=None)
    dialog.title_input.setText("准备考试")
    dialog.radio_long.setChecked(True)
    target_date = date.today() + timedelta(days=14)
    dialog.date_edit.setDate(QDate(target_date.year, target_date.month, target_date.day))
    dialog._prio_buttons["high"].setChecked(True)
    dialog._on_tag_toggled(tags[0].id, True)
    dialog._on_tag_toggled(tags[2].id, True)
    dialog.desc_edit.setPlainText("复习第1-5章")

    # 获取数据
    data = dialog.get_data()
    assert data["title"] == "准备考试"
    assert data["task_type"] == Task.TYPE_LONG_TERM
    assert data["due_date"] == target_date
    assert data["priority"] == "high"
    assert len(data["tag_ids"]) == 2
    assert data["description"] == "复习第1-5章"

    # 用 TaskService 创建
    task = task_svc.create_task(**data)
    assert task.id is not None
    assert task.title == "准备考试"
    assert task.task_type == Task.TYPE_LONG_TERM
    assert task.priority == "high"
    assert len(task.tags) == 2

    session.close()
    print("[PASS] test_full_create_workflow - 完整创建工作流正确")


def test_full_edit_workflow():
    """模拟完整的编辑任务流程"""
    session = _make_session()
    tags = _make_tags(session)
    task_svc = TaskService(session)

    # 先创建一个任务
    task = task_svc.create_task(
        "原始标题", task_type=Task.TYPE_SHORT_TERM,
        priority="low", tag_ids=[tags[0].id],
    )

    # 打开编辑对话框
    dialog = TaskEditorDialog(tags, task=task)
    assert dialog.title_input.text() == "原始标题"

    # 修改数据
    dialog.title_input.setText("修改后的标题")
    dialog.radio_long.setChecked(True)
    new_date = date.today() + timedelta(days=7)
    dialog.date_edit.setDate(QDate(new_date.year, new_date.month, new_date.day))
    dialog._prio_buttons["medium"].setChecked(True)
    dialog._on_tag_toggled(tags[0].id, False)  # 取消论文
    dialog._on_tag_toggled(tags[1].id, True)   # 选中生活

    data = dialog.get_data()
    task_svc.update_task(task.id, **data)

    # 验证更新
    updated = task_svc.get_task(task.id)
    assert updated.title == "修改后的标题"
    assert updated.task_type == Task.TYPE_LONG_TERM
    assert updated.due_date == new_date
    assert updated.priority == "medium"
    tag_names = {t.name for t in updated.tags}
    assert "生活" in tag_names
    assert "论文" not in tag_names

    session.close()
    print("[PASS] test_full_edit_workflow - 完整编辑工作流正确")


def test_editor_new_tag_callback():
    """测试编辑弹窗中标签选择机制（标签新建已移至侧栏）"""
    session = _make_session()
    tags = _make_tags(session)

    dialog = TaskEditorDialog(tags, task=None)

    # 编辑器应有标签chip但无新建输入框
    assert len(dialog._tags) == 3
    assert len(dialog._tag_chips) == 3
    assert not hasattr(dialog, 'new_tag_input'), "编辑器不应包含新建标签输入框"

    # 模拟选中标签
    dialog._on_tag_toggled(tags[0].id, True)
    assert tags[0].id in dialog._selected_tag_ids

    # 模拟取消选中
    dialog._on_tag_toggled(tags[0].id, False)
    assert tags[0].id not in dialog._selected_tag_ids

    session.close()
    print("[PASS] test_editor_new_tag_callback - 标签选择机制正确")


# ============================================================
# 5. QSS 样式测试
# ============================================================
def test_editor_styles_in_theme():
    from src.ui.styles.themes import get_theme, build_stylesheet, get_theme_keys
    for key in get_theme_keys():
        theme = get_theme(key)
        qss = build_stylesheet(theme)
        assert "EditorContainer" in qss
        assert "EditorTitle" in qss
        assert "EditorInput" in qss
        assert "EditorSaveBtn" in qss
        assert "EditorCancelBtn" in qss
        assert "QMenu" in qss
    print("[PASS] test_editor_styles_in_theme - 编辑弹窗和菜单样式存在于主题中")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # TaskEditor 新建/编辑
        test_editor_new_mode,
        test_editor_edit_mode,
        test_editor_tag_selection,
        test_editor_tag_toggle,
        test_editor_get_data_short_term,
        test_editor_get_data_long_term,
        test_editor_date_visibility,
        # TagChip
        test_tag_chip_creation,
        test_tag_chip_toggle,
        # 右键菜单
        test_task_item_context_menu_exists,
        test_task_item_set_status,
        test_task_item_delete_signal,
        # 完整工作流
        test_full_create_workflow,
        test_full_edit_workflow,
        test_editor_new_tag_callback,
        # 样式
        test_editor_styles_in_theme,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

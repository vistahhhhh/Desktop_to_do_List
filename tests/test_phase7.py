"""第七阶段测试 - 分任务功能"""

import sys
from pathlib import Path
from datetime import date, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.services.task_service import TaskService
from src.services.filter_service import FilterService
from src.ui.task_item import TaskItemWidget, SubtaskItemWidget, SubtaskSection
from src.ui.task_list import TaskListWidget
from src.ui.styles.themes import get_theme, build_stylesheet, get_theme_keys

app = QApplication.instance() or QApplication(sys.argv)


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


# ============================================================
# 1. Task 模型 parent_id 字段
# ============================================================
def test_task_parent_id_field():
    """Task 有 parent_id 字段且可赋值"""
    session = _make_session()
    parent = Task(title="父任务", task_type=Task.TYPE_SHORT_TERM)
    session.add(parent)
    session.commit()

    sub = Task(title="子任务", task_type=Task.TYPE_SHORT_TERM, parent_id=parent.id)
    session.add(sub)
    session.commit()

    assert sub.parent_id == parent.id
    session.close()
    print("[PASS] test_task_parent_id_field - parent_id 字段存在且可赋值")


def test_task_subtasks_relationship():
    """Task.subtasks 关系正确返回子任务"""
    session = _make_session()
    parent = Task(title="父任务", task_type=Task.TYPE_SHORT_TERM)
    session.add(parent)
    session.commit()

    s1 = Task(title="分任务A", task_type=Task.TYPE_SHORT_TERM, parent_id=parent.id)
    s2 = Task(title="分任务B", task_type=Task.TYPE_SHORT_TERM, parent_id=parent.id)
    session.add_all([s1, s2])
    session.commit()

    session.expire(parent)
    assert len(parent.subtasks) == 2
    titles = {s.title for s in parent.subtasks}
    assert "分任务A" in titles
    assert "分任务B" in titles
    session.close()
    print("[PASS] test_task_subtasks_relationship - subtasks 关系正确")


# ============================================================
# 2. TaskService 分任务 CRUD
# ============================================================
def test_create_subtask():
    """create_subtask 创建分任务，继承父任务类型"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)

    sub = svc.create_subtask(parent.id, "分任务1")
    assert sub.id is not None
    assert sub.parent_id == parent.id
    assert sub.task_type == Task.TYPE_SHORT_TERM
    assert sub.status == "todo"
    session.close()
    print("[PASS] test_create_subtask - 创建分任务正确")


def test_create_subtask_nonexistent_parent():
    """create_subtask 对不存在的父任务抛出 ValueError"""
    session = _make_session()
    svc = TaskService(session)
    try:
        svc.create_subtask(999, "孤立子任务")
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "父任务" in str(e)
    session.close()
    print("[PASS] test_create_subtask_nonexistent_parent - 父任务不存在时抛出异常")


def test_create_subtask_empty_title():
    """create_subtask 空标题抛出 ValueError"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    try:
        svc.create_subtask(parent.id, "")
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass
    session.close()
    print("[PASS] test_create_subtask_empty_title - 空标题时抛出异常")


def test_get_subtasks():
    """get_subtasks 返回指定任务的分任务列表"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    other = svc.create_task("其他任务", task_type=Task.TYPE_SHORT_TERM)

    svc.create_subtask(parent.id, "分1")
    svc.create_subtask(parent.id, "分2")
    svc.create_subtask(other.id, "其他分1")

    subs = svc.get_subtasks(parent.id)
    assert len(subs) == 2
    titles = {s.title for s in subs}
    assert "分1" in titles
    assert "分2" in titles
    assert "其他分1" not in titles
    session.close()
    print("[PASS] test_get_subtasks - 获取分任务列表正确")


def test_get_subtasks_excludes_deleted():
    """get_subtasks 不返回已删除的分任务"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    s1 = svc.create_subtask(parent.id, "正常分任务")
    s2 = svc.create_subtask(parent.id, "已删分任务")
    svc.delete_task(s2.id)

    subs = svc.get_subtasks(parent.id)
    assert len(subs) == 1
    assert subs[0].title == "正常分任务"
    session.close()
    print("[PASS] test_get_subtasks_excludes_deleted - 分任务排除已删除项")


def test_delete_task_cascades_subtasks():
    """delete_task 父任务软删除时级联软删除所有分任务"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    s1 = svc.create_subtask(parent.id, "分1")
    s2 = svc.create_subtask(parent.id, "分2")

    svc.delete_task(parent.id)

    # 父任务和分任务都应被软删除
    assert svc.get_task(parent.id) is None
    deleted_s1 = session.query(Task).filter_by(id=s1.id).first()
    deleted_s2 = session.query(Task).filter_by(id=s2.id).first()
    assert deleted_s1.is_deleted == 1
    assert deleted_s2.is_deleted == 1
    session.close()
    print("[PASS] test_delete_task_cascades_subtasks - 父任务删除时级联删除分任务")


# ============================================================
# 3. FilterService 不含分任务
# ============================================================
def test_filter_excludes_subtasks():
    """FilterService 的所有智能清单不返回分任务"""
    session = _make_session()
    svc = TaskService(session)
    fs = FilterService(session)
    today = date.today()

    # 今日任务 + 分任务
    parent_short = svc.create_task("今日父任务", task_type=Task.TYPE_SHORT_TERM)
    svc.create_subtask(parent_short.id, "今日分任务")

    # 周任务 + 分任务
    parent_week = svc.create_task("周父任务", task_type=Task.TYPE_WEEKLY,
                                   due_date=today + timedelta(days=1))
    svc.create_subtask(parent_week.id, "周分任务")

    # 长期任务 + 分任务
    parent_long = svc.create_task("长期父任务", task_type=Task.TYPE_LONG_TERM,
                                   due_date=today + timedelta(days=30))
    svc.create_subtask(parent_long.id, "长期分任务")

    today_tasks = fs.get_today_tasks()
    week_tasks = fs.get_week_tasks()
    long_tasks = fs.get_long_term_tasks()

    # 分任务不应出现在任何列表中
    for tasks, name in [(today_tasks, "today"), (week_tasks, "week"), (long_tasks, "long")]:
        subtitles = {t.title for t in tasks if t.parent_id is not None}
        assert len(subtitles) == 0, f"{name} 列表不应含分任务，但含: {subtitles}"

    # 父任务应存在
    assert any(t.title == "今日父任务" for t in today_tasks)
    assert any(t.title == "周父任务" for t in week_tasks)
    assert any(t.title == "长期父任务" for t in long_tasks)

    session.close()
    print("[PASS] test_filter_excludes_subtasks - 智能清单不含分任务")


def test_history_excludes_subtasks():
    """get_history_tasks 不包含分任务"""
    session = _make_session()
    svc = TaskService(session)
    yesterday = date.today() - timedelta(days=1)

    parent = Task(title="历史父任务", task_type=Task.TYPE_SHORT_TERM, task_date=yesterday)
    session.add(parent)
    session.commit()

    sub = Task(title="历史分任务", task_type=Task.TYPE_SHORT_TERM,
               task_date=yesterday, parent_id=parent.id)
    session.add(sub)
    session.commit()

    grouped = svc.get_history_tasks()
    titles = {t.title for tasks in grouped.values() for t in tasks}
    assert "历史父任务" in titles
    assert "历史分任务" not in titles
    session.close()
    print("[PASS] test_history_excludes_subtasks - 历史记录不含分任务")


# ============================================================
# 4. UI 组件
# ============================================================
def test_subtask_item_widget():
    """SubtaskItemWidget 正确显示分任务状态"""
    session = _make_session()
    sub = Task(title="分任务测试", task_type=Task.TYPE_SHORT_TERM, status="todo")
    session.add(sub)
    session.commit()

    item = SubtaskItemWidget(sub)
    assert item.check_btn.objectName() == "SubtaskCheck"
    assert item.title_label.objectName() == "SubtaskTitle"

    # 切换到完成
    received = []
    item.status_changed.connect(lambda sid, s: received.append((sid, s)))
    item._toggle_status()
    assert sub.status == "done"
    assert item.check_btn.objectName() == "SubtaskCheckDone"
    assert item.title_label.objectName() == "SubtaskTitleDone"
    assert len(received) == 1
    session.close()
    print("[PASS] test_subtask_item_widget - SubtaskItemWidget 状态切换正确")


def test_subtask_section_signals():
    """SubtaskSection 信号正确发射"""
    session = _make_session()
    parent_task = Task(title="父任务", task_type=Task.TYPE_SHORT_TERM)
    session.add(parent_task)
    sub = Task(title="分任务", task_type=Task.TYPE_SHORT_TERM)
    session.add(sub)
    session.commit()

    section = SubtaskSection(parent_task.id, [sub])

    created = []
    section.subtask_create_requested.connect(lambda pid, t: created.append((pid, t)))

    # 通过 focus_input 弹出内联输入框，再模拟输入确认
    section.focus_input()
    assert section._inline_input is not None
    section._inline_input.setText("新分任务")
    section._confirm_input(section._inline_input)
    assert created == [(parent_task.id, "新分任务")]
    assert section._inline_input is None
    session.close()
    print("[PASS] test_subtask_section_signals - SubtaskSection 信号正确")


def test_task_item_with_subtasks():
    """TaskItemWidget 有分任务时显示折叠/展开按钮（含进度）"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    s1 = svc.create_subtask(parent.id, "分1")
    svc.create_subtask(parent.id, "分2")
    svc.update_status(s1.id, "done")

    subs = svc.get_subtasks(parent.id)
    item = TaskItemWidget(parent, subtasks=subs)

    assert item._toggle_btn is not None
    assert item._toggle_btn.text() == "▼ 1/2"
    assert item._subtask_section is not None
    session.close()
    print("[PASS] test_task_item_with_subtasks - 折叠按钮和进度正确显示")


def test_task_item_no_subtasks():
    """TaskItemWidget 无分任务时无折叠按钮和分任务区块"""
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("普通任务", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    assert item._toggle_btn is None
    assert item._subtask_section is None
    session.close()
    print("[PASS] test_task_item_no_subtasks - 无分任务时无折叠按钮")


def test_task_item_progress_realtime():
    """分任务状态切换后，折叠按钮进度立即更新"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    svc.create_subtask(parent.id, "分1")
    svc.create_subtask(parent.id, "分2")

    subs = svc.get_subtasks(parent.id)
    item = TaskItemWidget(parent, subtasks=subs)
    assert item._toggle_btn.text() == "▼ 0/2"

    # 勾选第一个分任务
    sub_widget = item._subtask_section._item_widgets[0]
    sub_widget._toggle_status()
    assert item._toggle_btn.text() == "▼ 1/2"

    # 再次取消
    sub_widget._toggle_status()
    assert item._toggle_btn.text() == "▼ 0/2"
    session.close()
    print("[PASS] test_task_item_progress_realtime - 进度实时更新正确")


def test_task_item_collapse_expand():
    """折叠/展开分任务区块功能"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    svc.create_subtask(parent.id, "分1")
    subs = svc.get_subtasks(parent.id)

    item = TaskItemWidget(parent, subtasks=subs)
    assert item._subtasks_expanded is True
    assert not item._subtask_section.isHidden()
    assert "▼" in item._toggle_btn.text()

    # 折叠
    item._toggle_subtask_section()
    assert item._subtasks_expanded is False
    assert item._subtask_section.isHidden()
    assert "▶" in item._toggle_btn.text()

    # 展开
    item._toggle_subtask_section()
    assert item._subtasks_expanded is True
    assert not item._subtask_section.isHidden()
    assert "▼" in item._toggle_btn.text()
    session.close()
    print("[PASS] test_task_item_collapse_expand - 折叠展开功能正确")


def test_task_item_subtask_signals():
    """TaskItemWidget 正确转发分任务信号（通过 + 按钮插入输入）"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    svc.create_subtask(parent.id, "分任务")
    subs = svc.get_subtasks(parent.id)

    item = TaskItemWidget(parent, subtasks=subs)

    creates = []
    item.subtask_create_requested.connect(lambda pid, t: creates.append((pid, t)))

    # 点击分任务的 + 按钮，弹出内联输入
    sub_widget = item._subtask_section._item_widgets[0]
    sub_widget.add_after_requested.emit(sub_widget.subtask.id)
    assert item._subtask_section._inline_input is not None

    # 输入并确认
    item._subtask_section._inline_input.setText("新分任务")
    item._subtask_section._confirm_input(item._subtask_section._inline_input)
    assert creates == [(parent.id, "新分任务")]
    session.close()
    print("[PASS] test_task_item_subtask_signals - TaskItemWidget 转发分任务信号正确")


def test_task_list_subtasks_map():
    """TaskListWidget 接受 subtasks_map 并正确渲染"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)
    svc.create_subtask(parent.id, "分1")
    subs = svc.get_subtasks(parent.id)

    widget = TaskListWidget()
    widget.set_tasks([parent], subtasks_map={parent.id: subs})

    item = widget._task_widgets[parent.id]
    assert item._subtask_section is not None
    assert item._toggle_btn is not None
    assert item._toggle_btn.text() == "▼ 0/1"
    session.close()
    print("[PASS] test_task_list_subtasks_map - TaskListWidget 正确处理分任务映射")


def test_task_list_subtask_signals_forwarded():
    """TaskListWidget 正确转发 subtask_create_requested"""
    session = _make_session()
    svc = TaskService(session)
    parent = svc.create_task("父任务", task_type=Task.TYPE_SHORT_TERM)

    widget = TaskListWidget()
    widget.set_tasks([parent])

    # 触发右键"添加分任务"
    item = widget._task_widgets[parent.id]
    item._show_subtask_input()
    assert item._subtask_section is not None
    assert item._subtask_section._inline_input is not None

    creates = []
    widget.subtask_create_requested.connect(lambda pid, t: creates.append((pid, t)))
    item._subtask_section._inline_input.setText("测试分任务")
    item._subtask_section._confirm_input(item._subtask_section._inline_input)
    assert creates == [(parent.id, "测试分任务")]
    session.close()
    print("[PASS] test_task_list_subtask_signals_forwarded - TaskListWidget 转发分任务创建信号")


# ============================================================
# 5. 主题样式包含分任务QSS
# ============================================================
def test_subtask_styles_in_all_themes():
    """所有主题包含分任务相关样式标识符"""
    required = [
        "SubtaskItem", "SubtaskCheck", "SubtaskCheckDone",
        "SubtaskTitle", "SubtaskTitleDone", "SubtaskToggle", "SubtaskAddBtn", "SubtaskInput",
    ]
    for key in get_theme_keys():
        theme = get_theme(key)
        qss = build_stylesheet(theme)
        for selector in required:
            assert selector in qss, f"主题 {key} 缺少样式 #{selector}"
    print("[PASS] test_subtask_styles_in_all_themes - 所有主题包含分任务样式")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # 模型
        test_task_parent_id_field,
        test_task_subtasks_relationship,
        # TaskService
        test_create_subtask,
        test_create_subtask_nonexistent_parent,
        test_create_subtask_empty_title,
        test_get_subtasks,
        test_get_subtasks_excludes_deleted,
        test_delete_task_cascades_subtasks,
        # FilterService
        test_filter_excludes_subtasks,
        test_history_excludes_subtasks,
        # UI
        test_subtask_item_widget,
        test_subtask_section_signals,
        test_task_item_with_subtasks,
        test_task_item_no_subtasks,
        test_task_item_progress_realtime,
        test_task_item_collapse_expand,
        test_task_item_subtask_signals,
        test_task_list_subtasks_map,
        test_task_list_subtask_signals_forwarded,
        # 样式
        test_subtask_styles_in_all_themes,
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

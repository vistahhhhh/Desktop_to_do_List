"""第六阶段测试 - 新功能：task_date、移交今日、待办回顾、周计划过期、侧栏布局"""

import sys
from pathlib import Path
from datetime import date, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication, QScrollArea
from PyQt5.QtCore import Qt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.models.tag import Tag
from src.services.task_service import TaskService
from src.services.tag_service import TagService
from src.services.filter_service import FilterService
from src.ui.tag_sidebar import TagSidebar, TagButton, SMART_LISTS
from src.ui.task_item import TaskItemWidget
from src.ui.task_list import TaskListWidget
from src.ui.styles.themes import get_theme, build_stylesheet, get_theme_keys

app = QApplication.instance() or QApplication(sys.argv)


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


# ============================================================
# 1. Task.task_date 字段测试
# ============================================================
def test_task_date_field_exists():
    """Task 模型有 task_date 字段"""
    session = _make_session()
    task = Task(title="测试", task_type=Task.TYPE_SHORT_TERM, task_date=date.today())
    session.add(task)
    session.commit()
    assert task.task_date == date.today()
    session.close()
    print("[PASS] test_task_date_field_exists - task_date 字段存在且可赋值")


def test_task_date_auto_set_on_create():
    """TaskService.create_task 自动为 short_term 设置 task_date"""
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("今日任务", task_type=Task.TYPE_SHORT_TERM)
    assert task.task_date == date.today()
    session.close()
    print("[PASS] test_task_date_auto_set_on_create - short_term 创建时自动设置 task_date")


def test_task_date_none_for_other_types():
    """非 short_term 任务的 task_date 为 None"""
    session = _make_session()
    svc = TaskService(session)
    weekly = svc.create_task("周任务", task_type=Task.TYPE_WEEKLY,
                             due_date=date.today() + timedelta(days=1))
    long_term = svc.create_task("长期", task_type=Task.TYPE_LONG_TERM,
                                due_date=date.today() + timedelta(days=30))
    assert weekly.task_date is None
    assert long_term.task_date is None
    session.close()
    print("[PASS] test_task_date_none_for_other_types - 非 short_term 的 task_date 为 None")


# ============================================================
# 2. carry_forward 功能测试
# ============================================================
def test_carry_forward():
    """carry_forward 将 task_date 更新为今天"""
    session = _make_session()
    svc = TaskService(session)
    # 手动创建一个昨天的任务
    task = Task(
        title="昨天的任务",
        task_type=Task.TYPE_SHORT_TERM,
        task_date=date.today() - timedelta(days=1),
    )
    session.add(task)
    session.commit()
    assert task.task_date == date.today() - timedelta(days=1)

    result = svc.carry_forward(task.id)
    assert result is not None
    assert result.task_date == date.today()
    session.close()
    print("[PASS] test_carry_forward - 移交今日功能正确")


def test_carry_forward_nonexistent():
    """carry_forward 对不存在的 task 返回 None"""
    session = _make_session()
    svc = TaskService(session)
    assert svc.carry_forward(999) is None
    session.close()
    print("[PASS] test_carry_forward_nonexistent - 不存在的任务返回 None")


# ============================================================
# 3. get_history_tasks 测试
# ============================================================
def test_get_history_tasks():
    """get_history_tasks 按日期分组返回过去的 short_term 任务"""
    session = _make_session()
    svc = TaskService(session)
    yesterday = date.today() - timedelta(days=1)
    two_days_ago = date.today() - timedelta(days=2)

    # 昨天的任务
    t1 = Task(title="昨天A", task_type=Task.TYPE_SHORT_TERM, task_date=yesterday)
    t2 = Task(title="昨天B", task_type=Task.TYPE_SHORT_TERM, task_date=yesterday,
              status="done")
    # 前天的任务
    t3 = Task(title="前天C", task_type=Task.TYPE_SHORT_TERM, task_date=two_days_ago)
    # 今天的任务（不应出现在历史中）
    t4 = Task(title="今天D", task_type=Task.TYPE_SHORT_TERM, task_date=date.today())
    session.add_all([t1, t2, t3, t4])
    session.commit()

    grouped = svc.get_history_tasks()
    assert yesterday in grouped
    assert two_days_ago in grouped
    assert date.today() not in grouped
    assert len(grouped[yesterday]) == 2
    assert len(grouped[two_days_ago]) == 1
    session.close()
    print("[PASS] test_get_history_tasks - 历史任务按日期分组正确")


def test_get_history_excludes_deleted():
    """get_history_tasks 不包含已删除的任务"""
    session = _make_session()
    svc = TaskService(session)
    yesterday = date.today() - timedelta(days=1)
    t1 = Task(title="正常", task_type=Task.TYPE_SHORT_TERM, task_date=yesterday)
    t2 = Task(title="已删", task_type=Task.TYPE_SHORT_TERM, task_date=yesterday,
              is_deleted=1)
    session.add_all([t1, t2])
    session.commit()

    grouped = svc.get_history_tasks()
    assert yesterday in grouped
    titles = {t.title for t in grouped[yesterday]}
    assert "正常" in titles
    assert "已删" not in titles
    session.close()
    print("[PASS] test_get_history_excludes_deleted - 历史排除已删除任务")


# ============================================================
# 4. FilterService 今日任务含遗留测试
# ============================================================
def test_filter_today_with_carryover():
    """get_today_tasks 返回今天任务 + 遗留未完成任务"""
    session = _make_session()
    svc = TaskService(session)
    yesterday = date.today() - timedelta(days=1)

    # 今天的任务
    svc.create_task("今天A", task_type=Task.TYPE_SHORT_TERM)
    # 昨天未完成（应作为遗留出现）
    t_old = Task(title="昨天未完", task_type=Task.TYPE_SHORT_TERM,
                 task_date=yesterday, status="todo")
    session.add(t_old)
    # 昨天已完成（不应出现）
    t_done = Task(title="昨天已完", task_type=Task.TYPE_SHORT_TERM,
                  task_date=yesterday, status="done")
    session.add(t_done)
    session.commit()

    fs = FilterService(session)
    tasks = fs.get_today_tasks()
    titles = {t.title for t in tasks}
    assert "今天A" in titles
    assert "昨天未完" in titles
    assert "昨天已完" not in titles
    session.close()
    print("[PASS] test_filter_today_with_carryover - 今日任务含遗留未完成")


def test_filter_today_carryover_detection():
    """遗留任务可通过 task_date < today 检测"""
    session = _make_session()
    svc = TaskService(session)
    yesterday = date.today() - timedelta(days=1)

    today_task = svc.create_task("今天", task_type=Task.TYPE_SHORT_TERM)
    old_task = Task(title="遗留", task_type=Task.TYPE_SHORT_TERM,
                    task_date=yesterday, status="todo")
    session.add(old_task)
    session.commit()

    fs = FilterService(session)
    tasks = fs.get_today_tasks()
    today = date.today()
    carryover_ids = {t.id for t in tasks if t.task_date is None or t.task_date < today}
    assert old_task.id in carryover_ids
    assert today_task.id not in carryover_ids
    session.close()
    print("[PASS] test_filter_today_carryover_detection - 遗留任务检测正确")


# ============================================================
# 5. TaskItem 遗留模式测试
# ============================================================
def test_task_item_carryover_mode():
    """is_carryover=True 时无状态按钮，有移交按钮"""
    session = _make_session()
    task = Task(title="遗留任务", task_type=Task.TYPE_SHORT_TERM,
                task_date=date.today() - timedelta(days=1))
    session.add(task)
    session.commit()

    item = TaskItemWidget(task, is_carryover=True)
    assert item.status_btn is None
    assert item.title_label.objectName() == "TaskTitleCarryover"
    # 应有 carry_forward_requested 信号
    received = []
    item.carry_forward_requested.connect(lambda tid: received.append(tid))
    item.carry_forward_requested.emit(task.id)
    assert received == [task.id]
    session.close()
    print("[PASS] test_task_item_carryover_mode - 遗留模式显示正确")


def test_task_item_week_overdue_mode():
    """is_week_overdue=True 时无状态按钮，有重新编辑日期按钮"""
    session = _make_session()
    task = Task(title="过期周任务", task_type=Task.TYPE_WEEKLY,
                due_date=date.today() - timedelta(days=2))
    session.add(task)
    session.commit()

    item = TaskItemWidget(task, is_week_overdue=True)
    assert item.status_btn is None
    assert item.title_label.objectName() == "TaskTitleCarryover"
    received = []
    item.reschedule_requested.connect(lambda tid: received.append(tid))
    item.reschedule_requested.emit(task.id)
    assert received == [task.id]
    session.close()
    print("[PASS] test_task_item_week_overdue_mode - 周过期模式显示正确")


def test_task_item_normal_mode():
    """默认模式有状态按钮，无移交/重编按钮"""
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("正常任务", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    assert item.status_btn is not None
    assert item.title_label.objectName() == "TaskTitle"
    session.close()
    print("[PASS] test_task_item_normal_mode - 正常模式显示正确")


# ============================================================
# 6. TaskList 信号传递测试
# ============================================================
def test_task_list_carry_forward_signal():
    """TaskList 正确转发 carry_forward_requested"""
    session = _make_session()
    task = Task(title="遗留", task_type=Task.TYPE_SHORT_TERM,
                task_date=date.today() - timedelta(days=1))
    session.add(task)
    session.commit()

    widget = TaskListWidget()
    widget.set_tasks([task], carryover_ids={task.id})

    received = []
    widget.carry_forward_requested.connect(lambda tid: received.append(tid))
    inner = widget._task_widgets[task.id]
    inner.carry_forward_requested.emit(task.id)
    assert received == [task.id]
    session.close()
    print("[PASS] test_task_list_carry_forward_signal - 列表移交信号转发正确")


def test_task_list_reschedule_signal():
    """TaskList 正确转发 reschedule_requested"""
    session = _make_session()
    task = Task(title="过期周", task_type=Task.TYPE_WEEKLY,
                due_date=date.today() - timedelta(days=1))
    session.add(task)
    session.commit()

    widget = TaskListWidget()
    widget.set_tasks([task], week_overdue_ids={task.id})

    received = []
    widget.reschedule_requested.connect(lambda tid: received.append(tid))
    inner = widget._task_widgets[task.id]
    inner.reschedule_requested.emit(task.id)
    assert received == [task.id]
    session.close()
    print("[PASS] test_task_list_reschedule_signal - 列表重编日期信号转发正确")


# ============================================================
# 7. 侧栏布局测试
# ============================================================
def test_sidebar_has_scroll_area():
    """侧栏包含可滚动的自定义标签区域"""
    sidebar = TagSidebar()
    assert hasattr(sidebar, '_tag_scroll')
    assert isinstance(sidebar._tag_scroll, QScrollArea)
    assert sidebar._tag_scroll.objectName() == "TagScrollArea"
    print("[PASS] test_sidebar_has_scroll_area - 侧栏有滚动标签区域")


def test_sidebar_has_history_button():
    """侧栏底部有待办回顾按钮"""
    sidebar = TagSidebar()
    assert hasattr(sidebar, 'history_btn')
    assert sidebar.history_btn.toolTip() == "过往每日待办"
    print("[PASS] test_sidebar_has_history_button - 侧栏有待办回顾按钮")


def test_sidebar_history_signal():
    """待办回顾按钮点击发射 history_requested 信号"""
    sidebar = TagSidebar()
    received = []
    sidebar.history_requested.connect(lambda: received.append(True))
    sidebar.history_btn.click()
    assert len(received) == 1
    print("[PASS] test_sidebar_history_signal - 待办回顾信号正确")


def test_sidebar_custom_tags_in_scroll():
    """自定义标签添加到滚动区域而非主布局"""
    sidebar = TagSidebar()
    sidebar.add_custom_tag(1, "论文", "#EF4444")
    sidebar.add_custom_tag(2, "生活", "#10B981")

    tag_btns = [b for b in sidebar._buttons if b.key.startswith("tag_")]
    assert len(tag_btns) == 2
    # 验证按钮在 _tag_layout 中
    assert sidebar._tag_layout.count() == 2
    print("[PASS] test_sidebar_custom_tags_in_scroll - 自定义标签在滚动区域内")


# ============================================================
# 8. 周计划 10 天范围测试
# ============================================================
def test_weekly_combo_10_days():
    """周计划日期选择有 10 个选项"""
    from src.ui.task_editor import TaskEditorDialog
    session = _make_session()
    tag_svc = TagService(session)

    dialog = TaskEditorDialog([], task=None)
    assert dialog.weekday_combo.count() == 10

    # 第一项应该是今天
    first_date = dialog.weekday_combo.itemData(0)
    assert first_date == date.today()

    # 最后一项应该是今天 + 9 天
    last_date = dialog.weekday_combo.itemData(9)
    assert last_date == date.today() + timedelta(days=9)

    session.close()
    print("[PASS] test_weekly_combo_10_days - 周计划有 10 天选项")


def test_weekly_combo_stores_dates():
    """周计划 combo 存储 date 对象"""
    from src.ui.task_editor import TaskEditorDialog

    dialog = TaskEditorDialog([], task=None)
    for i in range(dialog.weekday_combo.count()):
        d = dialog.weekday_combo.itemData(i)
        assert isinstance(d, date), f"第 {i} 项不是 date 对象: {type(d)}"
    print("[PASS] test_weekly_combo_stores_dates - combo 存储 date 对象")


# ============================================================
# 9. 新主题样式测试
# ============================================================
def test_new_styles_in_themes():
    """新增样式标识符存在于所有主题中"""
    for key in get_theme_keys():
        theme = get_theme(key)
        qss = build_stylesheet(theme)
        assert "CarryForwardBtn" in qss, f"{key} 缺少 CarryForwardBtn"
        assert "TaskTitleCarryover" in qss, f"{key} 缺少 TaskTitleCarryover"
        assert "HistoryDateLabel" in qss, f"{key} 缺少 HistoryDateLabel"
        assert "HistoryTitle" in qss, f"{key} 缺少 HistoryTitle"
        assert "HistoryTitleDone" in qss, f"{key} 缺少 HistoryTitleDone"
        assert "HistoryDone" in qss, f"{key} 缺少 HistoryDone"
        assert "HistoryTodo" in qss, f"{key} 缺少 HistoryTodo"
        assert "TagScrollArea" in qss, f"{key} 缺少 TagScrollArea"
        assert "SidebarSeparator" in qss, f"{key} 缺少 SidebarSeparator"
        assert "TrashScroll" in qss, f"{key} 缺少 TrashScroll"
    print("[PASS] test_new_styles_in_themes - 所有主题包含新增样式")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # task_date 字段
        test_task_date_field_exists,
        test_task_date_auto_set_on_create,
        test_task_date_none_for_other_types,
        # carry_forward
        test_carry_forward,
        test_carry_forward_nonexistent,
        # 历史任务
        test_get_history_tasks,
        test_get_history_excludes_deleted,
        # 今日筛选含遗留
        test_filter_today_with_carryover,
        test_filter_today_carryover_detection,
        # TaskItem 模式
        test_task_item_carryover_mode,
        test_task_item_week_overdue_mode,
        test_task_item_normal_mode,
        # TaskList 信号
        test_task_list_carry_forward_signal,
        test_task_list_reschedule_signal,
        # 侧栏布局
        test_sidebar_has_scroll_area,
        test_sidebar_has_history_button,
        test_sidebar_history_signal,
        test_sidebar_custom_tags_in_scroll,
        # 周计划 10 天
        test_weekly_combo_10_days,
        test_weekly_combo_stores_dates,
        # 主题样式
        test_new_styles_in_themes,
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

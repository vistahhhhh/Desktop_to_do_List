"""第二阶段测试 - TaskService, TagService, FilterService"""

import sys
from pathlib import Path
from datetime import date, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.models.tag import Tag
from src.services.task_service import TaskService
from src.services.tag_service import TagService
from src.services.filter_service import FilterService


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


# ============================================================
# TagService 测试
# ============================================================
def test_tag_service_create():
    session = _make_session()
    ts = TagService(session)
    tag = ts.create_tag("论文", "#EF4444")
    assert tag.id is not None
    assert tag.name == "论文"
    assert tag.color == "#EF4444"
    session.close()
    print("[PASS] test_tag_service_create")


def test_tag_service_create_strips_hash():
    """输入 #论文 自动去除 # 前缀"""
    session = _make_session()
    ts = TagService(session)
    tag = ts.create_tag("#助教")
    assert tag.name == "助教"
    session.close()
    print("[PASS] test_tag_service_create_strips_hash")


def test_tag_service_create_duplicate():
    session = _make_session()
    ts = TagService(session)
    ts.create_tag("论文")
    try:
        ts.create_tag("论文")
        assert False, "应该抛出重复异常"
    except ValueError as e:
        assert "已存在" in str(e)
    session.close()
    print("[PASS] test_tag_service_create_duplicate")


def test_tag_service_create_empty():
    session = _make_session()
    ts = TagService(session)
    try:
        ts.create_tag("")
        assert False, "应该抛出空名称异常"
    except ValueError:
        pass
    try:
        ts.create_tag("  #  ")
        assert False, "应该抛出空名称异常"
    except ValueError:
        pass
    session.close()
    print("[PASS] test_tag_service_create_empty")


def test_tag_service_get_all():
    session = _make_session()
    ts = TagService(session)
    ts.create_tag("生活")
    ts.create_tag("助教")
    ts.create_tag("论文")
    tags = ts.get_all_tags()
    assert len(tags) == 3
    # 按名称排序
    names = [t.name for t in tags]
    assert names == sorted(names)
    session.close()
    print("[PASS] test_tag_service_get_all")


def test_tag_service_update():
    session = _make_session()
    ts = TagService(session)
    tag = ts.create_tag("论文")
    updated = ts.update_tag(tag.id, name="毕业论文", color="#FF0000")
    assert updated.name == "毕业论文"
    assert updated.color == "#FF0000"
    session.close()
    print("[PASS] test_tag_service_update")


def test_tag_service_update_duplicate_name():
    session = _make_session()
    ts = TagService(session)
    ts.create_tag("论文")
    tag2 = ts.create_tag("助教")
    try:
        ts.update_tag(tag2.id, name="论文")
        assert False, "应该抛出重名异常"
    except ValueError as e:
        assert "已存在" in str(e)
    session.close()
    print("[PASS] test_tag_service_update_duplicate_name")


def test_tag_service_delete():
    session = _make_session()
    ts = TagService(session)
    tag = ts.create_tag("临时")
    assert ts.delete_tag(tag.id) is True
    assert ts.get_tag(tag.id) is None
    assert ts.delete_tag(999) is False
    session.close()
    print("[PASS] test_tag_service_delete")


def test_tag_service_get_by_name():
    session = _make_session()
    ts = TagService(session)
    ts.create_tag("论文")
    tag = ts.get_tag_by_name("#论文")  # 带#也能找到
    assert tag is not None
    assert tag.name == "论文"
    assert ts.get_tag_by_name("不存在") is None
    session.close()
    print("[PASS] test_tag_service_get_by_name")


# ============================================================
# TaskService 测试
# ============================================================
def test_task_service_create_short():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("买菜", task_type=Task.TYPE_SHORT_TERM)
    assert task.id is not None
    assert task.title == "买菜"
    assert task.task_type == "short_term"
    assert task.status == "todo"
    assert task.due_date is None
    session.close()
    print("[PASS] test_task_service_create_short")


def test_task_service_create_long_with_tags():
    session = _make_session()
    tag_svc = TagService(session)
    t1 = tag_svc.create_tag("论文")
    t2 = tag_svc.create_tag("助教")

    svc = TaskService(session)
    task = svc.create_task(
        title="完成论文",
        task_type=Task.TYPE_LONG_TERM,
        description="# 大纲\n- 引言",
        due_date=date(2026, 5, 1),
        priority="high",
        tag_ids=[t1.id, t2.id],
    )
    assert task.due_date == date(2026, 5, 1)
    assert task.priority == "high"
    assert len(task.tags) == 2
    session.close()
    print("[PASS] test_task_service_create_long_with_tags")


def test_task_service_create_validation():
    session = _make_session()
    svc = TaskService(session)
    # 空标题
    try:
        svc.create_task("", task_type=Task.TYPE_SHORT_TERM)
        assert False
    except ValueError:
        pass
    # 无效类型
    try:
        svc.create_task("test", task_type="invalid")
        assert False
    except ValueError:
        pass
    # 无效优先级
    try:
        svc.create_task("test", task_type=Task.TYPE_SHORT_TERM, priority="urgent")
        assert False
    except ValueError:
        pass
    session.close()
    print("[PASS] test_task_service_create_validation")


def test_task_service_update():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("原标题", task_type=Task.TYPE_SHORT_TERM)
    updated = svc.update_task(task.id, title="新标题", priority="high")
    assert updated.title == "新标题"
    assert updated.priority == "high"
    session.close()
    print("[PASS] test_task_service_update")


def test_task_service_update_tags():
    session = _make_session()
    tag_svc = TagService(session)
    t1 = tag_svc.create_tag("论文")
    t2 = tag_svc.create_tag("生活")

    svc = TaskService(session)
    task = svc.create_task("任务", task_type=Task.TYPE_SHORT_TERM, tag_ids=[t1.id])
    assert len(task.tags) == 1

    # 更换标签
    updated = svc.update_task(task.id, tag_ids=[t2.id])
    assert len(updated.tags) == 1
    assert updated.tags[0].name == "生活"

    # 清空标签
    updated = svc.update_task(task.id, tag_ids=None)
    assert len(updated.tags) == 0
    session.close()
    print("[PASS] test_task_service_update_tags")


def test_task_service_update_nonexistent():
    session = _make_session()
    svc = TaskService(session)
    result = svc.update_task(999, title="不存在")
    assert result is None
    session.close()
    print("[PASS] test_task_service_update_nonexistent")


def test_task_service_update_status():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("任务", task_type=Task.TYPE_SHORT_TERM)
    updated = svc.update_status(task.id, "in_progress")
    assert updated.status == "in_progress"
    updated = svc.update_status(task.id, "done")
    assert updated.status == "done"
    # 无效状态
    try:
        svc.update_status(task.id, "invalid")
        assert False
    except ValueError:
        pass
    session.close()
    print("[PASS] test_task_service_update_status")


def test_task_service_delete():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("删我", task_type=Task.TYPE_SHORT_TERM)
    assert svc.delete_task(task.id) is True
    assert svc.get_task(task.id) is None
    assert svc.delete_task(999) is False
    session.close()
    print("[PASS] test_task_service_delete")


def test_task_service_get_all():
    session = _make_session()
    svc = TaskService(session)
    svc.create_task("任务1", task_type=Task.TYPE_SHORT_TERM)
    svc.create_task("任务2", task_type=Task.TYPE_SHORT_TERM)
    svc.create_task("任务3", task_type=Task.TYPE_LONG_TERM, due_date=date(2026, 6, 1))
    tasks = svc.get_all_tasks()
    assert len(tasks) == 3
    session.close()
    print("[PASS] test_task_service_get_all")


def test_task_service_add_remove_tag():
    session = _make_session()
    tag_svc = TagService(session)
    t1 = tag_svc.create_tag("论文")
    svc = TaskService(session)
    task = svc.create_task("任务", task_type=Task.TYPE_SHORT_TERM)

    assert svc.add_tag_to_task(task.id, t1.id) is True
    refreshed = svc.get_task(task.id)
    assert len(refreshed.tags) == 1

    # 重复添加不出错
    assert svc.add_tag_to_task(task.id, t1.id) is True

    assert svc.remove_tag_from_task(task.id, t1.id) is True
    refreshed = svc.get_task(task.id)
    assert len(refreshed.tags) == 0

    # 无效ID
    assert svc.add_tag_to_task(999, t1.id) is False
    assert svc.remove_tag_from_task(task.id, 999) is False
    session.close()
    print("[PASS] test_task_service_add_remove_tag")


# ============================================================
# FilterService 测试
# ============================================================
def _setup_filter_data(session):
    """构造测试数据"""
    tag_svc = TagService(session)
    t_paper = tag_svc.create_tag("论文")
    t_life = tag_svc.create_tag("生活")

    svc = TaskService(session)
    today = date.today()

    # 短期任务（当日）
    svc.create_task("买菜", task_type=Task.TYPE_SHORT_TERM, tag_ids=[t_life.id])
    svc.create_task("洗衣服", task_type=Task.TYPE_SHORT_TERM, tag_ids=[t_life.id])

    # 本周任务（weekly）
    tomorrow = today + timedelta(days=1)
    svc.create_task("周三开会", task_type=Task.TYPE_WEEKLY,
                    due_date=tomorrow, tag_ids=[t_paper.id])

    # 长期任务 - 未过期
    svc.create_task("今日截稿", task_type=Task.TYPE_LONG_TERM,
                    due_date=today, priority="high", tag_ids=[t_paper.id])

    # 长期任务 - 已过期
    svc.create_task("过期任务", task_type=Task.TYPE_LONG_TERM,
                    due_date=today - timedelta(days=3), priority="high")

    # 长期任务 - 下周截止
    svc.create_task("下周任务", task_type=Task.TYPE_LONG_TERM,
                    due_date=today + timedelta(days=14))

    # 已完成任务
    done_task = svc.create_task("已完成事项", task_type=Task.TYPE_SHORT_TERM)
    svc.update_status(done_task.id, "done")

    # 已取消任务
    cancelled = svc.create_task("取消的事", task_type=Task.TYPE_SHORT_TERM)
    svc.update_status(cancelled.id, "cancelled")

    return t_paper, t_life


def test_filter_today():
    session = _make_session()
    t_paper, t_life = _setup_filter_data(session)
    fs = FilterService(session)
    tasks = fs.get_today_tasks()
    titles = {t.title for t in tasks}
    # 今日任务包含 short_term 活跃+已完成任务
    assert "买菜" in titles
    assert "洗衣服" in titles
    assert "已完成事项" in titles  # done 保留显示
    # 不包含 weekly/long_term/已取消
    assert "周三开会" not in titles
    assert "今日截稿" not in titles
    assert "取消的事" not in titles
    session.close()
    print("[PASS] test_filter_today")


def test_filter_week():
    session = _make_session()
    t_paper, t_life = _setup_filter_data(session)
    fs = FilterService(session)
    tasks = fs.get_week_tasks()
    titles = {t.title for t in tasks}
    # 本周任务仅包含 weekly 类型活跃任务
    assert "周三开会" in titles
    # 不包含 short_term/long_term
    assert "买菜" not in titles
    assert "今日截稿" not in titles
    assert "已完成事项" not in titles
    session.close()
    print("[PASS] test_filter_week")


def test_filter_long_term():
    session = _make_session()
    _setup_filter_data(session)
    fs = FilterService(session)
    tasks = fs.get_long_term_tasks()
    titles = {t.title for t in tasks}
    # 长期任务包含所有 long_term 活跃任务（含过期）
    assert "今日截稿" in titles
    assert "过期任务" in titles
    assert "下周任务" in titles
    # 不包含 short_term/weekly
    assert "买菜" not in titles
    assert "周三开会" not in titles
    session.close()
    print("[PASS] test_filter_long_term")


def test_filter_by_tag():
    session = _make_session()
    t_paper, t_life = _setup_filter_data(session)
    fs = FilterService(session)

    paper_tasks = fs.get_tasks_by_tag(t_paper.id)
    paper_titles = {t.title for t in paper_tasks}
    assert "今日截稿" in paper_titles
    assert "周三开会" in paper_titles

    life_tasks = fs.get_tasks_by_tag(t_life.id)
    life_titles = {t.title for t in life_tasks}
    assert "买菜" in life_titles
    assert "洗衣服" in life_titles
    session.close()
    print("[PASS] test_filter_by_tag")


def test_filter_by_multiple_tags():
    session = _make_session()
    t_paper, t_life = _setup_filter_data(session)
    fs = FilterService(session)

    tasks = fs.get_tasks_by_tags([t_paper.id, t_life.id])
    titles = {t.title for t in tasks}
    assert "今日截稿" in titles
    assert "买菜" in titles

    # 空列表
    assert fs.get_tasks_by_tags([]) == []
    session.close()
    print("[PASS] test_filter_by_multiple_tags")


def test_filter_by_status():
    session = _make_session()
    _setup_filter_data(session)
    fs = FilterService(session)

    done = fs.get_tasks_by_status("done")
    assert any(t.title == "已完成事项" for t in done)

    cancelled = fs.get_tasks_by_status("cancelled")
    assert any(t.title == "取消的事" for t in cancelled)

    # 无效状态
    try:
        fs.get_tasks_by_status("invalid")
        assert False
    except ValueError:
        pass
    session.close()
    print("[PASS] test_filter_by_status")


def test_filter_active():
    session = _make_session()
    _setup_filter_data(session)
    fs = FilterService(session)
    active = fs.get_active_tasks()
    for t in active:
        assert t.status in ("todo", "in_progress")
    # 不包含已完成/已取消
    titles = {t.title for t in active}
    assert "已完成事项" not in titles
    assert "取消的事" not in titles
    session.close()
    print("[PASS] test_filter_active")


def test_filter_completed():
    session = _make_session()
    _setup_filter_data(session)
    fs = FilterService(session)
    completed = fs.get_completed_tasks()
    titles = {t.title for t in completed}
    assert "已完成事项" in titles
    assert "取消的事" in titles
    assert len(completed) == 2
    session.close()
    print("[PASS] test_filter_completed")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # TagService
        test_tag_service_create,
        test_tag_service_create_strips_hash,
        test_tag_service_create_duplicate,
        test_tag_service_create_empty,
        test_tag_service_get_all,
        test_tag_service_update,
        test_tag_service_update_duplicate_name,
        test_tag_service_delete,
        test_tag_service_get_by_name,
        # TaskService
        test_task_service_create_short,
        test_task_service_create_long_with_tags,
        test_task_service_create_validation,
        test_task_service_update,
        test_task_service_update_tags,
        test_task_service_update_nonexistent,
        test_task_service_update_status,
        test_task_service_delete,
        test_task_service_get_all,
        test_task_service_add_remove_tag,
        # FilterService
        test_filter_today,
        test_filter_week,
        test_filter_long_term,
        test_filter_by_tag,
        test_filter_by_multiple_tags,
        test_filter_by_status,
        test_filter_active,
        test_filter_completed,
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

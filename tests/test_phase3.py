"""第三阶段测试 - UI 组件测试（非交互式自动化验证）"""

import sys
from pathlib import Path
from datetime import date, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.models.tag import Tag
from src.services.task_service import TaskService
from src.services.tag_service import TagService
from src.services.filter_service import FilterService
from src.ui.styles.themes import (
    get_theme, build_stylesheet, get_theme_keys, THEMES, Theme
)
from src.ui.tag_sidebar import TagSidebar, TagButton, SMART_LISTS
from src.ui.task_item import TaskItemWidget, STATUS_FLOW, PRIORITY_LABELS
from src.ui.task_list import TaskListWidget

# 需要 QApplication 实例才能创建 QWidget
app = QApplication.instance() or QApplication(sys.argv)


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _make_tasks(session):
    """构造测试任务数据"""
    tag_svc = TagService(session)
    t1 = tag_svc.create_tag("论文", "#EF4444")
    t2 = tag_svc.create_tag("生活", "#10B981")

    svc = TaskService(session)
    tasks = []
    tasks.append(svc.create_task(
        "完成论文初稿", task_type=Task.TYPE_LONG_TERM,
        due_date=date.today() + timedelta(days=3),
        priority="high", tag_ids=[t1.id],
    ))
    tasks.append(svc.create_task(
        "准备助教材料", task_type=Task.TYPE_SHORT_TERM,
        priority="medium",
    ))
    tasks.append(svc.create_task(
        "购买生活用品", task_type=Task.TYPE_SHORT_TERM,
        priority="low", tag_ids=[t2.id],
    ))
    return tasks, [t1, t2]


# ============================================================
# 1. 主题系统测试
# ============================================================
def test_theme_keys():
    keys = get_theme_keys()
    assert "dark" in keys
    assert "light" in keys
    assert "black" in keys
    assert "morandy" in keys
    assert "green" in keys
    assert len(keys) == 5
    print("[PASS] test_theme_keys - 5种主题注册正确")


def test_theme_attributes():
    for key in get_theme_keys():
        theme = get_theme(key)
        assert isinstance(theme, Theme)
        assert theme.name
        assert theme.bg_color.startswith("#")
        assert theme.primary_color.startswith("#")
        assert theme.text_color.startswith("#")
        assert 0 <= theme.bg_opacity <= 1.0
    print("[PASS] test_theme_attributes - 主题属性完整")


def test_theme_stylesheet_generation():
    for key in get_theme_keys():
        theme = get_theme(key)
        qss = build_stylesheet(theme)
        assert len(qss) > 100
        assert "MainContainer" in qss
        assert "TitleBar" in qss
        assert "TaskCard" in qss
        assert "TagBtn" in qss
        assert "StatusCircle" in qss
        assert "AddTaskBtn" in qss
        assert theme.primary_color in qss
        assert "rgba(" in qss  # 背景色现在用 rgba 格式
    print("[PASS] test_theme_stylesheet_generation - QSS 样式表生成正确")


def test_theme_fallback():
    theme = get_theme("nonexistent_key")
    assert theme.name == "深色半透明"  # 回退到默认
    print("[PASS] test_theme_fallback - 无效主题名回退到默认")


# ============================================================
# 2. TagSidebar 测试
# ============================================================
def test_sidebar_creation():
    sidebar = TagSidebar()
    assert sidebar.width() == 42
    assert sidebar.objectName() == "TagSidebar"
    assert sidebar.get_current_key() == "today"  # 默认选中今日
    print("[PASS] test_sidebar_creation - 标签栏创建成功")


def test_sidebar_smart_lists():
    sidebar = TagSidebar()
    # 应有 4 个智能清单按钮
    smart_btns = [b for b in sidebar._buttons if not b.key.startswith("tag_")]
    assert len(smart_btns) == len(SMART_LISTS)
    keys = {b.key for b in smart_btns}
    assert keys == {"today", "week", "long_term"}
    print("[PASS] test_sidebar_smart_lists - 智能清单按钮正确")


def test_sidebar_add_custom_tags():
    sidebar = TagSidebar()
    sidebar.add_custom_tag(1, "论文", "#EF4444")
    sidebar.add_custom_tag(2, "生活", "#10B981")
    tag_btns = [b for b in sidebar._buttons if b.key.startswith("tag_")]
    assert len(tag_btns) == 2
    assert tag_btns[0].key == "tag_1"
    assert tag_btns[1].key == "tag_2"
    print("[PASS] test_sidebar_add_custom_tags - 自定义标签添加成功")


def test_sidebar_refresh_tags():
    session = _make_session()
    tag_svc = TagService(session)
    t1 = tag_svc.create_tag("论文")
    t2 = tag_svc.create_tag("生活")

    sidebar = TagSidebar()
    sidebar.refresh_tags([t1, t2])
    tag_btns = [b for b in sidebar._buttons if b.key.startswith("tag_")]
    assert len(tag_btns) == 2

    # 刷新为新列表
    t3 = tag_svc.create_tag("助教")
    sidebar.refresh_tags([t1, t3])
    tag_btns = [b for b in sidebar._buttons if b.key.startswith("tag_")]
    assert len(tag_btns) == 2
    keys = {b.key for b in tag_btns}
    assert f"tag_{t1.id}" in keys
    assert f"tag_{t3.id}" in keys
    session.close()
    print("[PASS] test_sidebar_refresh_tags - 标签刷新正确")


def test_sidebar_selection():
    sidebar = TagSidebar()
    received = []
    sidebar.filter_changed.connect(lambda ft, fv: received.append((ft, fv)))

    # 模拟点击 "本周"
    sidebar._on_click("week")
    assert sidebar.get_current_key() == "week"
    assert received[-1] == ("smart_list", "week")

    # 模拟点击自定义标签
    sidebar.add_custom_tag(5, "论文")
    sidebar._on_click("tag_5")
    assert sidebar.get_current_key() == "tag_5"
    assert received[-1] == ("tag", "5")

    # 验证按钮激活状态
    for btn in sidebar._buttons:
        if btn.key == "tag_5":
            assert btn.is_active is True
        else:
            assert btn.is_active is False
    print("[PASS] test_sidebar_selection - 标签选中与信号发射正确")


# ============================================================
# 3. TaskItemWidget 测试
# ============================================================
def test_task_item_display():
    session = _make_session()
    tasks, tags = _make_tasks(session)
    task = tasks[0]

    item = TaskItemWidget(task)
    assert item.objectName() == "TaskCard"
    assert item.title_label.text() == "完成论文初稿"
    assert item.title_label.objectName() == "TaskTitle"
    assert item.status_btn.objectName() == "StatusCircle"
    session.close()
    print("[PASS] test_task_item_display - 任务项显示正确")


def test_task_item_status_toggle():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("测试任务", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    received = []
    item.status_changed.connect(lambda tid, s: received.append((tid, s)))

    # todo -> done
    assert task.status == "todo"
    item._toggle_status()
    assert received[-1] == (task.id, "done")
    assert item.status_btn.objectName() == "StatusCircleDone"
    assert item.title_label.objectName() == "TaskTitleDone"

    # done -> todo
    item._toggle_status()
    assert received[-1] == (task.id, "todo")
    assert item.status_btn.objectName() == "StatusCircle"
    assert item.title_label.objectName() == "TaskTitle"

    session.close()
    print("[PASS] test_task_item_status_toggle - 状态循环切换正确")


def test_task_item_double_click_signal():
    session = _make_session()
    svc = TaskService(session)
    task = svc.create_task("双击测试", task_type=Task.TYPE_SHORT_TERM)

    item = TaskItemWidget(task)
    received = []
    item.edit_requested.connect(lambda tid: received.append(tid))

    # 模拟双击
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QPointF, QEvent
    event = QMouseEvent(
        QEvent.MouseButtonDblClick,
        QPointF(10, 10),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    item.mouseDoubleClickEvent(event)
    assert len(received) == 1
    assert received[0] == task.id
    session.close()
    print("[PASS] test_task_item_double_click_signal - 双击编辑信号正确")


def test_status_flow_map():
    assert STATUS_FLOW["todo"] == "done"
    assert STATUS_FLOW["in_progress"] == "done"
    assert STATUS_FLOW["done"] == "todo"
    assert STATUS_FLOW["cancelled"] == "todo"
    print("[PASS] test_status_flow_map - 状态流转映射正确")


def test_priority_labels():
    assert PRIORITY_LABELS["high"] == "🔴"
    assert PRIORITY_LABELS["medium"] == "🟡"
    assert PRIORITY_LABELS["low"] == "🟢"
    print("[PASS] test_priority_labels - 优先级标签正确")


# ============================================================
# 4. TaskListWidget 测试
# ============================================================
def test_task_list_empty():
    widget = TaskListWidget()
    widget.set_tasks([])
    assert widget.get_task_count() == 0
    assert widget.is_empty()
    print("[PASS] test_task_list_empty - 空列表显示正确")


def test_task_list_with_tasks():
    session = _make_session()
    tasks, _ = _make_tasks(session)

    widget = TaskListWidget()
    widget.set_tasks(tasks)
    assert widget.get_task_count() == 3
    assert not widget.is_empty()
    session.close()
    print("[PASS] test_task_list_with_tasks - 任务列表渲染正确")


def test_task_list_refresh():
    session = _make_session()
    tasks, _ = _make_tasks(session)

    widget = TaskListWidget()
    widget.set_tasks(tasks)
    assert widget.get_task_count() == 3

    # 只显示前两个
    widget.set_tasks(tasks[:2])
    assert widget.get_task_count() == 2

    # 清空
    widget.set_tasks([])
    assert widget.get_task_count() == 0
    assert widget.is_empty()
    session.close()
    print("[PASS] test_task_list_refresh - 列表刷新正确")


def test_task_list_status_signal():
    session = _make_session()
    tasks, _ = _make_tasks(session)

    widget = TaskListWidget()
    widget.set_tasks(tasks)

    received = []
    widget.status_changed.connect(lambda tid, s: received.append((tid, s)))

    # 通过内部 widget 触发状态变更
    task_id = tasks[0].id
    inner_widget = widget._task_widgets[task_id]
    inner_widget._toggle_status()
    assert len(received) == 1
    assert received[0][0] == task_id
    session.close()
    print("[PASS] test_task_list_status_signal - 列表状态信号正确")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # 主题系统
        test_theme_keys,
        test_theme_attributes,
        test_theme_stylesheet_generation,
        test_theme_fallback,
        # 标签栏
        test_sidebar_creation,
        test_sidebar_smart_lists,
        test_sidebar_add_custom_tags,
        test_sidebar_refresh_tags,
        test_sidebar_selection,
        # 任务项
        test_task_item_display,
        test_task_item_status_toggle,
        test_task_item_double_click_signal,
        test_status_flow_map,
        test_priority_labels,
        # 任务列表
        test_task_list_empty,
        test_task_list_with_tasks,
        test_task_list_refresh,
        test_task_list_status_signal,
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

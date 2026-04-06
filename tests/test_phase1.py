"""第一阶段测试 - 数据模型、数据库、配置管理"""

import sys
import os
import tempfile
import json
from pathlib import Path
from datetime import date, datetime, timezone

# 项目根目录加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task, task_tags
from src.models.tag import Tag
from src.utils.config_manager import ConfigManager


# ============================================================
# 辅助：每个测试使用内存数据库，互不干扰
# ============================================================
def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


# ============================================================
# 1. 数据库建表测试
# ============================================================
def test_create_tables():
    """验证所有表能正确创建"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    table_names = Base.metadata.tables.keys()
    assert "tasks" in table_names, "tasks 表未创建"
    assert "tags" in table_names, "tags 表未创建"
    assert "task_tags" in table_names, "task_tags 关联表未创建"
    print("[PASS] test_create_tables - 三张表创建成功")


# ============================================================
# 2. Tag 模型 CRUD
# ============================================================
def test_tag_create():
    """创建标签"""
    session = _make_session()
    tag = Tag(name="论文", color="#EF4444")
    session.add(tag)
    session.commit()
    assert tag.id is not None
    assert tag.name == "论文"
    assert tag.color == "#EF4444"
    assert tag.created_at is not None
    session.close()
    print("[PASS] test_tag_create - 标签创建成功")


def test_tag_unique_name():
    """标签名唯一约束"""
    session = _make_session()
    session.add(Tag(name="助教"))
    session.commit()
    session.add(Tag(name="助教"))
    try:
        session.commit()
        assert False, "应该抛出唯一约束异常"
    except Exception:
        session.rollback()
    session.close()
    print("[PASS] test_tag_unique_name - 标签名唯一约束生效")


def test_tag_to_dict():
    """标签序列化"""
    session = _make_session()
    tag = Tag(name="生活", color="#10B981")
    session.add(tag)
    session.commit()
    d = tag.to_dict()
    assert d["name"] == "生活"
    assert d["color"] == "#10B981"
    assert "id" in d
    session.close()
    print("[PASS] test_tag_to_dict - 标签序列化正确")


# ============================================================
# 3. Task 模型 CRUD
# ============================================================
def test_task_create_short_term():
    """创建短期任务（当日）"""
    session = _make_session()
    task = Task(
        title="购买生活用品",
        task_type=Task.TYPE_SHORT_TERM,
        priority=Task.PRIORITY_LOW,
    )
    session.add(task)
    session.commit()
    assert task.id is not None
    assert task.title == "购买生活用品"
    assert task.task_type == "short_term"
    assert task.due_date is None
    assert task.status == "todo"
    assert task.priority == "low"
    session.close()
    print("[PASS] test_task_create_short_term - 短期任务创建成功")


def test_task_create_long_term():
    """创建长期任务（有截止日期）"""
    session = _make_session()
    task = Task(
        title="完成论文初稿",
        description="# 论文大纲\n- 第一章\n- 第二章",
        task_type=Task.TYPE_LONG_TERM,
        due_date=date(2026, 4, 15),
        priority=Task.PRIORITY_HIGH,
    )
    session.add(task)
    session.commit()
    assert task.task_type == "long_term"
    assert task.due_date == date(2026, 4, 15)
    assert task.description.startswith("# 论文大纲")
    assert task.priority == "high"
    session.close()
    print("[PASS] test_task_create_long_term - 长期任务创建成功")


def test_task_status_update():
    """任务状态流转"""
    session = _make_session()
    task = Task(title="测试状态", task_type=Task.TYPE_SHORT_TERM)
    session.add(task)
    session.commit()
    assert task.status == "todo"

    task.status = Task.STATUS_IN_PROGRESS
    session.commit()
    assert task.status == "in_progress"

    task.status = Task.STATUS_DONE
    session.commit()
    assert task.status == "done"

    task.status = Task.STATUS_CANCELLED
    session.commit()
    assert task.status == "cancelled"
    session.close()
    print("[PASS] test_task_status_update - 状态流转正常")


def test_task_valid_enums():
    """枚举常量正确"""
    assert Task.VALID_TYPES == ("long_term", "short_term", "weekly")
    assert Task.VALID_PRIORITIES == ("high", "medium", "low")
    assert Task.VALID_STATUSES == ("todo", "in_progress", "done", "cancelled")
    print("[PASS] test_task_valid_enums - 枚举常量正确")


# ============================================================
# 4. 多对多关系 (Task <-> Tag)
# ============================================================
def test_task_tag_relationship():
    """任务与标签的多对多关联"""
    session = _make_session()
    tag1 = Tag(name="论文", color="#EF4444")
    tag2 = Tag(name="助教", color="#3B82F6")
    task = Task(
        title="完成论文并准备助教材料",
        task_type=Task.TYPE_LONG_TERM,
        due_date=date(2026, 4, 1),
    )
    task.tags.append(tag1)
    task.tags.append(tag2)
    session.add(task)
    session.commit()

    # 验证正向关系
    fetched = session.query(Task).filter_by(id=task.id).first()
    assert len(fetched.tags) == 2
    tag_names = {t.name for t in fetched.tags}
    assert tag_names == {"论文", "助教"}

    # 验证反向关系
    fetched_tag = session.query(Tag).filter_by(name="论文").first()
    assert len(fetched_tag.tasks) == 1
    assert fetched_tag.tasks[0].title == "完成论文并准备助教材料"

    session.close()
    print("[PASS] test_task_tag_relationship - 多对多关系正确")


def test_task_remove_tag():
    """移除任务标签"""
    session = _make_session()
    tag = Tag(name="生活")
    task = Task(title="购物", task_type=Task.TYPE_SHORT_TERM)
    task.tags.append(tag)
    session.add(task)
    session.commit()
    assert len(task.tags) == 1

    task.tags.remove(tag)
    session.commit()
    fetched = session.query(Task).filter_by(id=task.id).first()
    assert len(fetched.tags) == 0
    session.close()
    print("[PASS] test_task_remove_tag - 标签移除成功")


def test_task_to_dict_with_tags():
    """任务序列化（含标签）"""
    session = _make_session()
    tag = Tag(name="论文", color="#EF4444")
    task = Task(
        title="写论文",
        task_type=Task.TYPE_LONG_TERM,
        due_date=date(2026, 5, 1),
        priority=Task.PRIORITY_HIGH,
    )
    task.tags.append(tag)
    session.add(task)
    session.commit()

    d = task.to_dict()
    assert d["title"] == "写论文"
    assert d["task_type"] == "long_term"
    assert d["due_date"] == "2026-05-01"
    assert d["priority"] == "high"
    assert len(d["tags"]) == 1
    assert d["tags"][0]["name"] == "论文"
    session.close()
    print("[PASS] test_task_to_dict_with_tags - 序列化（含标签）正确")


# ============================================================
# 5. ConfigManager 测试
# ============================================================
def test_config_default_creation():
    """配置文件默认创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cm = ConfigManager(config_path=cfg_path)

        assert cfg_path.exists(), "config.json 未创建"
        assert cm.get("window.opacity") == 0.95
        assert cm.get("theme.primary_color") == "#6366F1"
        assert cm.get("behavior.minimize_to_tray") is True
    print("[PASS] test_config_default_creation - 默认配置创建成功")


def test_config_get_set():
    """配置读写"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cm = ConfigManager(config_path=cfg_path)

        cm.set("window.opacity", 0.8)
        assert cm.get("window.opacity") == 0.8

        cm.set("theme.primary_color", "#FF0000")
        assert cm.get("theme.primary_color") == "#FF0000"

        # 重新加载验证持久化
        cm2 = ConfigManager(config_path=cfg_path)
        assert cm2.get("window.opacity") == 0.8
        assert cm2.get("theme.primary_color") == "#FF0000"
    print("[PASS] test_config_get_set - 配置读写与持久化正确")


def test_config_nested_set():
    """配置嵌套路径设置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cm = ConfigManager(config_path=cfg_path)

        cm.set("current_filter.type", "tag")
        cm.set("current_filter.value", "3")
        assert cm.get("current_filter.type") == "tag"
        assert cm.get("current_filter.value") == "3"
    print("[PASS] test_config_nested_set - 嵌套路径设置正确")


def test_config_get_nonexistent():
    """获取不存在的键返回默认值"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cm = ConfigManager(config_path=cfg_path)
        assert cm.get("nonexistent.key") is None
        assert cm.get("nonexistent.key", "fallback") == "fallback"
    print("[PASS] test_config_get_nonexistent - 不存在的键返回默认值")


def test_config_reset():
    """重置配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cm = ConfigManager(config_path=cfg_path)
        cm.set("window.opacity", 0.5)
        cm.reset()
        assert cm.get("window.opacity") == 0.95
    print("[PASS] test_config_reset - 配置重置成功")


def test_config_merge_defaults():
    """加载已有配置文件时合并缺失的默认值"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        # 模拟一个不完整的配置文件
        partial = {"window": {"x": 200, "y": 300}}
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(partial, f)

        cm = ConfigManager(config_path=cfg_path)
        # 已有值保留
        assert cm.get("window.x") == 200
        assert cm.get("window.y") == 300
        # 缺失值用默认补齐
        assert cm.get("window.opacity") == 0.95
        assert cm.get("theme.primary_color") == "#6366F1"
    print("[PASS] test_config_merge_defaults - 默认值合并正确")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        test_create_tables,
        test_tag_create,
        test_tag_unique_name,
        test_tag_to_dict,
        test_task_create_short_term,
        test_task_create_long_term,
        test_task_status_update,
        test_task_valid_enums,
        test_task_tag_relationship,
        test_task_remove_tag,
        test_task_to_dict_with_tags,
        test_config_default_creation,
        test_config_get_set,
        test_config_nested_set,
        test_config_get_nonexistent,
        test_config_reset,
        test_config_merge_defaults,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__} - {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

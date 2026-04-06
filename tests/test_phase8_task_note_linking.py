"""第八阶段测试 - 任务与便签关联"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.task import Task
from src.models.note import Note
from src.services.task_service import TaskService
from src.services.note_service import NoteService
from src.services.link_service import LinkService


def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _make_task_and_note(session):
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    task = task_svc.create_task("任务A", task_type=Task.TYPE_SHORT_TERM)
    note = note_svc.create()
    note_svc.save(note, "便签A", "<p>内容</p>")
    return task, note


def test_link_create_success():
    session = _make_session()
    task, note = _make_task_and_note(session)
    svc = LinkService(session)

    ok = svc.link(task.id, note.id)
    assert ok is True
    assert note.task_id == task.id
    assert svc.count_notes_for_task(task.id) == 1

    session.close()
    print("[PASS] test_link_create_success")


def test_link_duplicate_blocked():
    session = _make_session()
    task, note = _make_task_and_note(session)
    svc = LinkService(session)

    assert svc.link(task.id, note.id) is True
    assert svc.link(task.id, note.id) is False
    assert svc.count_notes_for_task(task.id) == 1

    session.close()
    print("[PASS] test_link_duplicate_blocked")


def test_link_replace_existing_note_for_task():
    session = _make_session()
    task, note_a = _make_task_and_note(session)
    note_svc = NoteService(session)
    svc = LinkService(session)

    note_b = note_svc.create()
    note_svc.save(note_b, "便签B", "<p>内容B</p>")

    assert svc.link(task.id, note_a.id) is True
    assert svc.link(task.id, note_b.id, replace=False) is False
    assert svc.link(task.id, note_b.id, replace=True) is True

    refreshed_a = note_svc.get_by_id(note_a.id)
    refreshed_b = note_svc.get_by_id(note_b.id)
    assert refreshed_a.task_id is None
    assert refreshed_b.task_id == task.id

    session.close()
    print("[PASS] test_link_replace_existing_note_for_task")


def test_unlink_success():
    session = _make_session()
    task, note = _make_task_and_note(session)
    svc = LinkService(session)

    assert svc.link(task.id, note.id) is True
    assert svc.unlink(task.id, note.id) is True
    assert svc.count_notes_for_task(task.id) == 0
    assert session.get(Note, note.id).task_id is None

    session.close()
    print("[PASS] test_unlink_success")


def test_delete_task_cleans_links_only():
    session = _make_session()
    task, note = _make_task_and_note(session)
    link_svc = LinkService(session)
    task_svc = TaskService(session)

    assert link_svc.link(task.id, note.id) is True
    assert task_svc.permanent_delete_task(task.id) is True

    remains_note = session.get(Note, note.id)
    assert remains_note is not None
    assert remains_note.task_id is None

    session.close()
    print("[PASS] test_delete_task_cleans_links_only")


def test_soft_deleted_note_hidden_from_task_links():
    session = _make_session()
    task, note = _make_task_and_note(session)
    link_svc = LinkService(session)
    note_svc = NoteService(session)

    assert link_svc.link(task.id, note.id) is True
    note_svc.delete(note.id)

    note_default = link_svc.get_note_for_task(task.id)
    note_including_deleted = link_svc.get_note_for_task(task.id, include_deleted=True)
    assert note_default is None
    assert note_including_deleted is not None

    session.close()
    print("[PASS] test_soft_deleted_note_hidden_from_task_links")


def test_restore_note_links_visible_again():
    session = _make_session()
    task, note = _make_task_and_note(session)
    link_svc = LinkService(session)
    note_svc = NoteService(session)

    assert link_svc.link(task.id, note.id) is True
    note_svc.delete(note.id)
    assert link_svc.get_note_for_task(task.id) is None

    note_svc.restore(note.id)
    visible = link_svc.get_note_for_task(task.id)
    assert visible is not None
    assert visible.id == note.id

    session.close()
    print("[PASS] test_restore_note_links_visible_again")


def test_create_linked_note_empty_not_persisted():
    session = _make_session()
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    link_svc = LinkService(session)

    task = task_svc.create_task("任务A", task_type=Task.TYPE_SHORT_TERM)
    note = note_svc.create_for_task(task.id, title_hint="")
    assert note is not None

    # 模拟后续编辑器将内容清空的行为
    note_svc.permanent_delete(note.id)

    notes = note_svc.get_all()
    linked = link_svc.get_note_for_task(task.id)
    assert all(n.id != note.id for n in notes)
    assert linked is None

    session.close()
    print("[PASS] test_create_linked_note_empty_not_persisted")


def test_replace_from_note_side_target_task_has_note():
    """便签A关联任务1，便签B关联任务2，将便签A改为关联任务2（replace=True）
    应该成功，便签B的task_id应被清除，不触发UNIQUE冲突。"""
    session = _make_session()
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    svc = LinkService(session)

    task1 = task_svc.create_task("任务1", task_type=Task.TYPE_SHORT_TERM)
    task2 = task_svc.create_task("任务2", task_type=Task.TYPE_SHORT_TERM)
    note_a = note_svc.create()
    note_svc.save(note_a, "便签A", "<p>A</p>")
    note_b = note_svc.create()
    note_svc.save(note_b, "便签B", "<p>B</p>")

    assert svc.link(task1.id, note_a.id) is True
    assert svc.link(task2.id, note_b.id) is True

    # 将便签A从任务1改为任务2（任务2已被便签B占用）
    ok = svc.link(task2.id, note_a.id, replace=True)
    assert ok is True, "replace=True时应成功替换"

    refreshed_a = note_svc.get_by_id(note_a.id)
    refreshed_b = note_svc.get_by_id(note_b.id)
    assert refreshed_a.task_id == task2.id, "便签A应关联到任务2"
    assert refreshed_b.task_id is None, "便签B的关联应被清除"

    session.close()
    print("[PASS] test_replace_from_note_side_target_task_has_note")


def test_link_target_task_occupied_no_replace():
    """目标任务已有便签关联，replace=False时应返回False而非崩溃。"""
    session = _make_session()
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    svc = LinkService(session)

    task = task_svc.create_task("任务X", task_type=Task.TYPE_SHORT_TERM)
    note_a = note_svc.create()
    note_svc.save(note_a, "便签A", "<p>A</p>")
    note_b = note_svc.create()
    note_svc.save(note_b, "便签B", "<p>B</p>")

    assert svc.link(task.id, note_a.id) is True
    ok = svc.link(task.id, note_b.id, replace=False)
    assert ok is False, "replace=False且目标任务已有便签时应返回False"

    # 确保原关联未被破坏
    assert note_svc.get_by_id(note_a.id).task_id == task.id
    assert note_svc.get_by_id(note_b.id).task_id is None

    session.close()
    print("[PASS] test_link_target_task_occupied_no_replace")


def test_replace_with_soft_deleted_note_holding_task():
    """软删除的便签仍持有task_id，新便签关联同一任务时应自动清除。"""
    session = _make_session()
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    svc = LinkService(session)

    task = task_svc.create_task("任务Y", task_type=Task.TYPE_SHORT_TERM)
    note_old = note_svc.create()
    note_svc.save(note_old, "旧便签", "<p>旧</p>")
    assert svc.link(task.id, note_old.id) is True

    # 软删除旧便签（task_id仍保留在DB中）
    note_svc.delete(note_old.id)
    assert note_svc.get_by_id(note_old.id).task_id == task.id

    # 新便签尝试关联同一任务
    note_new = note_svc.create()
    note_svc.save(note_new, "新便签", "<p>新</p>")
    ok = svc.link(task.id, note_new.id, replace=True)
    assert ok is True, "replace=True时应成功，即使旧便签是软删除的"

    assert note_svc.get_by_id(note_new.id).task_id == task.id
    assert note_svc.get_by_id(note_old.id).task_id is None

    session.close()
    print("[PASS] test_replace_with_soft_deleted_note_holding_task")


def test_double_replace_cycle():
    """反复替换关联不崩溃：A→T1, B→T2, 然后A→T2, 再A→T1"""
    session = _make_session()
    task_svc = TaskService(session)
    note_svc = NoteService(session)
    svc = LinkService(session)

    t1 = task_svc.create_task("T1", task_type=Task.TYPE_SHORT_TERM)
    t2 = task_svc.create_task("T2", task_type=Task.TYPE_SHORT_TERM)
    na = note_svc.create()
    note_svc.save(na, "NA", "<p>a</p>")
    nb = note_svc.create()
    note_svc.save(nb, "NB", "<p>b</p>")

    assert svc.link(t1.id, na.id) is True
    assert svc.link(t2.id, nb.id) is True

    # A→T2 (T2已被B占用, A已关联T1)
    assert svc.link(t2.id, na.id, replace=True) is True
    assert note_svc.get_by_id(na.id).task_id == t2.id
    assert note_svc.get_by_id(nb.id).task_id is None

    # A→T1 (T1空闲，A已关联T2)
    assert svc.link(t1.id, na.id, replace=True) is True
    assert note_svc.get_by_id(na.id).task_id == t1.id

    session.close()
    print("[PASS] test_double_replace_cycle")


def _make_migration_engine():
    """创建带 task_note_links 旧表的内存数据库，模拟迁移前状态。"""
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "title VARCHAR(200) NOT NULL,"
            "task_type VARCHAR(20) NOT NULL DEFAULT 'short_term',"
            "status VARCHAR(20) DEFAULT 'pending',"
            "priority INTEGER DEFAULT 2,"
            "is_deleted INTEGER DEFAULT 0,"
            "created_at DATETIME,"
            "updated_at DATETIME"
            ")"
        ))
        conn.execute(text(
            "CREATE TABLE notes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "title VARCHAR(200) DEFAULT '',"
            "body_html TEXT DEFAULT '',"
            "deleted BOOLEAN DEFAULT 0,"
            "task_id INTEGER,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(text(
            "CREATE TABLE task_note_links ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "task_id INTEGER NOT NULL,"
            "note_id INTEGER NOT NULL,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
    return engine


def test_migration_with_preexisting_task_ids():
    """迁移时便签已有 task_id，不应崩溃。"""
    from sqlalchemy import text, inspect
    from src.models.database import _migrate_task_note_links_to_one_to_one

    engine = _make_migration_engine()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tasks(id, title) VALUES (1, 'T1')"))
        conn.execute(text("INSERT INTO tasks(id, title) VALUES (2, 'T2')"))
        conn.execute(text("INSERT INTO notes(id, title, updated_at) VALUES (10, 'N10', '2026-01-01')"))
        conn.execute(text("INSERT INTO notes(id, title, updated_at) VALUES (11, 'N11', '2026-01-02')"))
        # N10 已经有 task_id（上次迁移部分成功）
        conn.execute(text("UPDATE notes SET task_id = 1 WHERE id = 10"))
        # 旧表中仍有两条记录
        conn.execute(text("INSERT INTO task_note_links(task_id, note_id) VALUES (1, 10)"))
        conn.execute(text("INSERT INTO task_note_links(task_id, note_id) VALUES (2, 11)"))

    # 创建 UNIQUE 索引（模拟真实环境）
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notes_task_id_not_null "
            "ON notes(task_id) WHERE task_id IS NOT NULL"
        ))

    # 执行迁移，不应崩溃
    _migrate_task_note_links_to_one_to_one(engine)

    with engine.begin() as conn:
        r10 = conn.execute(text("SELECT task_id FROM notes WHERE id = 10")).fetchone()
        r11 = conn.execute(text("SELECT task_id FROM notes WHERE id = 11")).fetchone()
        assert r10[0] == 1, f"N10 should keep task_id=1, got {r10[0]}"
        assert r11[0] == 2, f"N11 should get task_id=2, got {r11[0]}"

    # 旧表应被删除
    tables = inspect(engine).get_table_names()
    assert "task_note_links" not in tables, "task_note_links should be dropped after migration"

    print("[PASS] test_migration_with_preexisting_task_ids")


def test_migration_idempotent_after_drop():
    """旧表删除后再次调用迁移不报错。"""
    from sqlalchemy import inspect
    from src.models.database import _migrate_task_note_links_to_one_to_one

    engine = _make_migration_engine()
    # 第一次迁移（无数据，只是走完流程并删表）
    _migrate_task_note_links_to_one_to_one(engine)
    tables = inspect(engine).get_table_names()
    assert "task_note_links" not in tables

    # 第二次调用不应报错
    _migrate_task_note_links_to_one_to_one(engine)
    print("[PASS] test_migration_idempotent_after_drop")


def run_all():
    tests = [
        test_link_create_success,
        test_link_duplicate_blocked,
        test_link_replace_existing_note_for_task,
        test_unlink_success,
        test_delete_task_cleans_links_only,
        test_soft_deleted_note_hidden_from_task_links,
        test_restore_note_links_visible_again,
        test_create_linked_note_empty_not_persisted,
        test_replace_from_note_side_target_task_has_note,
        test_link_target_task_occupied_no_replace,
        test_replace_with_soft_deleted_note_holding_task,
        test_double_replace_cycle,
        test_migration_with_preexisting_task_ids,
        test_migration_idempotent_after_drop,
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

"""数据库初始化与会话管理"""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.utils.paths import get_data_dir

Base = declarative_base()

# 数据库文件路径：通过 paths 模块统一管理
_DB_DIR = get_data_dir()
_DB_PATH = _DB_DIR / "tasks.db"

_engine = None
_SessionFactory = None


def get_engine():
    """获取或创建数据库引擎"""
    global _engine
    if _engine is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{_DB_PATH}",
            echo=False,
            future=True,
        )
    return _engine


def init_db():
    """初始化数据库：创建所有表，并执行必要的迁移"""
    engine = get_engine()
    # 导入模型以注册到 Base.metadata
    from src.models.task import Task  # noqa: F401
    from src.models.tag import Tag  # noqa: F401
    from src.models.note import Note  # noqa: F401
    Base.metadata.create_all(engine)
    _migrate(engine)
    return engine


def _migrate(engine):
    """轻量迁移：为已有表添加新列"""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    # 确保 notes 表存在（create_all 已处理，此处仅保障兼容性）
    tables = inspector.get_table_names()
    if "notes" not in tables:
        from src.models.note import Note  # noqa: F401
        Base.metadata.tables["notes"].create(engine)
    task_cols = [c["name"] for c in inspector.get_columns("tasks")]
    if "is_deleted" not in task_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN is_deleted INTEGER DEFAULT 0"))
    tag_cols = [c["name"] for c in inspector.get_columns("tags")]
    if "icon" not in tag_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tags ADD COLUMN icon VARCHAR(10) DEFAULT '📌'"))
    if "task_date" not in task_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN task_date DATE"))
            # 为已有的 short_term 任务补充 task_date（使用 created_at 的日期）
            conn.execute(text(
                "UPDATE tasks SET task_date = DATE(created_at) "
                "WHERE task_type = 'short_term' AND task_date IS NULL"
            ))
    if "parent_id" not in task_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN parent_id INTEGER"))

    notes_cols = [c["name"] for c in inspector.get_columns("notes")]
    if "task_id" not in notes_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE notes ADD COLUMN task_id INTEGER"))

    _migrate_task_note_links_to_one_to_one(engine)

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_notes_task_id ON notes(task_id)"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_notes_task_id_not_null "
            "ON notes(task_id) WHERE task_id IS NOT NULL"
        ))


def _migrate_task_note_links_to_one_to_one(engine):
    """将旧 task_note_links（多对多）按规则迁移到 notes.task_id（一对一）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "task_note_links" not in tables:
        return

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS task_note_link_migration_backup ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "task_id INTEGER NOT NULL,"
            "note_id INTEGER NOT NULL,"
            "created_at DATETIME,"
            "reason VARCHAR(32) NOT NULL"
            ")"
        ))

        rows = conn.execute(text(
            "SELECT l.task_id, l.note_id, l.created_at, n.updated_at "
            "FROM task_note_links l "
            "JOIN notes n ON n.id = l.note_id "
            "ORDER BY n.updated_at DESC, l.created_at DESC, l.note_id DESC"
        )).fetchall()

        assigned_task_ids = set()
        assigned_note_ids = set()

        # 收集已经有 task_id 的便签（可能上次迁移已部分完成）
        existing = conn.execute(text(
            "SELECT id, task_id FROM notes WHERE task_id IS NOT NULL"
        )).fetchall()
        for nid, tid in existing:
            assigned_note_ids.add(nid)
            assigned_task_ids.add(tid)

        for task_id, note_id, created_at, _note_updated_at in rows:
            if task_id in assigned_task_ids:
                conn.execute(text(
                    "INSERT INTO task_note_link_migration_backup(task_id, note_id, created_at, reason) "
                    "VALUES (:task_id, :note_id, :created_at, 'task_conflict')"
                ), {"task_id": task_id, "note_id": note_id, "created_at": created_at})
                continue

            if note_id in assigned_note_ids:
                conn.execute(text(
                    "INSERT INTO task_note_link_migration_backup(task_id, note_id, created_at, reason) "
                    "VALUES (:task_id, :note_id, :created_at, 'note_conflict')"
                ), {"task_id": task_id, "note_id": note_id, "created_at": created_at})
                continue

            conn.execute(text(
                "UPDATE notes SET task_id = :task_id WHERE id = :note_id"
            ), {"task_id": task_id, "note_id": note_id})
            assigned_task_ids.add(task_id)
            assigned_note_ids.add(note_id)

        # 迁移完成，删除旧表，防止下次启动重复执行
        conn.execute(text("DROP TABLE IF EXISTS task_note_links"))


def get_session():
    """获取一个新的数据库会话"""
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionFactory()


def get_session_factory():
    """获取会话工厂"""
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionFactory

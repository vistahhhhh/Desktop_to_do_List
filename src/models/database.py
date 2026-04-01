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

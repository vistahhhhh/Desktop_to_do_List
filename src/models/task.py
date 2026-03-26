"""任务数据模型"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship, backref
from src.models.database import Base


# 任务-标签 多对多关联表
task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(20), nullable=False)        # 'long_term' | 'short_term'
    due_date = Column(Date, nullable=True)                 # 长期任务截止日期
    priority = Column(String(10), default="medium")        # 'high' | 'medium' | 'low'
    status = Column(String(20), default="todo")            # 'todo' | 'in_progress' | 'done' | 'cancelled'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    is_deleted = Column(Integer, default=0, server_default="0")  # 0=正常, 1=回收站
    task_date = Column(Date, nullable=True)  # 今日任务所属日期
    parent_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)  # 分任务父级ID

    # 多对多关系
    tags = relationship("Tag", secondary=task_tags, backref="tasks", lazy="joined")

    # 自引用：分任务列表
    subtasks = relationship(
        'Task',
        backref=backref('parent', remote_side='Task.id'),
        foreign_keys='[Task.parent_id]',
        lazy='select',
    )

    # 枚举常量
    TYPE_LONG_TERM = "long_term"
    TYPE_SHORT_TERM = "short_term"
    TYPE_WEEKLY = "weekly"
    VALID_TYPES = (TYPE_LONG_TERM, TYPE_SHORT_TERM, TYPE_WEEKLY)

    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"
    VALID_PRIORITIES = (PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW)

    STATUS_TODO = "todo"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    VALID_STATUSES = (STATUS_TODO, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED)

    def __repr__(self):
        return (
            f"<Task(id={self.id}, title='{self.title}', "
            f"type='{self.task_type}', status='{self.status}')>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": self.priority,
            "status": self.status,
            "tags": [tag.to_dict() for tag in self.tags],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

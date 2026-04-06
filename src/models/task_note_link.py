"""任务-便签关联模型"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from src.models.database import Base


class TaskNoteLink(Base):
    __tablename__ = "task_note_links"
    __table_args__ = (
        UniqueConstraint("task_id", "note_id", name="uq_task_note"),
        Index("ix_task_note_task_id", "task_id"),
        Index("ix_task_note_note_id", "note_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    task = relationship("Task", back_populates="note_links")
    note = relationship("Note", back_populates="task_links")

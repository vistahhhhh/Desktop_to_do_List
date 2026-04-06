"""便签数据模型"""

import re
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from src.models.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=True, default="")
    body_html = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    deleted = Column(Boolean, default=False, server_default="0")
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), unique=True, nullable=True)

    # 便签-任务 一对一关系
    linked_task = relationship("Task", back_populates="linked_note", uselist=False)

    def display_name(self) -> str:
        # 有标题：显示完整标题（不限字数）
        if self.title and self.title.strip():
            one_line = re.sub(r"\s+", " ", self.title.strip())
            return one_line
        # 无标题：显示正文前10字
        raw = self.body_html or ""
        # 先移除 <style>...</style> / <script>...</script> 块（含内容）
        raw = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', raw, flags=re.DOTALL | re.IGNORECASE)
        # 再移除所有 HTML 标签
        plain = re.sub(r'<[^>]+>', '', raw)
        # 移除 HTML 实体
        plain = re.sub(r'&[a-zA-Z]+;', '', plain).strip()
        plain = re.sub(r"\s+", " ", plain)
        if not plain:
            return "（无内容）"
        return (plain[:10] + "…") if len(plain) > 10 else plain

    def __repr__(self):
        return f"<Note(id={self.id}, title='{self.title}')>"

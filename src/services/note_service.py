"""便签服务层"""

import re
from datetime import datetime, timezone

from src.models.note import Note


class NoteService:
    def __init__(self, session):
        self._session = session

    def _extract_plain_text(self, html: str) -> str:
        if not html:
            return ""
        text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        return text.strip()

    def _has_content(self, note: Note) -> bool:
        title = (note.title or "").strip()
        plain = self._extract_plain_text(note.body_html or "")
        return bool(title) or bool(plain)

    def get_all(self) -> list:
        """获取所有未删除的便签，按最后修改时间倒序"""
        notes = (
            self._session.query(Note)
            .filter(Note.deleted == False)  # noqa: E712
            .order_by(Note.updated_at.desc())
            .all()
        )

        to_purge = [n for n in notes if not self._has_content(n)]
        if to_purge:
            for n in to_purge:
                try:
                    self._session.delete(n)
                except Exception:
                    pass
            try:
                self._session.commit()
            except Exception:
                pass
            notes = [n for n in notes if n not in to_purge]

        return notes

    def create(self) -> Note:
        """创建一条新空便签（不自动落库，直到 save/commit）"""
        note = Note(
            title="",
            body_html="",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted=True,
        )
        self._session.add(note)
        self._session.flush()
        return note

    def save(self, note: Note, title: str, body_html: str):
        """保存便签内容"""
        note.title = title.strip()
        note.body_html = body_html
        note.updated_at = datetime.now(timezone.utc)
        note.deleted = False
        self._session.commit()

    def delete(self, note_id: int):
        """软删除便签"""
        note = self._session.get(Note, note_id)
        if note:
            note.deleted = True
            self._session.commit()

    def get_by_id(self, note_id: int):
        return self._session.get(Note, note_id)

    def get_deleted(self) -> list:
        """获取所有已软删除的便签，按删除时间倒序"""
        return (
            self._session.query(Note)
            .filter(Note.deleted == True)  # noqa: E712
            .order_by(Note.updated_at.desc())
            .all()
        )

    def restore(self, note_id: int):
        """恢复软删除的便签"""
        note = self._session.get(Note, note_id)
        if note:
            note.deleted = False
            self._session.commit()

    def permanent_delete(self, note_id: int):
        """永久删除便签"""
        note = self._session.get(Note, note_id)
        if note:
            self._session.delete(note)
            self._session.commit()

    def clear_deleted(self):
        """清空回收站"""
        deleted = self.get_deleted()
        for note in deleted:
            self._session.delete(note)
        self._session.commit()

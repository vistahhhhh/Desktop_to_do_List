"""任务-便签关联服务（一对一）"""

from sqlalchemy.exc import IntegrityError

from src.models.task import Task
from src.models.note import Note


class LinkService:
    def __init__(self, session):
        self._session = session

    def bind_note_to_task(self, task_id: int, note_id: int, replace: bool = False) -> bool:
        """将便签绑定到任务（一对一）。"""
        task = self._session.get(Task, task_id)
        note = self._session.get(Note, note_id)
        if task is None or note is None:
            return False

        # 已经是同一对关联，直接返回
        if note.task_id == task_id:
            return False

        # 检查当前便签是否已关联其他任务
        if note.task_id is not None and note.task_id != task_id and not replace:
            return False

        # 检查目标任务是否已被其他便签关联
        conflict = (
            self._session.query(Note)
            .filter(Note.task_id == task_id, Note.id != note_id)
            .first()
        )
        if conflict is not None and not replace:
            return False

        try:
            # 批量清除所有持有目标 task_id 的便签（绕过 ORM 缓存）
            self._session.query(Note).filter(
                Note.task_id == task_id, Note.id != note_id
            ).update({Note.task_id: None}, synchronize_session="fetch")
            self._session.flush()

            # 清除当前便签的旧关联
            if note.task_id is not None and note.task_id != task_id:
                note.task_id = None
                self._session.flush()

            note.task_id = task_id
            self._session.commit()
            return True
        except IntegrityError:
            self._session.rollback()
            return False

    def unbind_by_task(self, task_id: int) -> bool:
        note = self.get_note_for_task(task_id, include_deleted=True)
        if note is None:
            return False
        note.task_id = None
        self._session.commit()
        return True

    def unbind_by_note(self, note_id: int) -> bool:
        note = self._session.get(Note, note_id)
        if note is None or note.task_id is None:
            return False
        note.task_id = None
        self._session.commit()
        return True

    def get_note_for_task(self, task_id: int, include_deleted: bool = False) -> Note | None:
        q = self._session.query(Note).filter(Note.task_id == task_id)
        if not include_deleted:
            q = q.filter(Note.deleted == False)  # noqa: E712
        return q.order_by(Note.updated_at.desc()).first()

    def get_task_for_note(self, note_id: int) -> Task | None:
        note = self._session.get(Note, note_id)
        if note is None or note.task_id is None:
            return None
        return (
            self._session.query(Task)
            .filter(Task.id == note.task_id, Task.is_deleted != 1)
            .first()
        )

    def has_note(self, task_id: int) -> bool:
        return self.get_note_for_task(task_id) is not None

    def count_notes_for_task(self, task_id: int) -> int:
        return 1 if self.get_note_for_task(task_id) is not None else 0

    def unlink_past_daily_tasks(self):
        """自动解除过往每日待办任务的便签关联（保留便签，仅断开链接）"""
        from datetime import date
        today = date.today()
        past_linked = (
            self._session.query(Note)
            .join(Task, Note.task_id == Task.id)
            .filter(
                Note.task_id.isnot(None),
                Task.task_type == 'short_term',
                Task.task_date < today,
                Task.task_date.isnot(None),
            )
            .all()
        )
        if not past_linked:
            return
        for note in past_linked:
            note.task_id = None
        self._session.commit()

    # ===== 兼容包装（便于渐进改造） =====
    def link(self, task_id: int, note_id: int, replace: bool = False) -> bool:
        return self.bind_note_to_task(task_id, note_id, replace=replace)

    def unlink(self, task_id: int, note_id: int | None = None) -> bool:
        note = self.get_note_for_task(task_id, include_deleted=True)
        if note is None:
            return False
        if note_id is not None and note.id != note_id:
            return False
        return self.unbind_by_task(task_id)

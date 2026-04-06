"""筛选服务 - 智能清单与多维筛选"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import and_, or_, case
from sqlalchemy.orm import Session

from src.models.task import Task, task_tags
from src.models.tag import Tag


class FilterService:
    """筛选与智能清单业务逻辑层"""

    def __init__(self, session: Session):
        self._session = session

    # ========== 智能清单 ==========

    # 已完成排到最后
    _done_last = case((Task.status == Task.STATUS_DONE, 1), else_=0)

    def get_today_tasks(self) -> List[Task]:
        """
        今日待办：task_date==今天的短期任务 + 遗留未完成任务。
        遗留任务 = task_date < 今天 且 status 为 todo/in_progress。
        """
        today = date.today()
        visible_statuses = [Task.STATUS_TODO, Task.STATUS_IN_PROGRESS, Task.STATUS_DONE]
        # 今天的任务
        today_tasks = (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_SHORT_TERM,
                Task.task_date == today,
                Task.status.in_(visible_statuses),
                Task.is_deleted != 1,
                Task.parent_id.is_(None),
            )
            .order_by(self._done_last, Task.priority.desc(), Task.created_at.desc())
            .all()
        )
        # 遗留任务（过去未完成的）
        carryover = (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_SHORT_TERM,
                or_(Task.task_date < today, Task.task_date.is_(None)),
                Task.status.in_([Task.STATUS_TODO, Task.STATUS_IN_PROGRESS]),
                Task.is_deleted != 1,
                Task.parent_id.is_(None),
            )
            .order_by(Task.task_date.asc(), Task.priority.desc())
            .all()
        )
        return carryover + today_tasks

    def get_week_tasks(self) -> List[Task]:
        """
        本周任务：仅本周任务（weekly），显示活跃+已完成。
        """
        visible_statuses = [Task.STATUS_TODO, Task.STATUS_IN_PROGRESS, Task.STATUS_DONE]
        return (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_WEEKLY,
                Task.status.in_(visible_statuses),
                Task.is_deleted != 1,
                Task.parent_id.is_(None),
            )
            .order_by(self._done_last, Task.due_date.asc(), Task.priority.desc())
            .all()
        )

    def get_long_term_tasks(self) -> List[Task]:
        """
        长期任务：仅长期任务（long_term），显示活跃+已完成。
        """
        visible_statuses = [Task.STATUS_TODO, Task.STATUS_IN_PROGRESS, Task.STATUS_DONE]
        return (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_LONG_TERM,
                Task.status.in_(visible_statuses),
                Task.is_deleted != 1,
                Task.parent_id.is_(None),
            )
            .order_by(self._done_last, Task.due_date.asc(), Task.priority.desc())
            .all()
        )

    # ========== 按标签筛选 ==========

    def get_tasks_by_tag(self, tag_id: int) -> List[Task]:
        """根据标签ID筛选任务"""
        return (
            self._session.query(Task)
            .join(task_tags)
            .filter(task_tags.c.tag_id == tag_id, Task.is_deleted != 1,
                    Task.parent_id.is_(None))
            .order_by(self._done_last, Task.created_at.desc())
            .all()
        )

    def get_tasks_by_tags(self, tag_ids: List[int]) -> List[Task]:
        """根据多个标签ID筛选任务（取并集：包含任意一个标签即匹配）"""
        if not tag_ids:
            return []
        return (
            self._session.query(Task)
            .join(task_tags)
            .filter(task_tags.c.tag_id.in_(tag_ids))
            .distinct()
            .order_by(Task.created_at.desc())
            .all()
        )

    # ========== 按状态筛选 ==========

    def get_tasks_by_status(self, status: str) -> List[Task]:
        """根据状态筛选任务"""
        if status not in Task.VALID_STATUSES:
            raise ValueError(f"无效的状态: {status}")
        return (
            self._session.query(Task)
            .filter_by(status=status)
            .order_by(Task.created_at.desc())
            .all()
        )

    def get_active_tasks(self) -> List[Task]:
        """获取所有活跃任务（todo + in_progress）"""
        return (
            self._session.query(Task)
            .filter(Task.status.in_([Task.STATUS_TODO, Task.STATUS_IN_PROGRESS]),
                    Task.is_deleted != 1,
                    Task.parent_id.is_(None))
            .order_by(Task.priority.desc(), Task.created_at.desc())
            .all()
        )

    def get_completed_tasks(self) -> List[Task]:
        """获取所有已完成/已取消的任务"""
        return (
            self._session.query(Task)
            .filter(Task.status.in_([Task.STATUS_DONE, Task.STATUS_CANCELLED]))
            .order_by(Task.updated_at.desc())
            .all()
        )

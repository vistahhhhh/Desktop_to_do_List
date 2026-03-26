"""任务服务 - 任务的增删改查与状态管理"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.task import Task
from src.models.tag import Tag


class TaskService:
    """任务业务逻辑层"""

    def __init__(self, session: Session):
        self._session = session

    def create_task(
        self,
        title: str,
        task_type: str,
        description: Optional[str] = None,
        due_date: Optional[date] = None,
        priority: str = "medium",
        tag_ids: Optional[List[int]] = None,
    ) -> Task:
        """
        创建任务。
        - title: 必填
        - task_type: 'long_term' | 'short_term'
        - description: 可选，支持Markdown
        - due_date: 长期任务截止日期
        - priority: 'high' | 'medium' | 'low'
        - tag_ids: 关联的标签ID列表
        """
        if not title or not title.strip():
            raise ValueError("任务标题不能为空")
        if task_type not in Task.VALID_TYPES:
            raise ValueError(f"无效的任务类型: {task_type}，可选: {Task.VALID_TYPES}")
        if priority not in Task.VALID_PRIORITIES:
            raise ValueError(f"无效的优先级: {priority}，可选: {Task.VALID_PRIORITIES}")

        task = Task(
            title=title.strip(),
            description=description,
            task_type=task_type,
            due_date=due_date,
            priority=priority,
            task_date=date.today() if task_type == Task.TYPE_SHORT_TERM else None,
        )

        # 关联标签
        if tag_ids:
            tags = self._session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            task.tags = tags

        self._session.add(task)
        self._session.commit()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """根据ID获取任务（不含已删除）"""
        return (
            self._session.query(Task)
            .filter(Task.id == task_id, Task.is_deleted != 1)
            .first()
        )

    def get_task_any(self, task_id: int) -> Optional[Task]:
        """根据ID获取任务（包含已删除）"""
        return self._session.query(Task).filter(Task.id == task_id).first()

    def get_all_tasks(self) -> List[Task]:
        """获取所有顶层任务（不含分任务），按创建时间倒序"""
        return (
            self._session.query(Task)
            .filter(Task.parent_id.is_(None))
            .order_by(Task.created_at.desc())
            .all()
        )

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        """
        更新任务属性。
        可更新字段: title, description, task_type, due_date, priority, status, tag_ids
        """
        task = self.get_task(task_id)
        if task is None:
            return None

        # 验证并更新简单字段
        updatable_fields = ("title", "description", "task_type", "due_date", "priority", "status")
        for field in updatable_fields:
            if field in kwargs:
                value = kwargs[field]
                # 字段验证
                if field == "title":
                    if not value or not value.strip():
                        raise ValueError("任务标题不能为空")
                    value = value.strip()
                elif field == "task_type" and value not in Task.VALID_TYPES:
                    raise ValueError(f"无效的任务类型: {value}")
                elif field == "priority" and value not in Task.VALID_PRIORITIES:
                    raise ValueError(f"无效的优先级: {value}")
                elif field == "status" and value not in Task.VALID_STATUSES:
                    raise ValueError(f"无效的状态: {value}")
                setattr(task, field, value)

        # 更新标签关系
        if "tag_ids" in kwargs:
            tag_ids = kwargs["tag_ids"]
            if tag_ids is not None:
                tags = self._session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
                task.tags = tags
            else:
                task.tags = []

        task.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        return task

    def update_status(self, task_id: int, new_status: str) -> Optional[Task]:
        """更新任务状态"""
        if new_status not in Task.VALID_STATUSES:
            raise ValueError(f"无效的状态: {new_status}，可选: {Task.VALID_STATUSES}")
        return self.update_task(task_id, status=new_status)

    def delete_task(self, task_id: int) -> bool:
        """软删除任务（放入回收站），级联软删除子任务，返回是否成功"""
        task = self.get_task(task_id)
        if task is None:
            return False
        task.is_deleted = 1
        task.updated_at = datetime.now(timezone.utc)
        for sub in self.get_subtasks(task_id):
            sub.is_deleted = 1
            sub.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        return True

    def restore_task(self, task_id: int) -> bool:
        """从回收站恢复任务"""
        task = self._session.query(Task).filter_by(id=task_id).first()
        if task is None:
            return False
        task.is_deleted = 0
        task.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        return True

    def permanent_delete_task(self, task_id: int) -> bool:
        """永久删除任务"""
        task = self._session.query(Task).filter_by(id=task_id).first()
        if task is None:
            return False
        self._session.delete(task)
        self._session.commit()
        return True

    def get_deleted_tasks(self) -> List[Task]:
        """获取回收站中的任务"""
        return (
            self._session.query(Task)
            .filter(Task.is_deleted == 1)
            .order_by(Task.updated_at.desc())
            .all()
        )

    def carry_forward(self, task_id: int) -> Optional[Task]:
        """将遗留任务移交到今日"""
        task = self.get_task(task_id)
        if task is None:
            return None
        task.task_date = date.today()
        task.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        return task

    def get_history_tasks(self, max_days: int = 10):
        """获取最近 max_days 天的已过去今日任务，按日期分组（不含今天，不含分任务）"""
        today = date.today()
        cutoff = today - timedelta(days=max_days)
        tasks = (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_SHORT_TERM,
                Task.task_date < today,
                Task.task_date >= cutoff,
                Task.task_date.isnot(None),
                Task.is_deleted != 1,
                Task.parent_id.is_(None),
            )
            .order_by(Task.task_date.desc(), Task.status.asc(), Task.created_at.desc())
            .all()
        )
        # 按日期分组
        grouped = {}
        for t in tasks:
            d = t.task_date
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(t)
        return grouped

    def clear_history_tasks(self):
        """永久删除所有过去的短期任务及其分任务（不含今天）"""
        today = date.today()
        old_tasks = (
            self._session.query(Task)
            .filter(
                Task.task_type == Task.TYPE_SHORT_TERM,
                Task.task_date < today,
                Task.task_date.isnot(None),
                Task.is_deleted != 1,
            )
            .all()
        )
        for t in old_tasks:
            self._session.delete(t)
        self._session.commit()
        return len(old_tasks)

    # ========== 分任务 ==========

    def create_subtask(self, parent_id: int, title: str) -> Task:
        """为指定任务创建分任务"""
        parent = self.get_task(parent_id)
        if parent is None:
            raise ValueError(f"父任务不存在: id={parent_id}")
        if not title or not title.strip():
            raise ValueError("分任务标题不能为空")
        subtask = Task(
            title=title.strip(),
            task_type=parent.task_type,
            priority="medium",
            status="todo",
            parent_id=parent_id,
            task_date=parent.task_date,
            due_date=parent.due_date,
        )
        self._session.add(subtask)
        self._session.commit()
        return subtask

    def get_subtasks(self, task_id: int) -> List[Task]:
        """获取指定任务的分任务列表（不含已删除）"""
        return (
            self._session.query(Task)
            .filter(Task.parent_id == task_id, Task.is_deleted != 1)
            .order_by(Task.created_at.asc())
            .all()
        )

    def add_tag_to_task(self, task_id: int, tag_id: int) -> bool:
        """为任务添加标签"""
        task = self.get_task(task_id)
        if task is None:
            return False
        tag = self._session.query(Tag).filter_by(id=tag_id).first()
        if tag is None:
            return False
        if tag not in task.tags:
            task.tags.append(tag)
            self._session.commit()
        return True

    def remove_tag_from_task(self, task_id: int, tag_id: int) -> bool:
        """移除任务的标签"""
        task = self.get_task(task_id)
        if task is None:
            return False
        tag = self._session.query(Tag).filter_by(id=tag_id).first()
        if tag is None or tag not in task.tags:
            return False
        task.tags.remove(tag)
        self._session.commit()
        return True

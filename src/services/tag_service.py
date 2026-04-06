"""标签服务 - 标签的增删改查"""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.tag import Tag


class TagService:
    """标签业务逻辑层"""

    def __init__(self, session: Session):
        self._session = session

    def create_tag(self, name: str, color: str = "#6366F1", icon: str = "📌") -> Tag:
        """
        创建标签。
        - name: 标签名（必填，唯一）
        - color: 标签颜色（十六进制）
        """
        if not name or not name.strip():
            raise ValueError("标签名不能为空")

        # 去除 # 前缀（用户可能输入 #论文）
        clean_name = name.strip().lstrip("#").strip()
        if not clean_name:
            raise ValueError("标签名不能为空")

        # 检查是否已存在
        existing = self._session.query(Tag).filter_by(name=clean_name).first()
        if existing:
            raise ValueError(f"标签 '{clean_name}' 已存在")

        tag = Tag(name=clean_name, color=color, icon=icon)
        self._session.add(tag)
        self._session.commit()
        return tag

    def get_tag(self, tag_id: int) -> Optional[Tag]:
        """根据ID获取标签"""
        return self._session.query(Tag).filter_by(id=tag_id).first()

    def get_tag_by_name(self, name: str) -> Optional[Tag]:
        """根据名称获取标签"""
        clean_name = name.strip().lstrip("#").strip()
        return self._session.query(Tag).filter_by(name=clean_name).first()

    def get_all_tags(self) -> List[Tag]:
        """获取所有标签，按名称排序"""
        return self._session.query(Tag).order_by(Tag.name).all()

    def update_tag(self, tag_id: int, **kwargs) -> Optional[Tag]:
        """
        更新标签属性。
        可更新字段: name, color
        """
        tag = self.get_tag(tag_id)
        if tag is None:
            return None

        if "name" in kwargs:
            new_name = kwargs["name"]
            if not new_name or not new_name.strip():
                raise ValueError("标签名不能为空")
            clean_name = new_name.strip().lstrip("#").strip()
            # 检查重名（排除自身）
            existing = (
                self._session.query(Tag)
                .filter(Tag.name == clean_name, Tag.id != tag_id)
                .first()
            )
            if existing:
                raise ValueError(f"标签 '{clean_name}' 已存在")
            tag.name = clean_name

        if "color" in kwargs:
            tag.color = kwargs["color"]

        self._session.commit()
        return tag

    def delete_tag(self, tag_id: int) -> bool:
        """删除标签，返回是否成功"""
        tag = self.get_tag(tag_id)
        if tag is None:
            return False
        self._session.delete(tag)
        self._session.commit()
        return True

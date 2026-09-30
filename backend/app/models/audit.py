# -*- coding: utf-8 -*-
"""管理员操作审计日志表

用于记录所有高危/敏感操作（删除用户、删除/发布套题、修改人设等），
满足「人机协同 / 操作留痕」与后续审计追溯需求。"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func

from app.core.database import Base


class AdminAudit(Base):
    __tablename__ = "admin_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, nullable=False, index=True)        # 操作人
    action = Column(String(64), nullable=False)                   # 动作：delete/publish/unpublish/update/approve/reject
    target_type = Column(String(32), nullable=False)              # 对象类型：user/question_set/question/persona/...
    target_id = Column(String(64), nullable=True)                 # 对象 ID
    detail = Column(Text, nullable=True)                          # 变更摘要/原因
    trace_id = Column(String(32), nullable=True)                  # 关联请求 trace_id
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "detail": self.detail,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

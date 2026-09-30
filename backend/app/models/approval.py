# -*- coding: utf-8 -*-
"""内容变更审批表（人机协同 · 人工卡点）

为什么单独一张表而不是只写 admin_audit：
- `admin_audit` 记录的是「已经发生的事」（事后追溯）；
- 本表记录的是「尚未发生、等待人拍板的变更」（事前拦截）。
  高危操作不再即时生效，而是先冻结为一份**变更快照**，
  由拥有 `approve` 权限的人复核后**才真正落库**，驳回则彻底作废。

状态机（单向、终态不可回退）：
    pending ──approve──> approved   （应用变更）
    pending ──reject───> rejected   （作废，不应用）
    pending ──cancel───> cancelled  （提交人主动撤回）
非 pending 状态下再次审批 → ConflictError（防重复点击/并发双审）。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func

from app.core.database import Base


class ContentApproval(Base):
    __tablename__ = "content_approval"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # —— 变更对象 ——
    target_type = Column(String(32), nullable=False, index=True)   # question_set / question / persona
    target_id = Column(String(64), nullable=True)                  # 新增时为 None（尚未产生实体）
    action = Column(String(32), nullable=False)                    # create / update / delete / publish / unpublish
    risk = Column(String(16), nullable=False, default="high")      # high / medium / low

    # —— 变更内容 ——
    payload = Column(Text, nullable=True)      # JSON：真正要写入的字段（create/update 用）
    snapshot = Column(Text, nullable=True)     # JSON：变更前实体快照（复核人靠它看清「要删/改的是什么」）
    summary = Column(String(255), nullable=True)   # 人读摘要，审批列表直接展示

    # —— 状态机 ——
    status = Column(String(16), nullable=False, default="pending", index=True)
    submitter_id = Column(Integer, nullable=False)          # 提交人
    reviewer_id = Column(Integer, nullable=True)            # 复核人
    review_comment = Column(Text, nullable=True)            # 复核意见（驳回时必填更有价值）
    last_error = Column(Text, nullable=True)                # 应用失败原因（保持 pending 以便修正后重试）
    trace_id = Column(String(32), nullable=True)            # 关联提交请求的 trace_id（P4 链路可查）

    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "action": self.action,
            "risk": self.risk,
            "payload": self.payload,
            "snapshot": self.snapshot,
            "summary": self.summary,
            "status": self.status,
            "submitter_id": self.submitter_id,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "last_error": self.last_error,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

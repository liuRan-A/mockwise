# -*- coding: utf-8 -*-
"""
人机协同：高危操作人工审核卡点（草稿 → 待审 → 复核）

设计取舍（对应「不追求全自动化」）：
- **只有高危动作进审批**。低危的增删改若也排队，会把人淹没在审批流里，
  最终变成「闭眼点通过」，反而失去卡点意义。高危判定 = 不可逆 或 直接影响线上：
  `delete`（连带删除题目）、`publish` / `unpublish`（改变候选人可见的题库）。
- **变更先冻结为快照**。提交时把 payload 与「变更前实体」一起存下来，
  复核人看到的是「要删掉的是什么」，而不是一个冰冷的 ID —— 否则审批只是走过场。
- **批准后才会真正落库**；驳回则彻底作废，实体保持原样。
- **审批动作本身留审计 + 绑定 trace_id**，谁在什么链路下放行的一路可查（复用 P1/P4）。
- **应用失败不吞掉**：保持 pending 并记 `last_error`，修正后可重试，避免"点了通过但其实没生效"。

状态机：
    pending ──approve──> approved
    pending ──reject───> rejected
    pending ──cancel───> cancelled
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger, request_id_var
from app.core.rbac import record_audit
from app.models.approval import ContentApproval

log = get_logger("approval")

# —— 动作风险分级 ——
RISK_HIGH = {"delete", "publish", "unpublish"}
RISK_MEDIUM = {"update"}
RISK_LOW = {"create"}

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"


def risk_of(action: str) -> str:
    if action in RISK_HIGH:
        return "high"
    if action in RISK_MEDIUM:
        return "medium"
    return "low"


def requires_approval(action: str) -> bool:
    """该动作是否需要人工复核。可通过 settings.APPROVAL_ENABLED 全局关闭。"""
    if not settings.APPROVAL_ENABLED:
        return False
    actions = {a.strip() for a in (settings.APPROVAL_ACTIONS or "").split(",") if a.strip()}
    return action in actions


# ============ 查询 ============
def get(db: Session, approval_id: int) -> Optional[ContentApproval]:
    return db.get(ContentApproval, approval_id)


def list_approvals(db: Session, status: Optional[str] = None,
                   target_type: Optional[str] = None, limit: int = 50) -> list[ContentApproval]:
    q = db.query(ContentApproval)
    if status:
        q = q.filter(ContentApproval.status == status)
    if target_type:
        q = q.filter(ContentApproval.target_type == target_type)
    return q.order_by(ContentApproval.id.desc()).limit(limit).all()


def pending_count(db: Session) -> int:
    return db.query(ContentApproval).filter(ContentApproval.status == STATUS_PENDING).count() or 0


# ============ 快照 ============
def _snapshot(db: Session, target_type: str, target_id) -> Optional[dict]:
    """记录变更前实体，供复核人判断影响面。查不到返回 None（新增场景本就没有）。"""
    try:
        if target_type == "question_set":
            from app.models.question import QuestionSet
            obj = db.get(QuestionSet, int(target_id)) if target_id else None
        elif target_type == "question":
            from app.models.question import Question
            obj = db.get(Question, int(target_id)) if target_id else None
        elif target_type == "persona":
            from app.models.question import PeerPersona
            obj = db.get(PeerPersona, int(target_id)) if target_id else None
        else:
            return None
        if not obj:
            return None
        out = {}
        for col in obj.__table__.columns:
            v = getattr(obj, col.name)
            if isinstance(v, datetime):
                v = v.isoformat()
            elif isinstance(v, (dict, list)):
                v = v  # JSON 列原样保留
            elif not isinstance(v, (str, int, float, type(None))):
                v = str(v)
            out[col.name] = v
        return out
    except Exception:
        log.exception("snapshot failed type=%s id=%s", target_type, target_id)
        return None


def _dump(v) -> Optional[str]:
    if v is None:
        return None
    try:
        return json.dumps(v, ensure_ascii=False, default=str)
    except Exception:
        return str(v)


# ============ 提交（进入草稿态） ============
def submit(db: Session, *, target_type: str, target_id=None, action: str,
           payload: Optional[dict] = None, summary: str = "",
           submitter_id: int) -> ContentApproval:
    """把一次高危变更冻结为待审记录。**此时不改动任何业务数据。**"""
    ap = ContentApproval(
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        action=action,
        risk=risk_of(action),
        payload=_dump(payload),
        snapshot=_dump(_snapshot(db, target_type, target_id)),
        summary=(summary or "")[:255],
        status=STATUS_PENDING,
        submitter_id=submitter_id,
        trace_id=request_id_var.get(),
    )
    db.add(ap)
    db.commit()
    db.refresh(ap)
    record_audit(db, submitter_id, f"submit:{action}", f"approval:{target_type}", ap.id, summary)
    log.info("approval submitted id=%s action=%s target=%s:%s by=%s",
             ap.id, action, target_type, target_id, submitter_id)
    return ap


# ============ 应用（只有批准后才执行） ============
def apply(db: Session, ap: ContentApproval) -> str:
    """真正执行变更。抛异常时由 approve 回滚并保持 pending。"""
    from app.crud import question as q_crud
    from app.crud import peer as p_crud

    tid = int(ap.target_id) if ap.target_id else None
    data = {}
    if ap.payload:
        try:
            data = json.loads(ap.payload) or {}
        except Exception:
            raise ValueError(f"审批 payload 无法解析：{ap.payload[:100]}")

    with _span(f"approval.apply.{ap.action}"):
        if ap.target_type == "question_set":
            if ap.action == "delete":
                if not q_crud.delete_set(db, tid):
                    raise LookupError("套题不存在或已被删除")
                return f"已删除套题 #{tid}"
            if ap.action in ("publish", "unpublish"):
                published = int(data.get("published", 1 if ap.action == "publish" else 0))
                if not q_crud.set_publish(db, tid, published):
                    raise LookupError("套题不存在")
                return f"套题 #{tid} 已{'上架' if published else '下架'}"
            if ap.action == "update":
                if not q_crud.update_set(db, tid, data):
                    raise LookupError("套题不存在")
                return f"已更新套题 #{tid}"
            if ap.action == "create":
                s = q_crud.create_set(db, data)
                return f"已新建套题 #{s.id}"

        elif ap.target_type == "question":
            if ap.action == "delete":
                if not q_crud.delete_question(db, tid):
                    raise LookupError("题目不存在或已被删除")
                return f"已删除题目 #{tid}"
            if ap.action == "update":
                if not q_crud.update_question(db, tid, data):
                    raise LookupError("题目不存在")
                return f"已更新题目 #{tid}"
            if ap.action == "create":
                sid = int(data.pop("set_id")) if data.get("set_id") else None
                if not sid:
                    raise ValueError("缺少 set_id")
                q = q_crud.create_question(db, sid, data)
                return f"已新建题目 #{q.id}"

        elif ap.target_type == "persona":
            if ap.action == "delete":
                if not p_crud.delete_persona(db, tid):
                    raise LookupError("人设不存在或已被删除")
                return f"已删除人设 #{tid}"
            if ap.action == "update":
                if not p_crud.update_persona(db, tid, data):
                    raise LookupError("人设不存在")
                return f"已更新人设 #{tid}"
            if ap.action == "create":
                p = p_crud.create_persona(db, data)
                return f"已新建人设 #{p.id}"

    raise ValueError(f"不支持的审批目标/动作：{ap.target_type}/{ap.action}")


def _span(name: str):
    """追踪 span（P4）。tracing 不可用时退化为 no-op，不影响审批。"""
    try:
        from app.services.tracing import span
        return span(name, kind="approval")
    except Exception:
        from contextlib import nullcontext
        return nullcontext()


# ============ 复核（人工卡点） ============
def approve(db: Session, approval_id: int, reviewer_id: int,
            comment: Optional[str] = None) -> ContentApproval:
    ap = db.get(ContentApproval, approval_id)
    if not ap:
        from app.core.errors import NotFoundError
        raise NotFoundError("审批单不存在")
    if ap.status != STATUS_PENDING:
        from app.core.errors import ConflictError
        raise ConflictError(f"审批单已是 {ap.status} 状态，不能重复处理")
    if not settings.APPROVAL_ALLOW_SELF and ap.submitter_id == reviewer_id:
        from app.core.errors import ForbiddenError
        raise ForbiddenError("提交人不能自行审批（需双人复核）")

    try:
        result = apply(db, ap)
    except Exception as e:
        db.rollback()          # 撤销 apply 的半成品写入
        ap = db.get(ContentApproval, approval_id)   # rollback 后重新取，避免操作已失效对象
        ap.last_error = str(e)[:500]
        ap.review_comment = comment
        db.commit()
        log.warning("approval apply failed id=%s: %s", approval_id, e)
        from app.core.errors import BadRequestError
        raise BadRequestError(f"应用变更失败，审批单保持待审：{e}")

    ap.status = STATUS_APPROVED
    ap.reviewer_id = reviewer_id
    ap.review_comment = comment
    ap.last_error = None
    ap.reviewed_at = datetime.now()
    db.commit()
    db.refresh(ap)
    record_audit(db, reviewer_id, f"approve:{ap.action}", f"approval:{ap.target_type}",
                 ap.id, f"{result}｜意见：{comment or '无'}")
    log.info("approval approved id=%s by=%s result=%s", ap.id, reviewer_id, result)
    return ap


def reject(db: Session, approval_id: int, reviewer_id: int,
           comment: Optional[str] = None) -> ContentApproval:
    ap = db.get(ContentApproval, approval_id)
    if not ap:
        from app.core.errors import NotFoundError
        raise NotFoundError("审批单不存在")
    if ap.status != STATUS_PENDING:
        from app.core.errors import ConflictError
        raise ConflictError(f"审批单已是 {ap.status} 状态，不能重复处理")

    ap.status = STATUS_REJECTED
    ap.reviewer_id = reviewer_id
    ap.review_comment = comment or "驳回（未填写意见）"
    ap.reviewed_at = datetime.now()
    db.commit()
    db.refresh(ap)
    record_audit(db, reviewer_id, f"reject:{ap.action}", f"approval:{ap.target_type}",
                 ap.id, f"已驳回，未产生任何变更｜意见：{comment or '无'}")
    log.info("approval rejected id=%s by=%s", ap.id, reviewer_id)
    return ap


def cancel(db: Session, approval_id: int, user_id: int) -> ContentApproval:
    """提交人主动撤回（自己发现自己填错了）。"""
    ap = db.get(ContentApproval, approval_id)
    if not ap:
        from app.core.errors import NotFoundError
        raise NotFoundError("审批单不存在")
    if ap.status != STATUS_PENDING:
        from app.core.errors import ConflictError
        raise ConflictError(f"审批单已是 {ap.status} 状态，不能撤回")
    if ap.submitter_id != user_id:
        from app.core.errors import ForbiddenError
        raise ForbiddenError("只能撤回自己提交的审批单")

    ap.status = STATUS_CANCELLED
    ap.reviewer_id = user_id
    ap.reviewed_at = datetime.now()
    db.commit()
    db.refresh(ap)
    record_audit(db, user_id, f"cancel:{ap.action}", f"approval:{ap.target_type}", ap.id, "提交人撤回")
    return ap

# -*- coding: utf-8 -*-
"""人工审批卡点路由：高危内容变更的「待审 → 复核」入口"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_permission, PERM_MANAGE_CONTENT, PERM_APPROVE
from app.core.logging_config import get_logger
from app.models.user import User
from app.schemas.common import R
from app.services import approval as appr

router = APIRouter(prefix="/admin/approvals", tags=["approval"])
log = get_logger("approval.api")


class ReviewBody(BaseModel):
    comment: str | None = None


def _out(ap) -> dict:
    d = ap.to_dict()
    # payload/snapshot 在列表里只给摘要，避免返回体过大；详情接口给全量
    d["payload"] = None
    d["snapshot"] = None
    return d


@router.get("", response_model=R, summary="审批单列表")
def list_approvals(
    status: str | None = Query(None, description="pending/approved/rejected/cancelled"),
    target_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)),
    db: Session = Depends(get_db),
):
    rows = appr.list_approvals(db, status=status, target_type=target_type, limit=limit)
    return R.ok([_out(r) for r in rows])


@router.get("/pending-count", response_model=R, summary="待我复核数量")
def pending_count(
    admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)),
    db: Session = Depends(get_db),
):
    return R.ok({"pending": appr.pending_count(db)})


@router.get("/{approval_id}", response_model=R, summary="审批单详情（含变更快照）")
def get_approval(
    approval_id: int,
    admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)),
    db: Session = Depends(get_db),
):
    ap = appr.get(db, approval_id)
    if not ap:
        return R.fail("审批单不存在")
    return R.ok(ap.to_dict())


@router.post("/{approval_id}/approve", response_model=R, summary="批准并应用变更")
def approve(
    approval_id: int,
    body: ReviewBody | None = None,
    admin: User = Depends(require_permission(PERM_APPROVE)),
    db: Session = Depends(get_db),
):
    ap = appr.approve(db, approval_id, admin.id, body.comment if body else None)
    return R.ok(ap.to_dict())


@router.post("/{approval_id}/reject", response_model=R, summary="驳回（变更不生效）")
def reject(
    approval_id: int,
    body: ReviewBody | None = None,
    admin: User = Depends(require_permission(PERM_APPROVE)),
    db: Session = Depends(get_db),
):
    ap = appr.reject(db, approval_id, admin.id, body.comment if body else None)
    return R.ok(ap.to_dict())


@router.post("/{approval_id}/cancel", response_model=R, summary="提交人撤回")
def cancel(
    approval_id: int,
    admin: User = Depends(require_permission(PERM_MANAGE_CONTENT)),
    db: Session = Depends(get_db),
):
    ap = appr.cancel(db, approval_id, admin.id)
    return R.ok(ap.to_dict())

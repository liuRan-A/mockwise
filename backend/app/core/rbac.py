# -*- coding: utf-8 -*-
"""
权限控制（RBAC-lite）+ 审计留痕

设计原则：
- 角色仍只有 user / admin 两档，但把「权限」从角色解耦为「权限点（permission）」，
  后续要加新权限只需在这里加常量 + 在 ROLE_PERMS 里分配，不动路由代码；
- `require_permission(perm)` 作为 FastAPI 依赖直接套在敏感路由上，缺权限抛 ForbiddenError；
- `record_audit(...)` 在敏感操作提交后落一条审计记录（失败不影响主流程，仅告警）。
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.user import User
from app.core.database import get_db
from app.core.logging_config import get_logger, request_id_var
from app.models.audit import AdminAudit

log = get_logger("rbac")

# —— 权限点（按需扩展）——
PERM_MANAGE_USERS = "manage:users"
PERM_MANAGE_CONTENT = "manage:content"      # 套题 / 题目 / 群面人设
PERM_MANAGE_REPORTS = "manage:reports"
PERM_VIEW_STATS = "view:stats"
PERM_APPROVE = "approve"                     # 人工复核/审批卡点

# —— 角色 → 权限集合 ——
ROLE_PERMS: dict[str, set] = {
    "admin": {
        PERM_MANAGE_USERS,
        PERM_MANAGE_CONTENT,
        PERM_MANAGE_REPORTS,
        PERM_VIEW_STATS,
        PERM_APPROVE,
    },
    "user": set(),
}


def require_permission(perm: str):
    """返回一个 FastAPI 依赖：校验当前用户是否拥有该权限点。"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if perm not in ROLE_PERMS.get(user.role, set()):
            from app.core.errors import ForbiddenError
            raise ForbiddenError(f"需要权限：{perm}")
        return user

    return checker


def record_audit(
    db: Session,
    actor_id: int,
    action: str,
    target_type: str,
    target_id=None,
    detail: str | None = None,
) -> None:
    """写入一条管理员操作审计记录。失败仅告警，不阻断主流程。"""
    try:
        db.add(AdminAudit(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
            trace_id=request_id_var.get(),   # 修正：此前误用 user_id_var，导致审计表 trace_id 存的是用户 ID
        ))
        db.commit()
    except Exception:
        log.exception("audit record failed actor=%s action=%s", actor_id, action)

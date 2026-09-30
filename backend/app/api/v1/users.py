# -*- coding: utf-8 -*-
"""用户管理（管理员）：创建 / 编辑 / 删除 / 启用禁用（列表/详情见 admin.py）

配合 admin.py 已有的：GET /admin/users（列表）、GET /admin/users/{id}（详情）、
PATCH /admin/users/{id}/status（启用禁用）。这里补齐「增 / 改 / 删」。
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_permission, record_audit, PERM_MANAGE_USERS
from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.models.user import User
from app.crud import user as u_crud
from app.schemas.common import R

router = APIRouter(prefix="/admin/users", tags=["user-admin"])
log = get_logger("user.admin")


class UserCreate(BaseModel):
    phone: str
    password: str
    nickname: str = ""
    target_position: str = ""
    role: str = "user"          # user / admin


class UserUpdate(BaseModel):
    nickname: str | None = None
    target_position: str | None = None
    role: str | None = None
    password: str | None = None          # 留空=不修改密码
    status: str | None = None            # active / paused


def _user_out(u: User) -> dict:
    from datetime import datetime
    return {
        "id": u.id, "phone": u.phone, "nickname": u.nickname,
        "target_position": u.target_position, "role": u.role, "status": u.status,
        "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
        "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "",
    }


@router.post("", response_model=R, summary="创建用户")
def create_user(payload: UserCreate,
                admin: User = Depends(require_permission(PERM_MANAGE_USERS)),
                db: Session = Depends(get_db)):
    if db.query(func.count(User.id)).filter(User.phone == payload.phone).scalar():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该手机号已注册")
    u = u_crud.create_user(
        db, phone=payload.phone, password=payload.password, nickname=payload.nickname)
    u.target_position = payload.target_position
    u.role = payload.role if payload.role in ("user", "admin") else "user"
    db.commit()
    db.refresh(u)
    record_audit(db, admin.id, "create", "user", u.id, f"phone={u.phone} role={u.role}")
    return R.ok(_user_out(u))


@router.put("/{uid}", response_model=R, summary="编辑用户（资料/角色/密码/状态）")
def update_user(uid: int, payload: UserUpdate,
                admin: User = Depends(require_permission(PERM_MANAGE_USERS)),
                db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if payload.nickname is not None:
        u.nickname = payload.nickname
    if payload.target_position is not None:
        u.target_position = payload.target_position
    if payload.role is not None:
        if payload.role not in ("user", "admin"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色非法")
        # 不能把唯一管理员降级为普通用户
        if u.role == "admin" and payload.role != "admin":
            admin_cnt = db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
            if admin_cnt <= 1:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少保留一名管理员")
        u.role = payload.role
    if payload.status is not None:
        if payload.status not in ("active", "paused", "churned"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "状态非法")
        u.status = payload.status
    if payload.password:
        if len(payload.password) < 6:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码至少 6 位")
        u.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(u)
    record_audit(db, admin.id, "update", "user", uid, f"role={u.role} status={u.status}")
    return R.ok(_user_out(u))


@router.delete("/{uid}", response_model=R, summary="删除用户（不可恢复）")
def delete_user(uid: int,
                admin: User = Depends(require_permission(PERM_MANAGE_USERS)),
                db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if u.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除当前登录的账号")
    if u.role == "admin":
        admin_cnt = db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
        if admin_cnt <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少保留一名管理员")
    db.delete(u)            # 级联删除其配额/连续天数；面试场次/历史无外键不受影响
    db.commit()
    record_audit(db, admin.id, "delete", "user", uid, f"phone={u.phone}")
    return R.ok({"deleted": uid})

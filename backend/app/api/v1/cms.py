# -*- coding: utf-8 -*-
"""CMS 后台管理路由（需管理员权限）+ 面向用户端公开读取接口

后台：公告/分类/轮播 的增删改查
公开：/cms/* 供候选人端拉取「已发布且在有效期」的公告、轮播、分类，确保重要信息触达
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_permission, record_audit, PERM_MANAGE_CMS
from app.core.logging_config import get_logger
from app.models.user import User
from app.models.cms import Announcement, Category, Carousel
from app.crud import cms as c_crud
from app.schemas.common import R
from app.schemas.cms import (
    AnnouncementCreate, AnnouncementUpdate,
    CategoryCreate, CategoryUpdate,
    CarouselCreate, CarouselUpdate,
)

log = get_logger("cms")

admin = APIRouter(prefix="/admin/cms", tags=["cms-admin"])
public = APIRouter(prefix="/cms", tags=["cms-public"])


# ============ 序列化 helper ============
def _dt(v: datetime | None) -> str | None:
    return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


def _ann_out(a: Announcement) -> dict:
    return {
        "id": a.id, "title": a.title, "content": a.content, "level": a.level,
        "audience": a.audience, "is_pinned": a.is_pinned, "is_published": a.is_published,
        "start_at": _dt(a.start_at), "end_at": _dt(a.end_at),
        "created_at": _dt(a.created_at), "updated_at": _dt(a.updated_at),
    }


def _cat_out(c: Category) -> dict:
    return {
        "id": c.id, "name": c.name, "kind": c.kind, "description": c.description,
        "sort_order": c.sort_order,
        "created_at": _dt(c.created_at), "updated_at": _dt(c.updated_at),
    }


def _car_out(c: Carousel) -> dict:
    return {
        "id": c.id, "title": c.title, "image_url": c.image_url, "link_url": c.link_url,
        "position": c.position, "is_active": c.is_active,
        "start_at": _dt(c.start_at), "end_at": _dt(c.end_at), "sort_order": c.sort_order,
        "created_at": _dt(c.created_at), "updated_at": _dt(c.updated_at),
    }


# ============ 公告（后台） ============
@admin.get("/announcements", response_model=R, summary="公告列表（分页/筛选）")
def list_announcements(level: str = "", audience: str = "",
                       published: int | None = Query(None),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                       db: Session = Depends(get_db)):
    rows, total = c_crud.list_announcements(
        db, level=level or None, audience=audience or None,
        published=published, page=page, page_size=page_size)
    return R.ok({"list": [_ann_out(a) for a in rows], "total": int(total)})


@admin.post("/announcements", response_model=R, summary="新建公告")
def create_announcement(payload: AnnouncementCreate,
                        admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                        db: Session = Depends(get_db)):
    a = c_crud.create_announcement(db, payload.dict())
    record_audit(db, admin.id, "create", "announcement", a.id, f"title={a.title}")
    return R.ok(_ann_out(a))


@admin.put("/announcements/{aid}", response_model=R, summary="编辑公告")
def update_announcement(aid: int, payload: AnnouncementUpdate,
                        admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                        db: Session = Depends(get_db)):
    a = c_crud.update_announcement(db, aid, payload.dict(exclude_unset=True))
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "公告不存在")
    record_audit(db, admin.id, "update", "announcement", aid, f"title={a.title}")
    return R.ok(_ann_out(a))


@admin.delete("/announcements/{aid}", response_model=R, summary="删除公告")
def delete_announcement(aid: int,
                        admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                        db: Session = Depends(get_db)):
    ok = c_crud.delete_announcement(db, aid)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "公告不存在")
    record_audit(db, admin.id, "delete", "announcement", aid)
    return R.ok({"deleted": aid})


# ============ 分类/标签（后台） ============
@admin.get("/categories", response_model=R, summary="分类列表（可按 kind 过滤）")
def list_categories(kind: str = "",
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    rows = c_crud.list_categories(db, kind=kind or None)
    return R.ok([_cat_out(c) for c in rows])


@admin.post("/categories", response_model=R, summary="新建分类")
def create_category(payload: CategoryCreate,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    c = c_crud.create_category(db, payload.dict())
    record_audit(db, admin.id, "create", "category", c.id, f"name={c.name}")
    return R.ok(_cat_out(c))


@admin.put("/categories/{cid}", response_model=R, summary="编辑分类")
def update_category(cid: int, payload: CategoryUpdate,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    c = c_crud.update_category(db, cid, payload.dict(exclude_unset=True))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    record_audit(db, admin.id, "update", "category", cid, f"name={c.name}")
    return R.ok(_cat_out(c))


@admin.delete("/categories/{cid}", response_model=R, summary="删除分类")
def delete_category(cid: int,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    ok = c_crud.delete_category(db, cid)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    record_audit(db, admin.id, "delete", "category", cid)
    return R.ok({"deleted": cid})


# ============ 轮播/广告位（后台） ============
@admin.get("/carousels", response_model=R, summary="轮播列表")
def list_carousels(position: str = "", page: int = Query(1, ge=1),
                   page_size: int = Query(50, ge=1, le=100),
                   admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                   db: Session = Depends(get_db)):
    rows, total = c_crud.list_carousels(db, position=position or None, page=page, page_size=page_size)
    return R.ok({"list": [_car_out(c) for c in rows], "total": int(total)})


@admin.post("/carousels", response_model=R, summary="新建轮播")
def create_carousel(payload: CarouselCreate,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    c = c_crud.create_carousel(db, payload.dict())
    record_audit(db, admin.id, "create", "carousel", c.id, f"title={c.title}")
    return R.ok(_car_out(c))


@admin.put("/carousels/{cid}", response_model=R, summary="编辑轮播")
def update_carousel(cid: int, payload: CarouselUpdate,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    c = c_crud.update_carousel(db, cid, payload.dict(exclude_unset=True))
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "轮播不存在")
    record_audit(db, admin.id, "update", "carousel", cid, f"title={c.title}")
    return R.ok(_car_out(c))


@admin.delete("/carousels/{cid}", response_model=R, summary="删除轮播")
def delete_carousel(cid: int,
                    admin: User = Depends(require_permission(PERM_MANAGE_CMS)),
                    db: Session = Depends(get_db)):
    ok = c_crud.delete_carousel(db, cid)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "轮播不存在")
    record_audit(db, admin.id, "delete", "carousel", cid)
    return R.ok({"deleted": cid})


# ============ 公开读取（用户端触达） ============
@public.get("/announcements", response_model=R, summary="用户端公告（已发布且有效期内）")
def public_announcements(db: Session = Depends(get_db)):
    return R.ok([_ann_out(a) for a in c_crud.public_announcements(db)])


@public.get("/carousels", response_model=R, summary="用户端轮播（启用且有效期内）")
def public_carousels(position: str = "", db: Session = Depends(get_db)):
    rows = c_crud.active_carousels(db, position=position or None)
    return R.ok([_car_out(c) for c in rows])


@public.get("/categories", response_model=R, summary="用户端分类（按 kind 过滤）")
def public_categories(kind: str = "", db: Session = Depends(get_db)):
    rows = c_crud.list_categories(db, kind=kind or None)
    return R.ok([_cat_out(c) for c in rows])

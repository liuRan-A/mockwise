# -*- coding: utf-8 -*-
"""CMS CRUD：公告 / 分类 / 轮播"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cms import Announcement, Category, Carousel


# ============ 公告 ============
def list_announcements(db: Session, *, level=None, audience=None, published=None,
                        page=1, page_size=20):
    q = db.query(Announcement)
    if level:
        q = q.filter(Announcement.level == level)
    if audience:
        q = q.filter(Announcement.audience == audience)
    if published is not None:
        q = q.filter(Announcement.is_published == published)
    total = q.count()
    rows = (q.order_by(Announcement.is_pinned.desc(), Announcement.id.desc())
              .offset((page - 1) * page_size).limit(page_size).all())
    return rows, total


def get_announcement(db: Session, aid: int):
    return db.get(Announcement, aid)


def create_announcement(db: Session, data: dict) -> Announcement:
    a = Announcement(**data)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def update_announcement(db: Session, aid: int, data: dict):
    a = db.get(Announcement, aid)
    if not a:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


def delete_announcement(db: Session, aid: int) -> bool:
    a = db.get(Announcement, aid)
    if not a:
        return False
    db.delete(a)
    db.commit()
    return True


def public_announcements(db: Session):
    """面向用户端：仅已发布且在有效时间窗内的公告，置顶优先。"""
    now = datetime.now()
    rows = (db.query(Announcement).filter(Announcement.is_published == True)
              .order_by(Announcement.is_pinned.desc(), Announcement.id.desc()).all())
    out = []
    for a in rows:
        if a.start_at and a.start_at > now:
            continue
        if a.end_at and a.end_at < now:
            continue
        out.append(a)
    return out


# ============ 分类 ============
def list_categories(db: Session, kind=None):
    q = db.query(Category)
    if kind:
        q = q.filter(Category.kind == kind)
    return q.order_by(Category.sort_order.asc(), Category.id.asc()).all()


def get_category(db: Session, cid: int):
    return db.get(Category, cid)


def create_category(db: Session, data: dict) -> Category:
    c = Category(**data)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_category(db: Session, cid: int, data: dict):
    c = db.get(Category, cid)
    if not c:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


def delete_category(db: Session, cid: int) -> bool:
    c = db.get(Category, cid)
    if not c:
        return False
    db.delete(c)
    db.commit()
    return True


# ============ 轮播 ============
def active_carousels(db: Session, position=None):
    """面向用户端：仅启用且在有效时间窗内的轮播。"""
    now = datetime.now()
    q = db.query(Carousel).filter(Carousel.is_active == True)
    if position:
        q = q.filter(Carousel.position == position)
    rows = q.order_by(Carousel.sort_order.asc(), Carousel.id.asc()).all()
    out = []
    for c in rows:
        if c.start_at and c.start_at > now:
            continue
        if c.end_at and c.end_at < now:
            continue
        out.append(c)
    return out


def list_carousels(db: Session, position=None, page=1, page_size=50):
    q = db.query(Carousel)
    if position:
        q = q.filter(Carousel.position == position)
    total = q.count()
    rows = (q.order_by(Carousel.sort_order.asc(), Carousel.id.desc())
              .offset((page - 1) * page_size).limit(page_size).all())
    return rows, total


def get_carousel(db: Session, cid: int):
    return db.get(Carousel, cid)


def create_carousel(db: Session, data: dict) -> Carousel:
    c = Carousel(**data)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_carousel(db: Session, cid: int, data: dict):
    c = db.get(Carousel, cid)
    if not c:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


def delete_carousel(db: Session, cid: int) -> bool:
    c = db.get(Carousel, cid)
    if not c:
        return False
    db.delete(c)
    db.commit()
    return True

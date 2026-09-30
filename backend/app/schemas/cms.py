# -*- coding: utf-8 -*-
"""CMS 请求模型（响应统一走 R.ok(dict)，由接口内 helper 序列化）"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ——— 公告/通知 ———
class AnnouncementCreate(BaseModel):
    title: str
    content: str = ""
    level: str = "info"                 # info / warning / important
    audience: str = "all"               # all / vip / new / beta
    is_pinned: bool = False
    is_published: bool = True
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    level: Optional[str] = None
    audience: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_published: Optional[bool] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


# ——— 分类/标签 ———
class CategoryCreate(BaseModel):
    name: str
    kind: str = "tag"                   # club / product / position / tag
    description: str = ""
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


# ——— 轮播图/广告位 ———
class CarouselCreate(BaseModel):
    title: str
    image_url: str = ""
    link_url: str = ""
    position: str = "home"              # home / banner / popup
    is_active: bool = True
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    sort_order: int = 0


class CarouselUpdate(BaseModel):
    title: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    sort_order: Optional[int] = None

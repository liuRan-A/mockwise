# -*- coding: utf-8 -*-
"""运营内容管理（CMS）：公告/通知、分类标签、轮播图/广告位"""
from datetime import datetime

from sqlalchemy import BigInteger, String, Text, SmallInteger, Boolean, Enum
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
import sqlalchemy as sa


class Announcement(Base):
    """公告/通知：系统级或定向用户群发布，确保重要信息触达。"""
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level: Mapped[str] = mapped_column(
        Enum("info", "warning", "important", name="ann_level"),
        nullable=False, default="info")
    audience: Mapped[str] = mapped_column(
        Enum("all", "vip", "new", "beta", name="ann_audience"),
        nullable=False, default="all")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3))


class Category(Base):
    """分类/标签：内容分类体系（社团类型、商品类别、岗位、自定义标签等）。"""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    kind: Mapped[str] = mapped_column(
        Enum("club", "product", "position", "tag", name="cat_kind"),
        nullable=False, default="tag")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3))


class Carousel(Base):
    """轮播图/广告位：首页或关键位置展示内容，用于运营活动与信息推广。"""
    __tablename__ = "carousels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    link_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    position: Mapped[str] = mapped_column(
        Enum("home", "banner", "popup", name="car_position"),
        nullable=False, default="home")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3))

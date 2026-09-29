"""用户域 ORM 模型"""
from datetime import datetime, date
from sqlalchemy import (
    BigInteger, String, SmallInteger, Enum, Date, DECIMAL, ForeignKey
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import sqlalchemy as sa


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    avatar_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_position: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "churned", name="user_status"),
        nullable=False, default="active",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )

    quotas: Mapped[list["UserQuota"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    streak: Mapped["UserStreak | None"] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserQuota(Base):
    __tablename__ = "user_quotas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False)
    simulated_left: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    simulated_total: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )

    user: Mapped[User] = relationship(back_populates="quotas")


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    current_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    best_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_practice_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )

    user: Mapped[User] = relationship(back_populates="streak")


class PracticeHistory(Base):
    __tablename__ = "practice_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=0)
    set_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    practiced_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)

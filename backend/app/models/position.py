"""招聘域：岗位 / JD / 简历"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, JSON, SmallInteger, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT, TINYINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import sqlalchemy as sa


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    industry: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_company: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )


class JdDocument(Base):
    __tablename__ = "jd_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("positions.id"), nullable=True)
    raw_text: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    raw_text: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # AI 画像
    file_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    file_type: Mapped[str] = mapped_column(String(16), nullable=False, default="txt")  # pdf/docx/txt
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploaded")  # uploaded/parsed/analyzed/failed
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)  # 1=当前使用
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )

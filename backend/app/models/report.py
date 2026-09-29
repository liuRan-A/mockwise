"""报告域 ORM"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, SmallInteger, JSON, Enum, DECIMAL, ForeignKey
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
import sqlalchemy as sa


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    form_type: Mapped[str] = mapped_column(
        Enum("structured", "group", "semi", name="rep_form_type"),
        nullable=False, default="structured",
    )
    total_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=0)
    dimensions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    comparison: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overview: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))


class ReportHighlight(Base):
    __tablename__ = "report_highlights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    ts_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    category: Mapped[str] = mapped_column(
        Enum("highlight", "risk", name="rh_category"),
        nullable=False, default="highlight",
    )


class ReportRecommendation(Base):
    __tablename__ = "report_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(
        Enum("improve", "practice", "review", name="rr_kind"),
        nullable=False, default="improve",
    )
    content: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

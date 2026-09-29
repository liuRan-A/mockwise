"""面试配置 + 模拟场次域 ORM"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, JSON, SmallInteger, Integer, Enum, DECIMAL, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT, TINYINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import sqlalchemy as sa


class InterviewConfig(Base):
    __tablename__ = "interview_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("positions.id"), nullable=True)
    form_type: Mapped[str] = mapped_column(
        Enum("structured", "group", "semi", name="cfg_form_type"),
        nullable=False, default="structured",
    )
    voice_mode: Mapped[str] = mapped_column(
        Enum("text", "voice", "mixed", name="cfg_voice_mode"),
        nullable=False, default="voice",
    )
    difficulty: Mapped[str] = mapped_column(
        Enum("easy", "medium", "hard", name="cfg_difficulty"),
        nullable=False, default="medium",
    )
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    enable_followup: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)
    peer_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    config_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("interview_configs.id", ondelete="SET NULL"), nullable=True)
    set_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True)
    form_type: Mapped[str] = mapped_column(
        Enum("structured", "group", "semi", name="sess_form_type"),
        nullable=False, default="structured",
    )
    status: Mapped[str] = mapped_column(
        Enum("idle", "preparing", "running", "paused", "done", "aborted", name="sess_status"),
        nullable=False, default="idle",
    )
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    total_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=sa.func.now(3), onupdate=sa.func.now(3)
    )

    questions: Mapped[list["SessionQuestion"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("questions.id", ondelete="RESTRICT"), nullable=True)
    # 动态题（简历 AI 出题）内容：question_id 为空时使用以下字段
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="bank")  # bank/resume
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    time_limit_s: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    seq: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    phase: Mapped[str] = mapped_column(
        Enum("statement", "group_free", "summary", "answer", name="sq_phase"),
        nullable=False, default="answer",
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "active", "done", "skipped", name="sq_status"),
        nullable=False, default="pending",
    )
    transcript: Mapped[str | None] = mapped_column(MEDIUMTEXT, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ref_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # —— 逐题深度分析（v1.1）——
    # 答得好的地方：[{"point":"…","quote":"…（候选人原话/概括）"}]
    strengths: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 欠缺/答得不好的地方：[{"point":"…","why":"…","how":"…改进建议"}]
    gaps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 结构化参考答案：{"key_points":[...], "outline":[...], "sample":"…", "common_traps":[...]}
    ref_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_score: Mapped[float | None] = mapped_column(DECIMAL(5, 2), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    scores: Mapped[list["SessionScore"]] = relationship(cascade="all, delete-orphan")
    metrics: Mapped["SessionMetrics | None"] = relationship(cascade="all, delete-orphan")
    highlights: Mapped[list["SessionHighlight"]] = relationship(cascade="all, delete-orphan")
    recommendations: Mapped[list["SessionRecommendation"]] = relationship(cascade="all, delete-orphan")


class SessionScore(Base):
    __tablename__ = "session_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id", ondelete="CASCADE"), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    comment: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class SessionMetrics(Base):
    __tablename__ = "session_metrics"

    session_question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id", ondelete="CASCADE"), primary_key=True)
    wpm: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    pause_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    pause_ms_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filler_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    interrupt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    extra_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SessionHighlight(Base):
    __tablename__ = "session_highlights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id", ondelete="CASCADE"), nullable=False)
    ts_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(
        Enum("highlight", "filler", "followup", "risk", name="hl_category"),
        nullable=False, default="highlight",
    )
    snippet: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class SessionRecommendation(Base):
    __tablename__ = "session_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(
        Enum("improve", "answer_key", name="rec_kind"),
        nullable=False, default="improve",
    )
    content: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

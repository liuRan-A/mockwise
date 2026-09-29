"""题库域：套题 / 题目"""
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, JSON, SmallInteger, Enum, DECIMAL, ForeignKey
from sqlalchemy.dialects.mysql import TINYINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import sqlalchemy as sa


class QuestionSet(Base):
    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    position_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    form_type: Mapped[str] = mapped_column(
        Enum("structured", "group", "semi", name="qs_form_type"),
        nullable=False, default="structured",
    )
    difficulty: Mapped[str] = mapped_column(
        Enum("easy", "medium", "hard", name="qs_difficulty"),
        nullable=False, default="medium",
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    cover_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    question_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    est_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    match_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False, default=0)
    is_published: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))

    questions: Mapped[list["Question"]] = relationship(back_populates="set", cascade="all, delete-orphan")


class PeerPersona(Base):
    """无领导小组讨论的 AI 虚拟候选人人设（含发言模板库）"""
    __tablename__ = "peer_personas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    style: Mapped[str] = mapped_column(String(32), nullable=False, default="")     # 角色标签：激进派/数据派…
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#3E63DD")
    bio: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    aggressiveness: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=3)  # 1-5 抢话倾向
    openings: Mapped[dict | None] = mapped_column(JSON, nullable=True)    # 个人陈述模板列表
    rebuttals: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # 自由讨论反驳模板列表
    summaries: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # 总结陈词模板列表
    set_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=True)  # 空=通用


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    set_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    form_type: Mapped[str] = mapped_column(
        Enum("structured", "group", "semi", name="q_form_type"),
        nullable=False, default="structured",
    )
    difficulty: Mapped[str] = mapped_column(
        Enum("easy", "medium", "hard", name="q_difficulty"),
        nullable=False, default="medium",
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    dimension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ref_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_limit_s: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=120)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), server_default=sa.func.now(3))

    set: Mapped[QuestionSet] = relationship(back_populates="questions")

"""群面域 ORM"""
from sqlalchemy import BigInteger, String, Text, JSON, SmallInteger, Integer, Enum, ForeignKey
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class GroupDiscussion(Base):
    __tablename__ = "group_discussions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    material_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=18)
    statement_sec: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=60)
    free_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=15)
    summary_sec: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=120)

    members: Mapped[list["GroupMember"]] = relationship(cascade="all, delete-orphan")
    timeline: Mapped[list["GroupTimeline"]] = relationship(cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discussion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("group_discussions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("me", "peer", "host", name="gm_role"),
        nullable=False, default="peer",
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    initial: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#3E63DD")
    talk_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_current_speaker: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=0)


class GroupTimeline(Base):
    __tablename__ = "group_timeline"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discussion_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("group_discussions.id", ondelete="CASCADE"), nullable=False)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("group_members.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[str] = mapped_column(
        Enum("statement", "group_free", "summary", name="gt_phase"),
        nullable=False, default="group_free",
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_interrupted: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=0)
    cited_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

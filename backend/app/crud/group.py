"""群面 CRUD"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.group import GroupDiscussion, GroupMember, GroupTimeline
from app.models.session import InterviewSession


def get_discussion_by_session(db: Session, session_id: int) -> GroupDiscussion | None:
    return db.query(GroupDiscussion).filter(GroupDiscussion.session_id == session_id).first()


def get_discussion_detail(db: Session, session_id: int):
    d = get_discussion_by_session(db, session_id)
    if not d:
        return None
    members = db.query(GroupMember).filter(GroupMember.discussion_id == d.id).all()
    timeline = db.query(GroupTimeline).filter(
        GroupTimeline.discussion_id == d.id
    ).order_by(GroupTimeline.started_at_ms).all()
    return d, members, timeline


def append_timeline(db: Session, discussion_id: int, member_id: int,
                    transcript: str, audio_url: str, duration_ms: int, phase: str = "group_free"):
    # 当前发言者切换
    db.query(GroupMember).filter(
        GroupMember.discussion_id == discussion_id,
        GroupMember.is_current_speaker == 1,
    ).update({GroupMember.is_current_speaker: 0})
    member = db.get(GroupMember, member_id)
    if member:
        member.is_current_speaker = 1
        member.talk_count = (member.talk_count or 0) + 1
    # 计算时间偏移
    last = db.query(GroupTimeline).filter(
        GroupTimeline.discussion_id == discussion_id
    ).order_by(GroupTimeline.started_at_ms.desc()).first()
    started_at_ms = (last.started_at_ms + last.duration_ms) if last else 0
    row = GroupTimeline(
        discussion_id=discussion_id, member_id=member_id, phase=phase,
        transcript=transcript, audio_url=audio_url,
        started_at_ms=started_at_ms, duration_ms=duration_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

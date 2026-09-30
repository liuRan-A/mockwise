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
    """追加一条发言时间线。

    并发安全：对同一场讨论（discussion_id）加行锁串行化，
    避免多用户/多请求同时 append 时出现「当前发言者串台」「时间偏移算错」的竞态。
    锁在 db.commit() 时释放。
    """
    # 锁定本场讨论行，串行化同一讨论的写入
    d = db.query(GroupDiscussion).filter(
        GroupDiscussion.id == discussion_id
    ).with_for_update().first()
    if not d:
        return None
    # 当前发言者切换（锁定相关成员行）
    db.query(GroupMember).filter(
        GroupMember.discussion_id == discussion_id,
        GroupMember.is_current_speaker == 1,
    ).with_for_update().update({GroupMember.is_current_speaker: 0})
    member = db.query(GroupMember).filter(
        GroupMember.id == member_id,
        GroupMember.discussion_id == discussion_id,
    ).with_for_update().first()
    if member:
        member.is_current_speaker = 1
        member.talk_count = (member.talk_count or 0) + 1
    # 计算时间偏移（基于已锁定的数据读取，结果可串行）
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

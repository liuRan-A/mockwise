"""群面路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.schemas.group import RaiseHandIn
from app.crud import group as gc

router = APIRouter(prefix="/group", tags=["group"])


@router.get("/sessions/{session_id}", response_model=R, summary="群面讨论详情")
def get_discussion(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    detail = gc.get_discussion_detail(db, session_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "群面讨论不存在")
    d, members, timeline = detail
    return R.ok({
        "id": d.id, "session_id": d.session_id, "prompt": d.prompt,
        "material_json": d.material_json, "total_minutes": d.total_minutes,
        "statement_sec": d.statement_sec, "free_minutes": d.free_minutes, "summary_sec": d.summary_sec,
        "members": [
            {"id": m.id, "role": m.role, "name": m.name, "initial": m.initial,
             "color": m.color, "talk_count": m.talk_count, "is_current_speaker": m.is_current_speaker}
            for m in members
        ],
        "timeline": [
            {"id": t.id, "member_id": t.member_id, "phase": t.phase, "transcript": t.transcript,
             "audio_url": t.audio_url, "started_at_ms": t.started_at_ms,
             "duration_ms": t.duration_ms, "is_interrupted": t.is_interrupted, "cited_count": t.cited_count}
            for t in timeline
        ],
    })


@router.post("/sessions/{session_id}/raise", response_model=R, summary="举手发言")
def raise_hand(
    session_id: int,
    payload: RaiseHandIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = gc.get_discussion_by_session(db, session_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "群面讨论不存在")
    row = gc.append_timeline(
        db, d.id, payload.member_id,
        payload.transcript, payload.audio_url, payload.duration_ms,
    )
    return R.ok({"timeline_id": row.id})

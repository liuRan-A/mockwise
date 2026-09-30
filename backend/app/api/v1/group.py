"""群面路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.schemas.group import RaiseHandIn, PeerRoundIn
from app.crud import group as gc
from app.crud import session as sc

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


@router.post("/sessions/{session_id}/round", response_model=R, summary="生成一轮 AI 候选人交锋（群面）")
def group_round(
    session_id: int,
    body: PeerRoundIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """后端接管的一轮群面交锋：链式生成 2-3 位 AI 候选人连贯发言（各回应上一位真实观点）。"""
    sess = sc.get_session(db, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    personas = []
    if sess.set_id:
        from app.crud.peer import list_personas_for_session
        personas = list_personas_for_session(db, sess.set_id, limit=6)
    if not personas:
        return R.ok({"turns": [], "engine": "empty"})
    # 召回候选人在群面维度的长期记忆，让虚拟候选人「有针对性地」交锋
    candidate_brief = ""
    try:
        from app.crud.memory import retrieve_relevant
        candidate_brief = retrieve_relevant(db, user.id, dimension="逻辑结构", max_chars=160) or ""
    except Exception:
        candidate_brief = ""
    from app.services.group_agent import generate_round
    turns = generate_round(
        personas=personas, stage=body.stage, topic=body.topic,
        user_text=body.user_text, recent_context=body.recent_context or [],
        candidate_brief=candidate_brief, n_speakers=body.n_speakers,
    )
    engine = turns[0].get("engine") if turns else "empty"
    return R.ok({"turns": turns, "engine": engine})

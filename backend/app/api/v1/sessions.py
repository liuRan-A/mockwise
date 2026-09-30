"""模拟场次路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.schemas.session import SessionCreate, SessionOut, SessionDetail, AnswerSubmit, SessionQuestionDetail
from app.crud import session as sc
from app.crud import question as qc
from app.models.session import SessionQuestion

router = APIRouter(prefix="/sessions", tags=["session"])
log = get_logger("session")


@router.post("", response_model=R, summary="开始一场模拟")
def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qset = qc.get_set(db, payload.set_id)
    if not qset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    cfg = sc.create_config(db, user.id,
                           position_id=payload.position_id,
                           form_type=payload.form_type,
                           voice_mode=payload.voice_mode,
                           difficulty=payload.difficulty,
                           enable_followup=int(payload.enable_followup),
                           peer_count=payload.peer_count)
    sess = sc.start_session(db, user.id, cfg, qset,
                           use_resume=payload.use_resume,
                           resume_count=payload.resume_count)
    db.commit()
    db.refresh(sess)
    return R.ok({"session_id": sess.id, "status": sess.status})


@router.get("/{session_id}", response_model=R, summary="场次详情（含所有题）")
def get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = sc.get_session(db, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    sqs = sc.list_session_questions(db, session_id)
    # 联表带出题干信息（/answer/:sessionId 直达时前端没有套题上下文）
    from app.models.question import Question
    qmap = {}
    qids = [s.question_id for s in sqs if s.question_id]
    if qids:
        for q in db.query(Question).filter(Question.id.in_(qids)).all():
            qmap[q.id] = q
    out = SessionDetail.from_orm(sess).dict()
    out["questions"] = [
        {
            "id": s.id, "session_id": s.session_id, "question_id": s.question_id,
            "seq": s.seq, "phase": s.phase, "status": s.status,
            "transcript": s.transcript, "audio_url": s.audio_url,
            "ref_answer": s.ref_answer, "total_score": s.total_score,
            "duration_ms": s.duration_ms,
            # 动态题（简历出题）优先取 SessionQuestion 自带内容，否则取题库联表
            "question_content": (s.content or (qmap.get(s.question_id).content if qmap.get(s.question_id) else "") or ""),
            "question_category": (s.category or (qmap.get(s.question_id).category if qmap.get(s.question_id) else "") or ""),
            "question_dimension": (s.dimension or (qmap.get(s.question_id).dimension if qmap.get(s.question_id) else "") or ""),
            "time_limit_s": s.time_limit_s or (qmap.get(s.question_id).time_limit_s if qmap.get(s.question_id) else 120) or 120,
            "source": s.source or "bank",
        }
        for s in sqs
    ]
    return R.ok(out)


@router.post("/{session_id}/questions/{sq_id}/answer", response_model=R, summary="提交单题作答")
def submit_answer(
    session_id: int,
    sq_id: int,
    payload: AnswerSubmit,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sq = sc.get_session_question(db, sq_id)
    if not sq or sq.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    sc.submit_answer(db, sq, payload.transcript, payload.audio_url, payload.duration_ms)
    db.commit()
    return R.ok({"total_score": float(sq.total_score or 0)})


@router.post("/{session_id}/finish", response_model=R, summary="结束场次 + 生成报告")
def finish_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = sc.get_session(db, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    rep = sc.finish_session(db, sess)
    if not rep:
        return R.fail("无作答记录，无法生成报告")
    return R.ok({"report_id": rep.id, "session_id": sess.id, "total_score": float(rep.total_score or 0)})


@router.get("/{session_id}/questions/{sq_id}", response_model=R, summary="逐题详情回放")
def get_question_detail(
    session_id: int,
    sq_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = sc.get_session_question(db, sq_id)
    if not detail or detail.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    # 复用 report crud 的逐题详情
    from app.crud import report as rc
    res = rc.get_session_question_detail(db, sq_id)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "详情不存在")
    sq, question, scores, metrics, highlights, recommendations = (
        res["sq"], res["question"], res["scores"], res["metrics"], res["highlights"], res["recommendations"]
    )
    out = {
        "id": sq.id, "session_id": sq.session_id, "question_id": sq.question_id,
        "seq": sq.seq, "phase": sq.phase, "status": sq.status,
        "transcript": sq.transcript, "audio_url": sq.audio_url,
        "ref_answer": sq.ref_answer, "total_score": float(sq.total_score) if sq.total_score is not None else None,
        "duration_ms": sq.duration_ms, "started_at": sq.started_at, "answered_at": sq.answered_at,
        "scores": scores,
        "metrics": {
            "wpm": metrics.wpm, "pause_count": metrics.pause_count,
            "pause_ms_total": metrics.pause_ms_total, "filler_count": metrics.filler_count,
            "interrupt_count": metrics.interrupt_count,
            "extra_json": getattr(metrics, "extra_json", None),
        } if metrics is not None else {
            "wpm": 0, "pause_count": 0, "pause_ms_total": 0,
            "filler_count": 0, "interrupt_count": 0, "extra_json": None,
        },
        "highlights": highlights,
        "recommendations": recommendations,
        "question_content": res.get("content") or (question.content if question else ""),
        "question_category": res.get("category") or (question.category if question else ""),
        "question_dimension": res.get("dimension") or (question.dimension if question else ""),
        "time_limit_s": sq.time_limit_s or (question.time_limit_s if question else 120),
        "source": sq.source or "bank",
        # v1.1：答得好的地方 / 欠缺的地方 / 结构化参考答案
        "strengths": sq.strengths or [],
        "gaps": sq.gaps or [],
        "ref_detail": sq.ref_detail,
    }
    return R.ok(out)


# —— AI 理解 + 建议接口（实时反馈） ——
class FeedbackReq(BaseModel):
    transcript: str
    question_dimension: str = ""
    question_content: str = ""


@router.post("/questions/{sq_id}/feedback")
def get_feedback(
    sq_id: int, body: FeedbackReq,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """AI 理解候选人的回答并给出实时建议"""
    from app.crud.session import analyze_transcript
    sq = db.get(SessionQuestion, sq_id)
    if not sq:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    # 上下文工程：按需召回本题知识片段 + 该候选人在本维度的长期记忆（任一缺失都不影响反馈）
    mem = know = None
    try:
        from app.crud.memory import retrieve_relevant
        from app.services.knowledge import get_question_knowledge
        mem = retrieve_relevant(db, _user.id, dimension=body.question_dimension or "")
        know = get_question_knowledge(ref_detail=sq.ref_detail, ref_answer=sq.ref_answer)
    except Exception as e:  # noqa: BLE001 - 上下文装配失败不应中断实时反馈
        log.warning("[session] 反馈上下文装配失败，回退纯任务上下文: %s", e)
    feedback = analyze_transcript(body.transcript, body.question_dimension, body.question_content,
                                  user_memory=mem, knowledge=know)
    return R.ok(feedback)


# —— 无领导小组讨论：AI 虚拟候选人 ——
@router.get("/{session_id}/peers", response_model=R, summary="本场 AI 候选人列表（群面）")
def get_session_peers(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = sc.get_session(db, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    if sess.form_type != "group":
        return R.ok([])
    from app.crud.peer import list_personas_for_session
    limit = 5
    if sess.config_id:
        from app.models.session import InterviewConfig
        cfg = db.get(InterviewConfig, sess.config_id)
        if cfg and cfg.peer_count:
            limit = cfg.peer_count
    personas = list_personas_for_session(db, sess.set_id, limit=max(1, limit))
    return R.ok([
        {
            "id": p.id, "name": p.name, "style": p.style, "color": p.color,
            "bio": p.bio, "aggressiveness": p.aggressiveness,
        }
        for p in personas
    ])


class PeerTalkReq(BaseModel):
    stage: str = "debate"        # opening / debate / summary
    persona_id: int
    stance: str = ""             # 该候选人所持立场的论点陈述
    topic: str = ""              # 辩题
    target_name: str = ""        # 反驳对象（候选人名或候选人=你）
    other_name: str = ""         # 场上另一位候选人名（整合派话术用）
    user_text: str = ""          # 被反驳的原话（从中摘取观点）
    # —— 上下文：让候选人能引用「最近的对话」而不是只看 user_text ——
    # [{"who":"me"|"peer","name":"...","text":"..."}]
    recent_context: list[dict] = []
    # 这一次发言主要是回应谁：me=候选人 / 某 peer 名 = 回应另一位候选人
    respond_to: str = "me"


@router.post("/{session_id}/peer-talk", response_model=R, summary="生成 AI 候选人发言（群面）")
def peer_talk(
    session_id: int,
    body: PeerTalkReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = sc.get_session(db, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    from app.models.question import PeerPersona
    persona = db.get(PeerPersona, body.persona_id)
    if not persona:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "人设不存在")
    # 本场全部候选人姓名（用于发言中的引用校验/纠偏）
    member_names = [persona.name]
    if sess.set_id:
        from app.crud.peer import list_personas_for_session
        others = list_personas_for_session(db, sess.set_id, limit=6)
        member_names = [p.name for p in others if p.id != persona.id][:5] + [persona.name]
    member_names = list(dict.fromkeys(member_names + ["你"]))
    # 上下文工程：召回候选人在群面维度的长期记忆，让 AI 虚拟候选人「有针对性地」交锋
    candidate_brief = ""
    try:
        from app.crud.memory import retrieve_relevant
        candidate_brief = retrieve_relevant(db, user.id, dimension="逻辑结构", max_chars=160) or ""
    except Exception:
        candidate_brief = ""
    # 后端多智能体编排生成（LLM 校验 + 失败降级模板），前端调用方式不变
    from app.services.group_agent import generate_group_turn
    turn = generate_group_turn(
        persona=persona, stage=body.stage, topic=body.topic, stance=body.stance,
        target_name=body.target_name, other_name=body.other_name,
        user_text=body.user_text, recent_context=body.recent_context or [],
        respond_to=body.respond_to or "me", member_names=member_names,
        candidate_brief=candidate_brief,
    )
    return R.ok({
        "persona_id": persona.id, "name": persona.name,
        "style": persona.style, "color": persona.color,
        "text": turn["content"], "engine": turn.get("engine"),
    })

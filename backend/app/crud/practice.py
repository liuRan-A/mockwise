# -*- coding: utf-8 -*-
"""
薄弱题型分析 + 针对性训练

能力：
1. get_weak_points —— 按「题型 category」和「考察维度 dimension」统计用户历史表现，
   标出薄弱项，并给出可立即开练的专项（优先匹配现成套题，其次按题型动态组题）；
2. start_category_session —— 针对某个薄弱题型，从题库抽题组一场专项训练。

设计原则：全部只读历史真实数据，不编造；无历史时返回 has_data=False 由前端引导先做一场。
"""
import random
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.question import Question, QuestionSet
from app.models.session import (
    InterviewConfig, InterviewSession, SessionQuestion, SessionScore,
)

# 分档阈值
WEAK_BELOW = 70.0      # 低于此分判定为薄弱
MEDIUM_BELOW = 80.0    # 70~80 为中等，>=80 为优势


def _level(score: float) -> str:
    if score < WEAK_BELOW:
        return "weak"
    if score < MEDIUM_BELOW:
        return "medium"
    return "good"


def get_weak_points(db: Session, user_id: int, top_n: int = 3) -> dict:
    """
    统计用户历史表现，返回薄弱题型与薄弱维度。
    返回结构：
    {
      "has_data": bool,
      "total_answered": int,
      "categories": [{"name","avg_score","count","level","set_id","set_name","available_questions","can_practice"}],
      "dimensions": [{"name","avg_score","count","level"}],
      "focus": [最需要补的 top_n 个题型（含开练入口）],
    }
    """
    # —— 1. 按题型统计（用 session_questions 自带 category，兼容简历动态题） ——
    cat_rows = db.query(
        SessionQuestion.category,
        func.avg(SessionQuestion.total_score),
        func.count(SessionQuestion.id),
    ).join(InterviewSession, SessionQuestion.session_id == InterviewSession.id).filter(
        InterviewSession.user_id == user_id,
        SessionQuestion.status == "done",
        SessionQuestion.total_score.isnot(None),
        SessionQuestion.category.isnot(None),
        SessionQuestion.category != "",
    ).group_by(SessionQuestion.category).all()

    # —— 2. 按考察维度统计（取 session_scores 的真实维度分，比题目维度更准） ——
    dim_rows = db.query(
        SessionScore.dimension,
        func.avg(SessionScore.score),
        func.count(SessionScore.id),
    ).join(SessionQuestion, SessionScore.session_question_id == SessionQuestion.id).join(
        InterviewSession, SessionQuestion.session_id == InterviewSession.id
    ).filter(
        InterviewSession.user_id == user_id,
        SessionQuestion.status == "done",
    ).group_by(SessionScore.dimension).all()

    total_answered = db.query(func.count(SessionQuestion.id)).join(
        InterviewSession, SessionQuestion.session_id == InterviewSession.id
    ).filter(
        InterviewSession.user_id == user_id,
        SessionQuestion.status == "done",
    ).scalar() or 0

    if not cat_rows and not dim_rows:
        return {"has_data": False, "total_answered": 0,
                "categories": [], "dimensions": [], "focus": []}

    # 是否有可用简历：决定「简历深挖」这类动态题型能否开练
    has_resume = _has_active_resume(db, user_id)

    categories = []
    for name, avg, cnt in cat_rows:
        if not name:
            continue
        avg = round(float(avg or 0), 1)
        set_row = _find_set_for_category(db, name)
        available = _count_questions(db, category=name)
        # 开练方式：优先现成套题 → 次之选同题型动态组题 → 最后是简历动态出题
        if set_row:
            mode = "set"
        elif available >= 3:
            mode = "category"
        elif has_resume:
            mode = "resume"
        else:
            mode = ""
        categories.append({
            "name": name,
            "avg_score": avg,
            "count": int(cnt or 0),
            "level": _level(avg),
            "set_id": set_row[0] if set_row else None,
            "set_name": set_row[1] if set_row else None,
            "available_questions": available,
            "practice_mode": mode,
            "can_practice": bool(mode),
        })

    dimensions = []
    for name, avg, cnt in dim_rows:
        if not name:
            continue
        avg = round(float(avg or 0), 1)
        dimensions.append({
            "name": name, "avg_score": avg,
            "count": int(cnt or 0), "level": _level(avg),
        })

    categories.sort(key=lambda x: x["avg_score"])
    dimensions.sort(key=lambda x: x["avg_score"])

    # focus：优先取薄弱且能开练的题型
    focus = [c for c in categories if c["level"] == "weak" and c["can_practice"]][:top_n]
    if not focus:
        focus = [c for c in categories if c["level"] == "medium" and c["can_practice"]][:top_n]
    if not focus:
        focus = [c for c in categories if c["can_practice"]][:top_n]

    return {
        "has_data": True,
        "total_answered": int(total_answered),
        "categories": categories,
        "dimensions": dimensions,
        "focus": focus,
    }


def _has_active_resume(db: Session, user_id: int) -> bool:
    """用户是否已上传并解析过简历（决定简历深挖类题型能否动态出题）"""
    try:
        from app.models.position import Resume
        r = db.query(Resume.id).filter(
            Resume.user_id == user_id, Resume.is_active == 1
        ).first()
        return r is not None
    except Exception:
        return False


def _find_set_for_category(db: Session, category: str):
    """为题型找一套现成的专项套题：先按名称/position_type 匹配，再退回专项练习库"""
    row = db.query(QuestionSet.id, QuestionSet.name).filter(
        QuestionSet.is_published == 1,
        (QuestionSet.name.like(f"%{category}%")) | (QuestionSet.position_type == category),
    ).order_by(QuestionSet.question_count.desc()).first()
    if row:
        return (row[0], row[1])
    return None


def _count_questions(db: Session, category: str = "", dimension: str = "") -> int:
    q = db.query(func.count(Question.id))
    if category:
        q = q.filter(Question.category == category)
    if dimension:
        q = q.filter(Question.dimension == dimension)
    return int(q.scalar() or 0)


def start_category_session(
    db: Session, user_id: int,
    category: str = "", dimension: str = "",
    count: int = 5, form_type: str = "structured",
    use_resume: bool = False,
) -> InterviewSession | None:
    """
    针对薄弱题型/维度组一场专项训练。
    抽题策略：优先抽该题型下「最近没练过」的题，数量不足时用同维度题补齐；
    用户有简历且开启 use_resume 时，再混入 1-2 道简历深挖题（保持针对性但不喧宾夺主）。
    """
    count = max(1, min(int(count or 5), 10))

    # 已练过的题目 id（避免连续重复）
    practiced_ids = {
        r[0] for r in db.query(SessionQuestion.question_id).join(
            InterviewSession, SessionQuestion.session_id == InterviewSession.id
        ).filter(
            InterviewSession.user_id == user_id,
            SessionQuestion.question_id.isnot(None),
        ).all()
    }

    def _pick(filters, limit):
        q = db.query(Question)
        for f in filters:
            q = q.filter(f)
        rows = q.all()
        if not rows:
            return []
        fresh = [r for r in rows if r.id not in practiced_ids] or rows
        random.shuffle(fresh)
        return fresh[:limit]

    picked: list[Question] = []
    if category:
        picked += _pick([Question.category == category], count)
    if dimension and len(picked) < count:
        got = {p.id for p in picked}
        picked += [p for p in _pick([Question.dimension == dimension], count)
                   if p.id not in got][:count - len(picked)]
    if len(picked) < count:
        got = {p.id for p in picked}
        picked += [p for p in _pick([], count) if p.id not in got][:count - len(picked)]

    if not picked:
        return None

    cfg = InterviewConfig(
        user_id=user_id, form_type=form_type, voice_mode="voice",
        difficulty="medium", enable_followup=1, peer_count=0,
        extra_json={"practice_category": category, "practice_dimension": dimension},
    )
    db.add(cfg)
    db.flush()

    sess = InterviewSession(
        user_id=user_id, config_id=cfg.id, set_id=None,
        form_type=form_type, status="running", started_at=datetime.now(),
    )
    db.add(sess)
    db.flush()

    items = [{"source": "bank", "question": q} for q in picked]
    if use_resume:
        from app.crud.session import _build_resume_questions, MIN_RESUME_Q
        rq = _build_resume_questions(db, user_id, count=2)
        if rq:
            from app.crud.session import _mix_questions
            items = _mix_questions(picked, rq, MIN_RESUME_Q)

    for i, item in enumerate(items, 1):
        if item["source"] == "resume":
            db.add(SessionQuestion(
                session_id=sess.id, question_id=None, source="resume",
                content=item["content"],
                category=item.get("category", "简历深挖"),
                dimension=item.get("dimension", "专业深度"),
                time_limit_s=item.get("time_limit_s", 180),
                ref_answer=item.get("ref_answer") or None,
                seq=i, phase="answer", status="pending",
            ))
        else:
            q = item["question"]
            db.add(SessionQuestion(
                session_id=sess.id, question_id=q.id, source="bank",
                content=q.content, category=q.category, dimension=q.dimension,
                time_limit_s=q.time_limit_s or 120,
                ref_answer=q.ref_answer or None,
                seq=i, phase="answer", status="pending",
            ))
    db.flush()
    return sess


def get_last_session_weak_questions(db: Session, user_id: int, session_id: int,
                                    threshold: float = 70.0) -> list[dict]:
    """取某场次中得分低于阈值的题目，用于报告页「针对答得不好的题再来一轮」"""
    rows = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == session_id,
        SessionQuestion.status == "done",
        SessionQuestion.total_score.isnot(None),
        SessionQuestion.total_score < threshold,
    ).order_by(SessionQuestion.total_score).all()
    # 校验归属
    sess = db.get(InterviewSession, session_id)
    if not sess or sess.user_id != user_id:
        return []
    return [{
        "id": r.id,
        "seq": r.seq,
        "content": r.content or "",
        "category": r.category or "",
        "dimension": r.dimension or "",
        "total_score": round(float(r.total_score or 0), 1),
    } for r in rows]

"""报告 CRUD"""
from sqlalchemy.orm import Session
from app.models.report import Report, ReportHighlight, ReportRecommendation
from app.models.session import InterviewSession, SessionQuestion
from app.models.question import Question


def get_report_by_session(db: Session, session_id: int) -> Report | None:
    return db.query(Report).filter(Report.session_id == session_id).first()


def get_report_detail(db: Session, report_id: int):
    rep = db.get(Report, report_id)
    if not rep:
        return None
    highlights = db.query(ReportHighlight).filter(
        ReportHighlight.report_id == report_id
    ).order_by(ReportHighlight.ts_ms).all()
    recs = db.query(ReportRecommendation).filter(
        ReportRecommendation.report_id == report_id
    ).order_by(ReportRecommendation.sort_index).all()
    # 逐题回顾
    sqs = db.query(SessionQuestion).filter(
        SessionQuestion.session_id == rep.session_id
    ).order_by(SessionQuestion.seq).all()
    questions = []
    for sq in sqs:
        q = db.get(Question, sq.question_id) if sq.question_id else None
        sq_highlights = sq.highlights or []
        # 未作答的题也给出欠缺提示，保证每题都有分析
        unanswered = (sq.status != "done") and not sq.transcript
        # 追问次数：优先统计 followup 标记，其次从半结构化转写【追问 N】真实解析
        followup_count = sum(1 for h in sq_highlights if h.category == "followup")
        if followup_count == 0 and sq.transcript:
            followup_count = sq.transcript.count("【追问")
        scores_list = sq.scores or []
        sq_metrics = sq.metrics
        # 转写摘要（前 50 字）
        trans_excerpt = ""
        if sq.transcript:
            trans_excerpt = sq.transcript[:80] + ("…" if len(sq.transcript) > 80 else "")
        questions.append({
            "session_question_id": sq.id,
            "seq": sq.seq,
            "category": sq.category or (q.category if q else ""),
            "dimension": sq.dimension or (q.dimension if q else ""),
            "content": sq.content or (q.content if q else ""),
            "total_score": float(sq.total_score) if sq.total_score is not None else None,
            "duration_ms": sq.duration_ms or 0,
            "followup_count": followup_count,
            # 每题参考标准答案（动态简历题在出题时生成；题库题用题库自带）
            "ref_answer": sq.ref_answer or (q.ref_answer if q else "") or "",
            # 逐题分析：答得好的地方（高光原句）与欠缺的地方（改进建议）
            "good_points": [] if unanswered else [
                h.snippet for h in sq_highlights if h.category == "highlight"
            ][:3],
            "weak_points": (
                ["本题未作答，会直接失分。建议按下方参考答案要点准备，用 STAR 结构补案例与数据。"]
                if unanswered else [
                    r.content for r in (sq.recommendations or []) if r.kind == "improve"
                ][:3]
            ),
            "dimension_scores": [
                {"name": sc.dimension, "score": float(sc.score), "comment": sc.comment}
                for sc in scores_list
            ],
            "transcript_excerpt": trans_excerpt,
            "metrics": {
                "wpm": sq_metrics.wpm if sq_metrics else 0,
                "filler_count": sq_metrics.filler_count if sq_metrics else 0,
                "pause_count": sq_metrics.pause_count if sq_metrics else 0,
            } if sq_metrics else {"wpm": 0, "filler_count": 0, "pause_count": 0},
            "highlight_count": len(sq_highlights or []),
        })
    return rep, highlights, recs, questions


def get_session_question_detail(db: Session, sq_id: int):
    """逐题详情回放"""
    sq = db.get(SessionQuestion, sq_id)
    if not sq:
        return None
    q = db.get(Question, sq.question_id) if sq.question_id else None
    return {
        "sq": sq,
        "question": q,
        # 动态题（简历出题）内容兜底
        "content": sq.content or (q.content if q else ""),
        "category": sq.category or (q.category if q else ""),
        "dimension": sq.dimension or (q.dimension if q else ""),
        "scores": [
            {"dimension": s.dimension, "score": float(s.score), "comment": s.comment}
            for s in (sq.scores or [])
        ],
        "metrics": sq.metrics,
        "highlights": [
            {"ts_ms": h.ts_ms, "category": h.category, "snippet": h.snippet}
            for h in (sq.highlights or [])
        ],
        "recommendations": [
            {"kind": r.kind, "content": r.content, "sort_index": r.sort_index}
            for r in (sq.recommendations or [])
        ],
    }


def list_user_reports(db: Session, user_id: int, limit: int = 20):
    return db.query(Report).filter(
        Report.user_id == user_id,
    ).order_by(Report.created_at.desc()).limit(limit).all()

"""仪表盘 / 工作台取数"""
from datetime import datetime, timedelta
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.models.user import User, UserQuota, UserStreak, PracticeHistory
from app.models.question import QuestionSet
from app.models.session import InterviewSession
from app.models.report import Report


def get_dashboard(db: Session, user: User):
    month_key = datetime.now().strftime("%Y-%m")
    quota = db.query(UserQuota).filter_by(user_id=user.id, month_key=month_key).first()
    streak = db.query(UserStreak).filter_by(user_id=user.id).first()
    # 30 天平均分
    since = datetime.now() - timedelta(days=30)
    avg_row = db.query(func.avg(PracticeHistory.total_score)).filter(
        PracticeHistory.user_id == user.id,
        PracticeHistory.practiced_at >= since,
    ).scalar()
    best_row = db.query(func.max(PracticeHistory.total_score)).filter(
        PracticeHistory.user_id == user.id,
    ).scalar()
    total_sessions = db.query(func.count(PracticeHistory.id)).filter(
        PracticeHistory.user_id == user.id,
    ).scalar() or 0
    # 最近两场比较
    last_two = db.query(PracticeHistory).filter(
        PracticeHistory.user_id == user.id,
    ).order_by(PracticeHistory.practiced_at.desc()).limit(2).all()
    last_delta = 0.0
    if len(last_two) == 2:
        last_delta = float(last_two[0].total_score or 0) - float(last_two[1].total_score or 0)
    # 本周练习次数
    week_start = datetime.now() - timedelta(days=datetime.now().weekday())
    week_count = db.query(func.count(PracticeHistory.id)).filter(
        PracticeHistory.user_id == user.id,
        PracticeHistory.practiced_at >= week_start,
    ).scalar() or 0
    # 同岗位百分位：基于全站练习历史真实排名（击败了百分之多少练习者）
    all_scores = [float(r[0] or 0) for r in db.query(PracticeHistory.total_score).all()]
    my_best = float(best_row or 0)
    if all_scores:
        below = sum(1 for x in all_scores if x < my_best)
        percentile = max(0, min(99, int(round(below / len(all_scores) * 100))))
    else:
        percentile = 0

    return {
        "user_id": user.id,
        "nickname": user.nickname,
        "target_position": user.target_position or "AI 方案架构师",
        "simulated_left": quota.simulated_left if quota else 0,
        "simulated_total": quota.simulated_total if quota else 0,
        "streak_days": streak.current_days if streak else 0,
        "avg_score_30d": float(avg_row or 0),
        "best_score": float(best_row or 0),
        "total_sessions": int(total_sessions),
        "last_delta": float(last_delta),
        "week_count": int(week_count),
        "percentile": percentile,
    }


def get_trend(db: Session, user: User, limit: int = 5):
    rows = db.query(PracticeHistory).filter(
        PracticeHistory.user_id == user.id,
    ).order_by(PracticeHistory.practiced_at.desc()).limit(limit).all()
    # 翻转为时间正序，便于绘图
    rows = list(reversed(rows))
    return [
        {
            "session_id": r.session_id,
            "score": float(r.total_score or 0),
            "set_name": r.set_name,
            "practiced_at": r.practiced_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in rows
    ]


def get_recommend(db: Session, user: User, limit: int = 3):
    """学情推荐：优先根据最近一场报告的最弱维度推荐对应专项练习，其余用高匹配套题补齐"""
    # 1. 找最近一场报告的最弱维度
    weakest_dim = None
    latest_rep = (
        db.query(Report)
        .filter(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .first()
    )
    if latest_rep and latest_rep.dimensions:
        try:
            dims = [d for d in latest_rep.dimensions if d.get("score") is not None]
            if dims:
                weakest_dim = min(dims, key=lambda d: float(d.get("score") or 0)).get("name")
        except Exception:
            weakest_dim = None

    out = []
    picked_ids = set()

    # 2. 最弱维度 → 对应专项套题
    if weakest_dim:
        special = (
            db.query(QuestionSet)
            .filter(
                QuestionSet.is_published == 1,
                QuestionSet.industry == "专项练习",
                QuestionSet.name.like(f"%{weakest_dim}%"),
            )
            .first()
        )
        if special:
            out.append({
                "set_id": special.id,
                "name": f"🎯 {special.name}（针对你的薄弱项「{weakest_dim}」）",
                "match_score": 99.0,
                "position_type": special.position_type,
                "difficulty": special.difficulty,
                "est_minutes": special.est_minutes,
            })
            picked_ids.add(special.id)

    # 3. 其余名额用高匹配正式套题补齐
    rows = (
        db.query(QuestionSet)
        .filter(QuestionSet.is_published == 1, QuestionSet.industry != "专项练习")
        .order_by(QuestionSet.match_score.desc())
        .limit(limit + 2)
        .all()
    )
    for r in rows:
        if len(out) >= limit:
            break
        if r.id in picked_ids:
            continue
        out.append({
            "set_id": r.id,
            "name": r.name,
            "match_score": float(r.match_score or 0),
            "position_type": r.position_type,
            "difficulty": r.difficulty,
            "est_minutes": r.est_minutes,
        })

    # 4. 无历史/无专项时的兜底
    if not out:
        rows = (
            db.query(QuestionSet)
            .filter(QuestionSet.is_published == 1)
            .order_by(QuestionSet.match_score.desc())
            .limit(limit)
            .all()
        )
        out = [
            {
                "set_id": r.id,
                "name": r.name,
                "match_score": float(r.match_score or 0),
                "position_type": r.position_type,
                "difficulty": r.difficulty,
                "est_minutes": r.est_minutes,
            }
            for r in rows
        ]
    return out


def get_history(db: Session, user: User, limit: int = 5):
    rows = db.query(PracticeHistory).filter(
        PracticeHistory.user_id == user.id,
    ).order_by(PracticeHistory.practiced_at.desc()).limit(limit).all()
    return [
        {
            "session_id": r.session_id,
            "set_name": r.set_name,
            "total_score": float(r.total_score or 0),
            "practiced_at": r.practiced_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in rows
    ]


def get_form_stats(db: Session, user: User):
    """选形式页：每个形式的已练次数"""
    out = []
    titles = {
        "structured": ("结构化面试", "1 对 1 与 AI 面试官对话，单题思考 60s + 作答 180s，自动进入下一题。", "5-10", "20-30 min"),
        "group": ("无领导小组讨论", "6 人同场 18 分钟，分为「个人陈述 → 自由讨论 → 总结陈词」三阶段，需举手抢发言权。", "6", "18-22 min"),
        "semi": ("半结构化面试", "在结构化基础上加 1-2 道追问，AI 根据你的回答灵活调整方向，更接近真实面试。", "4-7", "22-28 min"),
    }
    for form_type in ("structured", "group", "semi"):
        cnt = db.query(func.count(InterviewSession.id)).filter(
            InterviewSession.user_id == user.id,
            InterviewSession.form_type == form_type,
        ).scalar() or 0
        t, d, qn, em = titles[form_type]
        out.append({
            "form_type": form_type,
            "title": t,
            "desc": d,
            "question_count_range": qn,
            "est_minutes_range": em,
            "practiced_count": int(cnt),
        })
    return out

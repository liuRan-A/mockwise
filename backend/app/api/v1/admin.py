# -*- coding: utf-8 -*-
"""管理员后台路由：平台统计 / 用户管理 / 全部场次 / 简历浏览 / 面试回放"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import func, or_
import csv
import io
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_admin_user
from app.core.rbac import record_audit
from app.models.user import User, PracticeHistory
from app.models.position import Resume
from app.models.session import InterviewSession, SessionQuestion, SessionScore
from app.models.question import QuestionSet, Question
from app.schemas.common import R

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=R, summary="平台总览统计")
def stats(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    new_users_today = db.query(func.count(User.id)).filter(
        func.date(User.created_at) == today
    ).scalar() or 0
    total_sessions = db.query(func.count(InterviewSession.id)).scalar() or 0
    done_sessions = db.query(func.count(InterviewSession.id)).filter(
        InterviewSession.status == "done"
    ).scalar() or 0
    total_resumes = db.query(func.count(Resume.id)).scalar() or 0
    avg_score = db.query(func.avg(PracticeHistory.total_score)).scalar()
    week_practices = db.query(func.count(PracticeHistory.id)).filter(
        PracticeHistory.practiced_at >= week_ago
    ).scalar() or 0

    # 近 7 天练习趋势
    trend = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        cnt = db.query(func.count(PracticeHistory.id)).filter(
            func.date(PracticeHistory.practiced_at) == day
        ).scalar() or 0
        trend.append({"date": day.strftime("%m-%d"), "count": int(cnt)})

    # 面试形式分布
    form_dist = []
    rows = db.query(InterviewSession.form_type, func.count(InterviewSession.id)).group_by(
        InterviewSession.form_type
    ).all()
    labels = {"structured": "结构化", "group": "群面", "semi": "半结构化"}
    for ft, cnt in rows:
        form_dist.append({"name": labels.get(ft, ft), "value": int(cnt)})

    return R.ok({
        "total_users": int(total_users),
        "new_users_today": int(new_users_today),
        "total_sessions": int(total_sessions),
        "done_sessions": int(done_sessions),
        "total_resumes": int(total_resumes),
        "week_practices": int(week_practices),
        "avg_score": round(float(avg_score), 1) if avg_score else 0,
        "trend": trend,
        "form_distribution": form_dist,
    })


@router.get("/users", response_model=R, summary="用户列表（分页/搜索）")
def list_users(
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((User.nickname.like(like)) | (User.phone.like(like)))
    total = q.count()
    rows = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 聚合每个用户练习次数/平均分
    out = []
    for u in rows:
        agg = db.query(
            func.count(PracticeHistory.id), func.avg(PracticeHistory.total_score)
        ).filter(PracticeHistory.user_id == u.id).one()
        resume_cnt = db.query(func.count(Resume.id)).filter(Resume.user_id == u.id).scalar() or 0
        out.append({
            "id": u.id,
            "phone": u.phone,
            "nickname": u.nickname,
            "target_position": u.target_position,
            "role": u.role,
            "status": u.status,
            "practice_count": int(agg[0] or 0),
            "avg_score": round(float(agg[1]), 1) if agg[1] else 0,
            "resume_count": int(resume_cnt),
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "",
        })
    return R.ok({"list": out, "total": int(total), "page": page, "page_size": page_size})


@router.patch("/users/{user_id}/status", response_model=R, summary="启用/禁用用户")
def set_user_status(user_id: int, status: str, admin: User = Depends(get_admin_user),
                    db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        from fastapi import HTTPException, status as st
        raise HTTPException(st.HTTP_404_NOT_FOUND, "用户不存在")
    if status not in ("active", "paused"):
        from fastapi import HTTPException, status as st
        raise HTTPException(st.HTTP_400_BAD_REQUEST, "状态非法")
    u.status = status
    db.commit()
    record_audit(db, admin.id, "update_status", "user", user_id, f"status={status}")
    return R.ok({"id": u.id, "status": u.status})


@router.get("/sessions", response_model=R, summary="全部面试场次（支持关键词/时间筛选）")
def list_sessions(
    keyword: str = "",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(InterviewSession)
    if keyword:
        kw = f"%{keyword}%"
        uids = [r[0] for r in db.query(User.id).filter(
            (User.nickname.like(kw)) | (User.phone.like(kw)))]
        sids = [r[0] for r in db.query(QuestionSet.id).filter(QuestionSet.name.like(kw))]
        q = q.filter(or_(InterviewSession.user_id.in_(uids or [-1]),
                        InterviewSession.set_id.in_(sids or [-1])))
    if start:
        q = q.filter(InterviewSession.started_at >= start)
    if end:
        q = q.filter(InterviewSession.started_at < end + timedelta(days=1))
    total = q.count()
    rows = q.order_by(InterviewSession.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    user_map = {u.id: u for u in db.query(User).all()}
    set_map = {s.id: s for s in db.query(QuestionSet).all()}
    labels = {"structured": "结构化", "group": "群面", "semi": "半结构化"}
    out = []
    for s in rows:
        u = user_map.get(s.user_id)
        qs = set_map.get(s.set_id)
        out.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_name": u.nickname if u else f"用户{s.user_id}",
            "form_type": s.form_type,
            "form_label": labels.get(s.form_type, s.form_type),
            "set_name": qs.name if qs else "简历专场" if s.set_id is None else "—",
            "status": s.status,
            "total_score": float(s.total_score) if s.total_score else 0,
            "started_at": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
        })
    return R.ok({"list": out, "total": int(total), "page": page, "page_size": page_size})


@router.get("/resumes", response_model=R, summary="全部简历（支持关键词/时间筛选）")
def list_resumes(
    keyword: str = "",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(Resume)
    if keyword:
        kw = f"%{keyword}%"
        uids = [r[0] for r in db.query(User.id).filter(
            (User.nickname.like(kw)) | (User.phone.like(kw)))]
        q = q.filter(or_(Resume.user_id.in_(uids or [-1]), Resume.filename.like(kw)))
    if start:
        q = q.filter(Resume.created_at >= start)
    if end:
        q = q.filter(Resume.created_at < end + timedelta(days=1))
    total = q.count()
    rows = q.order_by(Resume.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    user_map = {u.id: u for u in db.query(User).all()}
    out = []
    for r in rows:
        u = user_map.get(r.user_id)
        p = r.parsed_json or {}
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_name": u.nickname if u else f"用户{r.user_id}",
            "filename": r.filename,
            "file_type": r.file_type,
            "status": r.status,
            "engine": p.get("engine", "rule"),
            "candidate_name": p.get("candidate_name", ""),
            "target_position": p.get("target_position", ""),
            "skills": p.get("skills", [])[:6],
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        })
    return R.ok({"list": out, "total": int(total), "page": page, "page_size": page_size})


# —— 面试回放（管理员视角） ——
@router.get("/sessions/{session_id}/detail", response_model=R, summary="管理员查看单场完整回放（含逐题转写/音频/录像占位）")
def admin_session_detail(
    session_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    sess = db.get(InterviewSession, session_id)
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "场次不存在")
    user = db.get(User, sess.user_id)
    qs = db.get(QuestionSet, sess.set_id) if sess.set_id else None

    # 逐题详情（含转写、音频/视频 url、分维度评分）
    sqs = (
        db.query(SessionQuestion)
        .filter(SessionQuestion.session_id == session_id)
        .order_by(SessionQuestion.seq)
        .all()
    )
    questions_out = []
    for sq in sqs:
        # 题目正文（动态简历题直接取 sq.content）
        q = db.get(Question, sq.question_id) if sq.question_id else None
        content = sq.content or (q.content if q else "") or ""
        scores = [
            {"dimension": s.dimension, "score": float(s.score), "comment": s.comment}
            for s in sq.scores
        ]
        questions_out.append({
            "id": sq.id,
            "seq": sq.seq,
            "phase": sq.phase,
            "status": sq.status,
            "question_content": content,
            "question_category": sq.category or (q.category if q else ""),
            "question_dimension": sq.dimension or (q.dimension if q else ""),
            "transcript": sq.transcript or "",
            "audio_url": sq.audio_url or "",     # 录音
            "video_url": "",                     # 录像占位：当前项目不录制视频，UI 上做"已保存"标识
            "duration_ms": sq.duration_ms or 0,
            "total_score": float(sq.total_score) if sq.total_score is not None else None,
            "scores": scores,
            "answered_at": sq.answered_at.strftime("%Y-%m-%d %H:%M:%S") if sq.answered_at else "",
        })

    labels = {"structured": "结构化", "group": "群面", "semi": "半结构化"}
    return R.ok({
        "session": {
            "id": sess.id,
            "user_id": sess.user_id,
            "user_name": user.nickname if user else f"用户{sess.user_id}",
            "user_phone": user.phone if user else "",
            "form_type": sess.form_type,
            "form_label": labels.get(sess.form_type, sess.form_type),
            "set_name": qs.name if qs else ("简历专场" if sess.set_id is None else "—"),
            "status": sess.status,
            "total_score": float(sess.total_score or 0),
            "avg_score": float(sess.avg_score or 0),
            "started_at": sess.started_at.strftime("%Y-%m-%d %H:%M:%S") if sess.started_at else "",
            "ended_at": sess.ended_at.strftime("%Y-%m-%d %H:%M:%S") if sess.ended_at else "",
        },
        "questions": questions_out,
    })


@router.get("/records", response_model=R, summary="面试回放列表（所有已完成场次的简要索引）")
def admin_records(
    form_type: str = "",
    keyword: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """面向"管理 → 面试回放"模块的列表：每行带「视频/转写是否保存」标识，
    点击可直接打开回放弹窗（走 /admin/sessions/{id}/detail）。"""
    q = db.query(InterviewSession)
    if form_type:
        q = q.filter(InterviewSession.form_type == form_type)
    total = q.count()
    rows = q.order_by(InterviewSession.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    user_map = {u.id: u for u in db.query(User).all()}
    set_map = {s.id: s for s in db.query(QuestionSet).all()}
    labels = {"structured": "结构化", "group": "群面", "semi": "半结构化"}
    out = []
    for s in rows:
        u = user_map.get(s.user_id)
        qs = set_map.get(s.set_id) if s.set_id else None
        sqs = db.query(SessionQuestion).filter(SessionQuestion.session_id == s.id).all()
        answered = [sq for sq in sqs if sq.status == "done" and sq.transcript]
        # 是否有任意音频或录像保存
        has_audio = any((sq.audio_url or "") for sq in answered)
        has_video = any(getattr(sq, "video_url", "") for sq in answered)  # 当前未录制视频
        duration_ms = sum((sq.duration_ms or 0) for sq in answered)
        text_chars = sum(len(sq.transcript or "") for sq in answered)
        rec = {
            "id": s.id,
            "user_id": s.user_id,
            "user_name": u.nickname if u else f"用户{s.user_id}",
            "user_phone": u.phone if u else "",
            "form_type": s.form_type,
            "form_label": labels.get(s.form_type, s.form_type),
            "set_name": qs.name if qs else ("简历专场" if s.set_id is None else "—"),
            "status": s.status,
            "total_score": float(s.total_score or 0),
            "started_at": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
            "ended_at": s.ended_at.strftime("%Y-%m-%d %H:%M") if s.ended_at else "",
            "question_count": len(sqs),
            "answered_count": len(answered),
            "duration_ms": int(duration_ms),
            "text_chars": int(text_chars),
            "has_audio": has_audio,
            "has_video": has_video,
        }
        # 关键词过滤：用户昵称 / 手机号 / 套题名
        if keyword:
            kw = keyword.lower()
            if (rec["user_name"].lower().find(kw) < 0
                and rec["user_phone"].lower().find(kw) < 0
                and rec["set_name"].lower().find(kw) < 0):
                continue
        out.append(rec)
    return R.ok({"list": out, "total": int(total), "page": page, "page_size": page_size})


# —— 通用：构造单条回放记录行 ——
def _record_row(s, db):
    u = db.get(User, s.user_id)
    qs = db.get(QuestionSet, s.set_id) if s.set_id else None
    sqs = db.query(SessionQuestion).filter(SessionQuestion.session_id == s.id).all()
    answered = [sq for sq in sqs if sq.status == "done" and sq.transcript]
    has_audio = any((sq.audio_url or "") for sq in answered)
    duration_ms = sum((sq.duration_ms or 0) for sq in answered)
    text_chars = sum(len(sq.transcript or "") for sq in answered)
    return {
        "id": s.id,
        "user_name": u.nickname if u else f"用户{s.user_id}",
        "user_phone": u.phone if u else "",
        "form_label": {"structured": "结构化", "group": "群面", "semi": "半结构化"}.get(s.form_type, s.form_type),
        "set_name": qs.name if qs else ("简历专场" if s.set_id is None else "—"),
        "status": s.status,
        "total_score": float(s.total_score or 0),
        "question_count": len(sqs),
        "answered_count": len(answered),
        "duration": f"{int(duration_ms // 60000)}:{int((duration_ms % 60000) // 1000):02d}",
        "text_chars": text_chars,
        "has_audio": has_audio,
        "started_at": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
        "ended_at": s.ended_at.strftime("%Y-%m-%d %H:%M") if s.ended_at else "",
    }


def _to_csv(rows, headers, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for _, h in headers])
    for row in rows:
        w.writerow([row.get(k, "") for k, _ in headers])
    data = buf.getvalue().encode("utf-8-sig")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# —— 用户详情（管理员视角） ——
@router.get("/users/{user_id}", response_model=R, summary="用户详情（含练习/简历/场次）")
def user_detail(user_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    practices = [
        {"set_name": p.set_name, "total_score": float(p.total_score),
         "practiced_at": p.practiced_at.strftime("%Y-%m-%d %H:%M")}
        for p in db.query(PracticeHistory).filter(PracticeHistory.user_id == user_id)
        .order_by(PracticeHistory.practiced_at.desc()).limit(50)
    ]
    resumes = [
        {"id": r.id, "filename": r.filename,
         "engine": (r.parsed_json or {}).get("engine", "rule"),
         "candidate_name": (r.parsed_json or {}).get("candidate_name", ""),
         "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""}
        for r in db.query(Resume).filter(Resume.user_id == user_id).order_by(Resume.created_at.desc())
    ]
    sessions = [
        {"id": s.id,
         "form_label": {"structured": "结构化", "group": "群面", "semi": "半结构化"}.get(s.form_type, s.form_type),
         "set_name": (db.get(QuestionSet, s.set_id).name if s.set_id and db.get(QuestionSet, s.set_id) else ("简历专场" if s.set_id is None else "—")),
         "status": s.status, "total_score": float(s.total_score or 0),
         "started_at": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else ""}
        for s in db.query(InterviewSession).filter(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.started_at.desc()).limit(50)
    ]
    agg = db.query(func.count(PracticeHistory.id), func.avg(PracticeHistory.total_score)).filter(
        PracticeHistory.user_id == user_id).one()
    return R.ok({
        "user": {
            "id": u.id, "phone": u.phone, "nickname": u.nickname,
            "target_position": u.target_position, "role": u.role, "status": u.status,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "",
            "practice_count": int(agg[0] or 0),
            "avg_score": round(float(agg[1]), 1) if agg[1] else 0,
            "resume_count": db.query(func.count(Resume.id)).filter(Resume.user_id == user_id).scalar() or 0,
        },
        "practices": practices,
        "resumes": resumes,
        "sessions": sessions,
    })


# —— 简历详情（解析全文） ——
@router.get("/resumes/{resume_id}", response_model=R, summary="简历详情（解析全文）")
def resume_detail(resume_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    r = db.get(Resume, resume_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "简历不存在")
    u = db.get(User, r.user_id)
    p = r.parsed_json or {}
    return R.ok({
        "id": r.id, "user_id": r.user_id,
        "user_name": u.nickname if u else f"用户{r.user_id}",
        "filename": r.filename, "file_type": r.file_type, "status": r.status,
        "engine": p.get("engine", "rule"),
        "candidate_name": p.get("candidate_name", ""),
        "target_position": p.get("target_position", ""),
        "skills": p.get("skills", []),
        "parsed": p,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
    })


# —— CSV 导出 ——
@router.get("/users/export", summary="导出用户 CSV（utf-8）")
def export_users(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    rows = []
    for u in db.query(User).order_by(User.created_at.desc()).all():
        agg = db.query(func.count(PracticeHistory.id), func.avg(PracticeHistory.total_score)).filter(
            PracticeHistory.user_id == u.id).one()
        rc = db.query(func.count(Resume.id)).filter(Resume.user_id == u.id).scalar() or 0
        rows.append({
            "id": u.id, "phone": u.phone, "nickname": u.nickname,
            "target_position": u.target_position, "role": u.role, "status": u.status,
            "practice_count": int(agg[0] or 0),
            "avg_score": round(float(agg[1]), 1) if agg[1] else 0,
            "resume_count": int(rc),
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "",
        })
    headers = [("id", "ID"), ("phone", "手机号"), ("nickname", "昵称"), ("target_position", "目标岗位"),
               ("role", "角色"), ("status", "状态"), ("practice_count", "练习次数"),
               ("avg_score", "平均分"), ("resume_count", "简历数"),
               ("created_at", "注册时间"), ("last_login_at", "最近登录")]
    return _to_csv(rows, headers, "mockwise_users.csv")


@router.get("/resumes/export", summary="导出简历 CSV（utf-8）")
def export_resumes(
    keyword: str = "",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(Resume)
    if keyword:
        kw = f"%{keyword}%"
        uids = [r[0] for r in db.query(User.id).filter(
            (User.nickname.like(kw)) | (User.phone.like(kw)))]
        q = q.filter(or_(Resume.user_id.in_(uids or [-1]), Resume.filename.like(kw)))
    if start:
        q = q.filter(Resume.created_at >= start)
    if end:
        q = q.filter(Resume.created_at < end + timedelta(days=1))
    rows = []
    for r in q.order_by(Resume.created_at.desc()).all():
        u = db.get(User, r.user_id)
        p = r.parsed_json or {}
        rows.append({
            "id": r.id,
            "user_name": u.nickname if u else f"用户{r.user_id}",
            "user_phone": u.phone if u else "",
            "filename": r.filename,
            "file_type": r.file_type,
            "engine": p.get("engine", "rule"),
            "candidate_name": p.get("candidate_name", ""),
            "target_position": p.get("target_position", ""),
            "skills": "、".join(p.get("skills", []) or []),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        })
    headers = [("id", "ID"), ("user_name", "用户"), ("user_phone", "手机号"), ("filename", "文件"),
               ("file_type", "类型"), ("engine", "引擎"), ("candidate_name", "候选人"),
               ("target_position", "目标岗位"), ("skills", "技能"), ("created_at", "上传时间")]
    return _to_csv(rows, headers, "mockwise_resumes.csv")


@router.get("/sessions/export", summary="导出面试场次 CSV（utf-8）")
def export_sessions(
    keyword: str = "",
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(InterviewSession)
    if keyword:
        kw = f"%{keyword}%"
        uids = [r[0] for r in db.query(User.id).filter((User.nickname.like(kw)) | (User.phone.like(kw)))]
        sids = [r[0] for r in db.query(QuestionSet.id).filter(QuestionSet.name.like(kw))]
        q = q.filter(or_(InterviewSession.user_id.in_(uids or [-1]), InterviewSession.set_id.in_(sids or [-1])))
    if start:
        q = q.filter(InterviewSession.started_at >= start)
    if end:
        q = q.filter(InterviewSession.started_at < end + timedelta(days=1))
    rows = []
    for s in q.order_by(InterviewSession.started_at.desc()).all():
        u = db.get(User, s.user_id)
        qs = db.get(QuestionSet, s.set_id) if s.set_id else None
        rows.append({
            "id": s.id,
            "user_name": u.nickname if u else f"用户{s.user_id}",
            "form_label": {"structured": "结构化", "group": "群面", "semi": "半结构化"}.get(s.form_type, s.form_type),
            "set_name": qs.name if qs else ("简历专场" if s.set_id is None else "—"),
            "status": s.status,
            "total_score": float(s.total_score or 0),
            "started_at": s.started_at.strftime("%Y-%m-%d %H:%M") if s.started_at else "",
            "ended_at": s.ended_at.strftime("%Y-%m-%d %H:%M") if s.ended_at else "",
        })
    headers = [("id", "场次ID"), ("user_name", "用户"), ("form_label", "形式"), ("set_name", "套题"),
               ("status", "状态"), ("total_score", "总分"), ("started_at", "开始时间"), ("ended_at", "结束时间")]
    return _to_csv(rows, headers, "mockwise_sessions.csv")


@router.get("/records/export", summary="导出面试回放 CSV（utf-8）")
def export_records(
    form_type: str = "",
    keyword: str = "",
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    q = db.query(InterviewSession)
    if form_type:
        q = q.filter(InterviewSession.form_type == form_type)
    rows = [_record_row(s, db) for s in q.order_by(InterviewSession.created_at.desc()).all()]
    if keyword:
        kw = keyword.lower()
        rows = [r for r in rows if kw in r["user_name"].lower() or kw in r["user_phone"].lower()
                or kw in r["set_name"].lower()]
    headers = [("id", "场次ID"), ("user_name", "用户"), ("user_phone", "手机号"), ("form_label", "形式"),
               ("set_name", "套题"), ("status", "状态"), ("total_score", "总分"),
               ("question_count", "题数"), ("answered_count", "已作答"), ("duration", "时长"),
               ("text_chars", "转写字数"), ("started_at", "开始时间"), ("ended_at", "结束时间")]
    return _to_csv(rows, headers, "mockwise_records.csv")

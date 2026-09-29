"""报告路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.crud import report as rc

router = APIRouter(prefix="/reports", tags=["report"])


@router.get("", response_model=R, summary="我的报告列表")
def list_reports(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = rc.list_user_reports(db, user.id, limit)
    return R.ok([
        {
            "id": r.id, "session_id": r.session_id, "form_type": r.form_type,
            "total_score": float(r.total_score or 0), "overview": r.overview or "",
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        }
        for r in rows
    ])


@router.get("/{report_id}", response_model=R, summary="报告详情")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    detail = rc.get_report_detail(db, report_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告不存在")
    rep, highlights, recs, questions = detail
    if rep.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问")
    out = {
        "id": rep.id, "session_id": rep.session_id, "form_type": rep.form_type,
        "total_score": float(rep.total_score or 0),
        "dimensions": rep.dimensions or [],
        "comparison": rep.comparison or {"last_delta": 0, "percentile": 0},
        "overview": rep.overview or "",
        "duration_sec": int(rep.duration_sec or 0),
        "created_at": rep.created_at.strftime("%Y-%m-%d %H:%M") if rep.created_at else "",
        "highlights": [
            {"ts_ms": h.ts_ms, "snippet": h.snippet, "category": h.category}
            for h in highlights
        ],
        "recommendations": [
            {"kind": r.kind, "content": r.content, "sort_index": r.sort_index}
            for r in recs
        ],
        "questions": questions,
    }
    return R.ok(out)


@router.get("/by-session/{session_id}", response_model=R, summary="按场次取报告")
def get_by_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rep = rc.get_report_by_session(db, session_id)
    if not rep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "报告尚未生成")
    return R.ok({"report_id": rep.id})

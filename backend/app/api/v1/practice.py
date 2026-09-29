"""针对性训练路由：薄弱题型分析 + 一键加练"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.crud import practice as pc

router = APIRouter(prefix="/practice", tags=["practice"])


class StartPracticeReq(BaseModel):
    category: str = ""          # 薄弱题型（优先级高于 dimension）
    dimension: str = ""         # 薄弱维度
    count: int = 5              # 题目数量
    form_type: str = "structured"
    use_resume: bool = False    # 是否混入简历深挖题


@router.get("/weak-points", response_model=R, summary="薄弱题型分析")
def weak_points(
    top_n: int = 3,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按题型与维度统计历史表现，返回薄弱项及可开练的专项入口"""
    return R.ok(pc.get_weak_points(db, user.id, top_n=top_n))


@router.post("/start", response_model=R, summary="开始针对性训练")
def start_practice(
    body: StartPracticeReq,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """针对某个薄弱题型/维度组一场专项训练"""
    if not body.category and not body.dimension:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请指定要练习的题型或维度")
    sess = pc.start_category_session(
        db, user.id,
        category=body.category, dimension=body.dimension,
        count=body.count, form_type=body.form_type,
        use_resume=body.use_resume,
    )
    if not sess:
        return R.fail("题库中暂无该类型的题目，换一个题型试试")
    db.commit()
    db.refresh(sess)
    return R.ok({
        "session_id": sess.id,
        "status": sess.status,
        "category": body.category,
        "dimension": body.dimension,
    })


@router.get("/weak-questions/{session_id}", response_model=R, summary="本场答得不好的题")
def weak_questions(
    session_id: int,
    threshold: float = 70.0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出某场次中得分低于阈值的题目，供「针对弱项再来一轮」"""
    rows = pc.get_last_session_weak_questions(db, user.id, session_id, threshold)
    return R.ok({"threshold": threshold, "questions": rows, "count": len(rows)})

"""题库路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.schemas.question import QuestionSetOut, QuestionOut
from app.crud import question as q

router = APIRouter(prefix="/question-sets", tags=["question"])


@router.get("", response_model=R, summary="套题列表")
def list_sets(
    form_type: str | None = None,
    position_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = q.list_sets(db, form_type, position_type)
    return R.ok([QuestionSetOut.from_orm(r).dict() for r in rows])


@router.get("/{set_id}", response_model=R, summary="套题详情（含题目）")
def get_set(set_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    detail = q.get_set_detail(db, set_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "套题不存在")
    s, questions = detail
    return R.ok({
        **QuestionSetOut.from_orm(s).dict(),
        "questions": [QuestionOut.from_orm(qq).dict() for qq in questions],
    })

"""工作台 / 仪表盘路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.crud import dashboard as d

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=R, summary="工作台聚合数据")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(d.get_dashboard(db, user))


@router.get("/trend", response_model=R, summary="得分趋势（最近 N 场）")
def trend(limit: int = 5, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(d.get_trend(db, user, limit))


@router.get("/recommend", response_model=R, summary="今日推荐练习")
def recommend(limit: int = 3, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(d.get_recommend(db, user, limit))


@router.get("/history", response_model=R, summary="练习历史")
def history(limit: int = 5, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(d.get_history(db, user, limit))


@router.get("/form-stats", response_model=R, summary="选形式页统计")
def form_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(d.get_form_stats(db, user))

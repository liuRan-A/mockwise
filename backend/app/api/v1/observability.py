# -*- coding: utf-8 -*-
"""可观测性管理接口（对应标准④）

把「成功率 / 耗时分位 / Token 成本 / 上下文命中 / 评分稳定性」暴露成可读接口，
让工程效果可查、可验证，而不是只存在于日志里。

全部接口需要 `view:stats` 权限（当前仅 admin 具备）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_permission, PERM_VIEW_STATS
from app.models.user import User
from app.schemas.common import R
from app.services import metrics, eval as eval_svc

router = APIRouter(prefix="/admin/observability", tags=["observability"])

_admin = Depends(require_permission(PERM_VIEW_STATS))


@router.get("/metrics/llm", response_model=R, summary="LLM 调用指标总览")
def llm_metrics(
    hours: int = Query(24, ge=1, le=24 * 30, description="统计时间窗（小时）"),
    scene: Optional[str] = Query(None, description="按场景过滤，如 score_answer"),
    admin: User = _admin,
    db: Session = Depends(get_db),
):
    return R.ok({
        "overview": metrics.llm_overview(db, hours=hours, scene=scene),
        "by_scene": metrics.by_scene(db, hours=hours),
    })


@router.get("/metrics/context", response_model=R, summary="上下文工程效果指标")
def context_metrics(
    hours: int = Query(24, ge=1, le=24 * 30),
    admin: User = _admin,
    db: Session = Depends(get_db),
):
    return R.ok(metrics.ctx_stats(db, hours=hours))


@router.get("/calls", response_model=R, summary="最近 LLM 调用明细")
def recent_calls(
    limit: int = Query(50, ge=1, le=500),
    scene: Optional[str] = Query(None),
    admin: User = _admin,
    db: Session = Depends(get_db),
):
    return R.ok(metrics.recent_calls(db, limit=limit, scene=scene))


@router.get("/traces/{trace_id}", response_model=R, summary="按 trace_id 还原调用链")
def trace_detail(trace_id: str, admin: User = _admin, db: Session = Depends(get_db)):
    return R.ok(metrics.trace_detail(db, trace_id))


@router.post("/eval/run", response_model=R, summary="跑一轮量化评测")
def run_eval(
    repeat: int = Query(3, ge=1, le=10, description="每个样本重复次数（用于测稳定性）"),
    offline: bool = Query(True, description="True=离线假 LLM（不烧钱、可复现）；False=真实调用"),
    admin: User = _admin,
    db: Session = Depends(get_db),
):
    report = eval_svc.run_eval(db, repeat=repeat, offline=offline)
    return R.ok(report)


@router.get("/eval/latest", response_model=R, summary="最近一次评测报告")
def eval_latest(admin: User = _admin, db: Session = Depends(get_db)):
    row = eval_svc.latest_run(db)
    return R.ok(row) if row else R.ok(None, msg="暂无评测记录")


@router.get("/eval/runs", response_model=R, summary="历史评测运行列表")
def eval_runs(limit: int = Query(20, ge=1, le=100),
              admin: User = _admin, db: Session = Depends(get_db)):
    return R.ok(eval_svc.list_runs(db, limit=limit))

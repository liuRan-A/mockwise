"""工作台 / 仪表盘 schemas"""
from typing import Optional
from pydantic import BaseModel


class DashboardOut(BaseModel):
    user_id: int
    nickname: str
    target_position: str
    simulated_left: int
    simulated_total: int
    streak_days: int
    avg_score_30d: float
    best_score: float
    total_sessions: int
    # 额外字段：较上场变化、本周练习次数、同岗位百分位
    last_delta: Optional[float] = 0.0
    week_count: int = 0
    percentile: int = 0


class TrendItem(BaseModel):
    session_id: int
    score: float
    set_name: str
    practiced_at: str


class RecommendItem(BaseModel):
    set_id: int
    name: str
    match_score: float
    position_type: str
    difficulty: str
    est_minutes: int


class HistoryItem(BaseModel):
    session_id: int
    set_name: str
    total_score: float
    practiced_at: str

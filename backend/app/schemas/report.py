"""报告 schemas"""
from typing import Optional, Any
from pydantic import BaseModel


class DimensionItem(BaseModel):
    name: str
    score: float
    comment: str = ""


class ComparisonOut(BaseModel):
    last_delta: Optional[float] = 0.0
    percentile: int = 0


class ReportOut(BaseModel):
    id: int
    session_id: int
    form_type: str
    total_score: float
    dimensions: Optional[list[DimensionItem]] = None
    comparison: Optional[ComparisonOut] = None
    overview: str = ""
    duration_sec: int = 0
    created_at: str

    class Config:
        orm_mode = True


class ReportHighlightOut(BaseModel):
    ts_ms: int
    snippet: str
    category: str = "highlight"


class ReportRecommendationOut(BaseModel):
    kind: str
    content: str
    sort_index: int = 0


class QuestionReviewItem(BaseModel):
    """报告里逐题回顾列表项"""
    session_question_id: int
    seq: int
    category: str
    content: str
    total_score: Optional[float]
    duration_ms: int = 0
    followup_count: int = 0


class ReportDetail(ReportOut):
    highlights: list[ReportHighlightOut] = []
    recommendations: list[ReportRecommendationOut] = []
    questions: list[QuestionReviewItem] = []

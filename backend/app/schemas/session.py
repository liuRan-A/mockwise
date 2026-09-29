"""模拟场次 schemas"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class SessionCreate(BaseModel):
    set_id: int
    form_type: str = "structured"
    voice_mode: str = "voice"
    difficulty: str = "medium"
    enable_followup: bool = True
    peer_count: int = 0
    position_id: Optional[int] = None
    use_resume: bool = False
    # 有简历时，一场希望插入几道来自简历的题（至少 2 道）
    resume_count: int = 2


class SessionQuestionOut(BaseModel):
    id: int
    session_id: int
    question_id: Optional[int] = None
    seq: int
    phase: str
    status: str
    source: str = "bank"
    content: Optional[str] = None
    category: Optional[str] = None
    dimension: Optional[str] = None
    time_limit_s: Optional[int] = None
    transcript: Optional[str] = None
    audio_url: Optional[str] = None
    ref_answer: Optional[str] = None
    total_score: Optional[float] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class SessionOut(BaseModel):
    id: int
    user_id: int
    set_id: Optional[int] = None
    form_type: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_score: float
    avg_score: float

    class Config:
        orm_mode = True


class SessionDetail(SessionOut):
    questions: list[SessionQuestionOut] = []


class AnswerSubmit(BaseModel):
    """提交单题作答"""
    transcript: str = ""
    audio_url: str = ""
    duration_ms: int = 0


class MetricOut(BaseModel):
    wpm: int
    pause_count: int
    pause_ms_total: int
    filler_count: int
    interrupt_count: int
    extra_json: Optional[dict] = None


class ScoreOut(BaseModel):
    dimension: str
    score: float
    comment: str = ""


class SessionQuestionDetail(SessionQuestionOut):
    """逐题详情（带评分/指标/高光/建议/优劣分析/参考答案）"""
    scores: list[ScoreOut] = []
    metrics: Optional[MetricOut] = None
    highlights: list[dict] = []
    recommendations: list[dict] = []
    # 关联题干
    question_content: str = ""
    question_category: str = ""
    question_dimension: str = ""
    time_limit_s: int = 120
    # v1.1 逐题深度分析
    strengths: list[dict] = []
    gaps: list[dict] = []
    ref_detail: Optional[dict] = None

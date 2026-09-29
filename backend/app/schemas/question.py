"""题库 schemas"""
from typing import Optional
from pydantic import BaseModel


class QuestionOut(BaseModel):
    id: int
    set_id: int
    seq: int
    form_type: str
    difficulty: str
    category: str
    dimension: str
    content: str
    attachments: Optional[dict] = None
    ref_answer: Optional[str] = None
    time_limit_s: int

    class Config:
        orm_mode = True


class QuestionSetOut(BaseModel):
    id: int
    name: str
    industry: str
    position_type: str
    form_type: str
    difficulty: str
    description: str
    cover_url: str
    question_count: int
    est_minutes: int
    match_score: float
    is_published: int

    class Config:
        orm_mode = True


class QuestionSetDetail(QuestionSetOut):
    questions: list[QuestionOut] = []


class FormOptionOut(BaseModel):
    """选形式页：每个形式的统计"""
    form_type: str
    title: str
    desc: str
    question_count_range: str
    est_minutes_range: str
    practiced_count: int

# -*- coding: utf-8 -*-
"""内容配置后台：套题 / 题目 / 群面虚拟候选人人设 的请求模型"""
from typing import Optional, List
from pydantic import BaseModel


# ——— 套题 ———
class SetCreate(BaseModel):
    name: str
    industry: str = ""
    position_type: str = ""
    form_type: str = "structured"          # structured / group / semi
    difficulty: str = "medium"             # easy / medium / hard
    description: str = ""
    cover_url: str = ""
    est_minutes: int = 0
    match_score: float = 0.0
    is_published: int = 1                  # 0 下架 / 1 上架


class SetUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    position_type: Optional[str] = None
    form_type: Optional[str] = None
    difficulty: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    est_minutes: Optional[int] = None
    match_score: Optional[float] = None
    is_published: Optional[int] = None


# ——— 题目 ———
class QuestionCreate(BaseModel):
    seq: int = 0                            # 0 = 自动追加到末尾
    form_type: str = "structured"
    difficulty: str = "medium"
    category: str = ""
    dimension: str = ""
    content: str
    ref_answer: Optional[str] = None
    time_limit_s: int = 120


class QuestionUpdate(BaseModel):
    seq: Optional[int] = None
    form_type: Optional[str] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    dimension: Optional[str] = None
    content: Optional[str] = None
    ref_answer: Optional[str] = None
    time_limit_s: Optional[int] = None


# ——— 群面虚拟候选人人设 ———
class PersonaCreate(BaseModel):
    name: str
    style: str = ""
    color: str = "#3E63DD"
    bio: str = ""
    aggressiveness: int = 3                # 1-5 抢话倾向
    openings: List[str] = []               # 个人陈述模板（换行拆分）
    rebuttals: List[str] = []              # 自由讨论反驳模板
    summaries: List[str] = []             # 总结陈词模板
    set_id: Optional[int] = None          # 空=通用


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    style: Optional[str] = None
    color: Optional[str] = None
    bio: Optional[str] = None
    aggressiveness: Optional[int] = None
    openings: Optional[List[str]] = None
    rebuttals: Optional[List[str]] = None
    summaries: Optional[List[str]] = None
    set_id: Optional[int] = None

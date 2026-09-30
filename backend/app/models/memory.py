# -*- coding: utf-8 -*-
"""
候选人长期记忆（用户记忆层）—— 上下文工程的核心数据源。

与「每场临时查简历」不同，这里跨场次累积候选人的：
- 薄弱维度 weak_dims：多次得分偏低的维度（含计数与滚动均值）
- 优势维度 strong_dims：多次得分偏高的维度
- 薄弱题目类别 weak_cats
- 偏好 prefs（岗位/形式）

评分/群面时由 crud.memory.retrieve_relevant 按需召回「与当前题目相关」的片段，
让模型只读取需要的信息，而不是每次把整份简历塞进 prompt。
"""
from app.core.database import Base
from sqlalchemy import Column, Integer, JSON, DateTime, func


class CandidateMemory(Base):
    __tablename__ = "candidate_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False, comment="用户ID")
    weak_dims = Column(JSON, default=lambda: [], comment="[{name,count,avg}] 多次得分偏低的维度")
    strong_dims = Column(JSON, default=lambda: [], comment="[{name,count,avg}] 多次得分偏高的维度")
    weak_cats = Column(JSON, default=lambda: [], comment="[{name,count}] 薄弱题目类别")
    prefs = Column(JSON, default=lambda: {}, comment="{position_types:[], form_types:[]} 岗位/形式偏好")
    session_count = Column(Integer, default=0, comment="已纳入统计的练习场次次数")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

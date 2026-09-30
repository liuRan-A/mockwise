# -*- coding: utf-8 -*-
"""
候选人记忆读写（上下文工程核心数据源）。

设计原则：
- 累积：每场结束把维度得分推进 CandidateMemory（计数 + 滚动均值），形成长期用户记忆；
- 召回：评分/群面时只取「与当前题目维度/类别」相关的片段，无记忆返回 None（不污染上下文）；
- 保守：单场样本数 < 2 时不给「总体概览」，避免以偏概全误导模型。
"""
from sqlalchemy.orm import Session
from app.models.memory import CandidateMemory
from app.core.logging_config import get_logger

log = get_logger("memory")

WEAK_THRESHOLD = 66.0     # 维度均分低于此值记为偏弱
STRONG_THRESHOLD = 80.0   # 维度均分高于此值记为优势


def get_or_create(db: Session, user_id: int) -> CandidateMemory:
    m = db.query(CandidateMemory).filter_by(user_id=user_id).first()
    if not m:
        m = CandidateMemory(
            user_id=user_id,
            weak_dims=[], strong_dims=[], weak_cats=[], prefs={}, session_count=0,
        )
        db.add(m)
        db.flush()
    return m


def _bump(dim_list, name, score):
    """在 [{name,count,avg}] 中累加一个样本，维护计数与滚动均值。"""
    dim_list = list(dim_list or [])
    entry = next((d for d in dim_list if d.get("name") == name), None)
    if entry is None:
        entry = {"name": name, "count": 0, "avg": 0.0}
        dim_list.append(entry)
    c = entry["count"] + 1
    entry["avg"] = round((entry["avg"] * entry["count"] + float(score)) / c, 2)
    entry["count"] = c
    return dim_list


def update_from_session(db: Session, user_id: int, dimensions: list[dict],
                        form_type: str = "", category: str = ""):
    """一场结束后，把维度得分累积进候选人长期记忆。dimensions: [{name,score,comment}]"""
    if not dimensions:
        return
    m = get_or_create(db, user_id)
    m.session_count = (m.session_count or 0) + 1

    for d in dimensions:
        name = d.get("name")
        score = float(d.get("score") or 0)
        if score < WEAK_THRESHOLD:
            m.weak_dims = _bump(m.weak_dims or [], name, score)
        elif score >= STRONG_THRESHOLD:
            m.strong_dims = _bump(m.strong_dims or [], name, score)

    # 题目类别：仅当整场均分偏弱时记一次弱项（避免偶发一场就钉死）
    if category:
        avg = sum(float(d.get("score") or 0) for d in dimensions) / max(1, len(dimensions))
        if avg < WEAK_THRESHOLD:
            cats = list(m.weak_cats or [])
            e = next((c for c in cats if c.get("name") == category), None)
            if e is None:
                e = {"name": category, "count": 0}
                cats.append(e)
            e["count"] = e["count"] + 1
            m.weak_cats = cats

    # 排序：最弱在前 / 最强在前，便于召回时优先点名
    m.weak_dims = sorted((m.weak_dims or []), key=lambda x: x.get("avg", 100))
    m.strong_dims = sorted((m.strong_dims or []), key=lambda x: -x.get("avg", 0))
    db.flush()


def retrieve_relevant(db: Session, user_id: int, *, dimension: str = "",
                      category: str = "", max_chars: int = 240) -> str | None:
    """按需召回与「当前题目维度/类别」相关的记忆片段，返回给 LLM 作为上下文。无记忆返回 None。"""
    m = db.query(CandidateMemory).filter_by(user_id=user_id).first()
    if not m or (m.session_count or 0) < 1:
        return None

    weak = [d for d in (m.weak_dims or []) if d.get("count", 0) >= 1]
    strong = [d for d in (m.strong_dims or []) if d.get("count", 0) >= 1]
    parts: list[str] = []

    # 指定维度且命中记忆：优先点名（最贴合「按需召回」）
    if dimension:
        hit_weak = next((d for d in weak if d["name"] == dimension), None)
        hit_strong = next((d for d in strong if d["name"] == dimension), None)
        if hit_weak:
            parts.append(
                f"候选人在「{dimension}」历史多次得分偏低（均分约 {hit_weak['avg']}），"
                f"请在本题重点考察并给出针对性改进建议。"
            )
        elif hit_strong:
            parts.append(
                f"候选人在「{dimension}」历史表现较好（均分约 {hit_strong['avg']}），"
                f"本题可适当提高考察深度。"
            )

    # 无维度命中时，仅在样本较充分（>=2 场）给总体薄弱概览，避免以偏概全
    if not parts and weak and (m.session_count or 0) >= 2:
        top = "、".join(f"「{d['name']}」" for d in weak[:3])
        parts.append(f"候选人历史薄弱维度：{top}；评分时可适当关注其相关表现。")

    if not parts:
        return None
    text = " ".join(parts)
    return text[:max_chars] if len(text) > max_chars else text

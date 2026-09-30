# -*- coding: utf-8 -*-
"""
可观测性指标聚合（对应标准④：记录成功率、耗时、Token 成本，建立量化评测指标）

数据来源：`llm_call_log`（LLM 调用明细，含 ctx_meta）与 `trace_span`（调用段）。
设计原则：
- **只做聚合，不做写**：本模块是只读查询层，写入由 services/tracing.py 负责；
- **窗口化**：所有概览都支持 `hours` 时间窗，避免全表扫描意义上的"历史包袱"；
- **分位数在 Python 侧算**：MySQL 无通用 percentile 函数，且样本量可控（限制取最近 N 条），
  简单可靠，也便于单测断言；
- **脏数据不致命**：ctx_meta 解析失败计入 unknown，不抛异常。

对外暴露的指标（即本项目的量化评测口径）：
    成功率 success_rate   = 成功调用 / 总调用
    耗时   avg/p50/p95     = 单次 LLM 调用端到端耗时（毫秒）
    成本   cost_cny        = 按配置单价估算（元），并给出单题均值
    上下文 ctx_stats       = 平均上下文 token、各层纳入率、超预算率（Phase 3 效果的可观测出口）
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.observability import LLMCallLog, TraceSpan

# 分位数计算最多回溯多少条（防止大表全量拉取）
_PCTL_SAMPLE_LIMIT = 2000


def percentile(values: list[float], p: float) -> Optional[float]:
    """线性插值分位数。p 取 0~100。空列表返回 None。"""
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    frac = k - lo
    return round(float(xs[lo]) * (1 - frac) + float(xs[hi]) * frac, 2)


def _since(hours: int) -> datetime:
    try:
        hours = int(hours or 0)
    except Exception:
        hours = 0
    if hours <= 0:
        return datetime(1970, 1, 1)
    return datetime.now() - timedelta(hours=hours)


def _base_query(db: Session, hours: int, scene: Optional[str] = None):
    q = db.query(LLMCallLog).filter(LLMCallLog.created_at >= _since(hours))
    if scene:
        q = q.filter(LLMCallLog.scene == scene)
    return q


def llm_overview(db: Session, hours: int = 24, scene: Optional[str] = None) -> dict:
    """LLM 调用总览：成功率 / 耗时分位 / Token / 成本。"""
    q = _base_query(db, hours, scene)
    total = q.count()
    if total == 0:
        return {
            "window_hours": hours, "scene": scene or "all",
            "total_calls": 0, "success_calls": 0, "failed_calls": 0,
            "success_rate": None,
            "avg_latency_ms": None, "p50_latency_ms": None, "p95_latency_ms": None,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cost_cny": 0.0, "avg_cost_per_call": None,
        }

    agg = db.query(
        func.sum(LLMCallLog.ok),
        func.sum(LLMCallLog.prompt_tokens),
        func.sum(LLMCallLog.completion_tokens),
        func.sum(LLMCallLog.total_tokens),
        func.sum(LLMCallLog.cost_cny),
        func.avg(LLMCallLog.latency_ms),
    ).filter(LLMCallLog.created_at >= _since(hours))
    if scene:
        agg = agg.filter(LLMCallLog.scene == scene)
    ok_sum, pt, ct, tt, cost, avg_lat = agg.first() or (0, 0, 0, 0, 0.0, None)

    latencies = [
        r[0] for r in db.query(LLMCallLog.latency_ms)
        .filter(LLMCallLog.created_at >= _since(hours))
        .order_by(LLMCallLog.id.desc()).limit(_PCTL_SAMPLE_LIMIT).all()
        if r[0] is not None
    ] if not scene else [
        r[0] for r in db.query(LLMCallLog.latency_ms)
        .filter(LLMCallLog.created_at >= _since(hours))
        .filter(LLMCallLog.scene == scene)
        .order_by(LLMCallLog.id.desc()).limit(_PCTL_SAMPLE_LIMIT).all()
        if r[0] is not None
    ]

    ok_n = int(ok_sum or 0)
    total_f = float(total)
    return {
        "window_hours": hours,
        "scene": scene or "all",
        "total_calls": total,
        "success_calls": ok_n,
        "failed_calls": total - ok_n,
        "success_rate": round(ok_n / total_f, 4),
        "avg_latency_ms": round(float(avg_lat or 0), 2),
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "prompt_tokens": int(pt or 0),
        "completion_tokens": int(ct or 0),
        "total_tokens": int(tt or 0),
        "cost_cny": round(float(cost or 0.0), 6),
        "avg_cost_per_call": round(float(cost or 0.0) / total_f, 6),
    }


def by_scene(db: Session, hours: int = 24) -> list[dict]:
    """按场景拆分统计（评分 / 实时反馈 / 群面 / 简历 ...）。"""
    rows = (
        db.query(
            LLMCallLog.scene,
            func.count(LLMCallLog.id),
            func.sum(LLMCallLog.ok),
            func.avg(LLMCallLog.latency_ms),
            func.sum(LLMCallLog.total_tokens),
            func.sum(LLMCallLog.cost_cny),
        )
        .filter(LLMCallLog.created_at >= _since(hours))
        .group_by(LLMCallLog.scene)
        .all()
    )
    out = []
    for scene, cnt, ok_sum, avg_lat, tokens, cost in rows:
        cnt = int(cnt or 0)
        ok_n = int(ok_sum or 0)
        lats = [
            r[0] for r in db.query(LLMCallLog.latency_ms)
            .filter(LLMCallLog.created_at >= _since(hours))
            .filter(LLMCallLog.scene == scene)
            .order_by(LLMCallLog.id.desc()).limit(_PCTL_SAMPLE_LIMIT).all()
            if r[0] is not None
        ]
        out.append({
            "scene": scene,
            "total_calls": cnt,
            "success_rate": round(ok_n / cnt, 4) if cnt else None,
            "avg_latency_ms": round(float(avg_lat or 0), 2),
            "p95_latency_ms": percentile(lats, 95),
            "total_tokens": int(tokens or 0),
            "cost_cny": round(float(cost or 0.0), 6),
        })
    out.sort(key=lambda d: -d["total_calls"])
    return out


def recent_calls(db: Session, limit: int = 50, scene: Optional[str] = None) -> list[dict]:
    """最近 N 条调用明细（排障用）。"""
    q = db.query(LLMCallLog)
    if scene:
        q = q.filter(LLMCallLog.scene == scene)
    rows = q.order_by(LLMCallLog.id.desc()).limit(max(1, min(int(limit or 50), 500))).all()
    return [r.to_dict() for r in rows]


def trace_detail(db: Session, trace_id: str) -> dict:
    """按 trace_id 还原一条链路：调用段 + LLM 调用（按时间升序）。"""
    spans = (
        db.query(TraceSpan).filter(TraceSpan.trace_id == trace_id)
        .order_by(TraceSpan.id.asc()).all()
    )
    calls = (
        db.query(LLMCallLog).filter(LLMCallLog.trace_id == trace_id)
        .order_by(LLMCallLog.id.asc()).all()
    )
    lat = [c.latency_ms for c in calls if c.latency_ms is not None]
    return {
        "trace_id": trace_id,
        "spans": [s.to_dict() for s in spans],
        "llm_calls": [c.to_dict() for c in calls],
        "totals": {
            "span_count": len(spans),
            "llm_call_count": len(calls),
            "total_tokens": sum(int(c.total_tokens or 0) for c in calls),
            "cost_cny": round(sum(float(c.cost_cny or 0) for c in calls), 6),
            "llm_latency_ms": sum(int(c.latency_ms or 0) for c in calls),
            "p95_latency_ms": percentile(lat, 95),
        },
    }


def ctx_stats(db: Session, hours: int = 24) -> dict:
    """上下文工程效果指标（消费 Phase 3 落库的 ctx_meta）。

    产出：平均上下文 token、各层纳入率、超预算率、去重丢弃层占比。
    """
    rows = (
        db.query(LLMCallLog.ctx_meta)
        .filter(LLMCallLog.created_at >= _since(hours))
        .filter(LLMCallLog.ctx_meta.isnot(None))
        .order_by(LLMCallLog.id.desc()).limit(_PCTL_SAMPLE_LIMIT)
        .all()
    )
    total = len(rows)
    if total == 0:
        return {"window_hours": hours, "sample_count": 0,
                "avg_context_tokens": None, "over_budget_rate": None,
                "layer_hit_rate": {}, "note": "窗口内暂无带 ctx_meta 的调用"}

    tokens: list[float] = []
    over = 0
    layer_hits: dict[str, int] = {}
    for (raw,) in rows:
        try:
            meta = json.loads(raw) if raw else None
        except Exception:
            meta = None
        if not isinstance(meta, dict):
            continue
        t = meta.get("total_tokens") or meta.get("context_tokens")
        if isinstance(t, (int, float)):
            tokens.append(float(t))
        if meta.get("over_budget"):
            over += 1
        for layer in (meta.get("included_layers") or []):
            layer_hits[str(layer)] = layer_hits.get(str(layer), 0) + 1

    return {
        "window_hours": hours,
        "sample_count": total,
        "avg_context_tokens": round(sum(tokens) / len(tokens), 1) if tokens else None,
        "max_context_tokens": round(max(tokens), 1) if tokens else None,
        "over_budget_rate": round(over / total, 4),
        "layer_hit_rate": {k: round(v / total, 4) for k, v in sorted(layer_hits.items(), key=lambda kv: -kv[1])},
    }


# —— 沙箱自测（内存 SQLite，不依赖 MySQL）——
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng, future=True)
    db = S()

    # 1) 分位数
    assert percentile([], 95) is None
    assert percentile([5], 95) == 5.0
    assert percentile([1, 2, 3, 4, 5], 50) == 3.0
    assert percentile([1, 2, 3, 4, 5], 95) == 4.8

    # 2) 造数据：score_answer 4 次（其中 1 次失败）、group_turn 1 次
    from app.services.tracing import record_llm_call
    for i, (sc, lat, ok) in enumerate([
        ("score_answer", 100, True), ("score_answer", 300, True),
        ("score_answer", 900, True), ("score_answer", 200, False),
        ("group_turn", 150, True),
    ]):
        record_llm_call(db, model="deepseek-chat", prompt_tokens=500, completion_tokens=200,
                        latency_ms=lat, ok=ok, scene_name=sc,
                        trace_id=f"t{i}", ctx_meta={"included_layers": ["task", "knowledge"],
                                                    "total_tokens": 700, "over_budget": False})

    ov = llm_overview(db, hours=24)
    assert ov["total_calls"] == 5, ov
    assert ov["success_calls"] == 4 and ov["success_rate"] == 0.8, ov
    assert ov["p95_latency_ms"] == 780.0, ov          # [100,150,200,300,900] → p95 = 300*0.2+900*0.8
    assert ov["total_tokens"] == 5 * 700, ov
    assert ov["cost_cny"] > 0, ov

    sc_map = {r["scene"]: r for r in by_scene(db, hours=24)}
    assert sc_map["score_answer"]["total_calls"] == 4, sc_map
    assert sc_map["score_answer"]["success_rate"] == 0.75, sc_map

    cs = ctx_stats(db, hours=24)
    assert cs["sample_count"] == 5 and cs["over_budget_rate"] == 0.0, cs
    assert cs["layer_hit_rate"]["knowledge"] == 1.0, cs

    td = trace_detail(db, "t0")
    assert td["totals"]["llm_call_count"] == 1 and td["totals"]["total_tokens"] == 700, td

    print("METRICS_SELFTEST_OK")

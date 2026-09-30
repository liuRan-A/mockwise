# -*- coding: utf-8 -*-
"""可观测性数据模型（对应标准④：评估与可观测性）

四张表分工：
1. `llm_call_log`  —— LLM 调用明细：每次真实调用一行，记录模型/入出 token/耗时/成本/成败/
                      场景/链路 trace_id，以及 Phase 3 上下文工程产出的 ctx_meta。
                      这是「成功率 / 耗时 / Token 成本」三类指标的**唯一事实来源**。
2. `trace_span`    —— 通用调用段（API / 编排步骤 / 工具），带 parent_span，
                      与 llm_call_log 通过 trace_id 串联，用于还原「一次请求走了哪些步」。
3. `eval_run`      —— 一次量化评测运行的汇总结论（成功率/稳定性/耗时/成本）。
4. `eval_sample`   —— 评测中每一条样本每一次重复的原始结果，用于定位是哪道题不稳定。

设计约束：
- 观测写入**绝不能阻断业务**：所有落库都在调用方 try/except 中完成（见 services/tracing.py）；
- 只存可聚合的标量 + 少量 JSON（ctx_meta / report），不做全量请求体落库（体积与隐私）；
- 时间字段统一用 `created_at`，指标按时间窗过滤。
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index, func

from app.core.database import Base


class LLMCallLog(Base):
    """LLM 调用明细（一次模型调用 = 一行）"""
    __tablename__ = "llm_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(32), nullable=False, index=True)      # 全链路追踪 ID（来自中间件）
    span_id = Column(String(32), nullable=True)                    # 所属调用段
    scene = Column(String(32), nullable=False, index=True,
                   default="-")                                    # 场景：score_answer / analyze_answer / group_turn / resume ...
    model = Column(String(64), nullable=True)
    ok = Column(Integer, nullable=False, default=1)                # 1 成功 / 0 失败（失败通常不落库，由调用方补记）
    error = Column(Text, nullable=True)

    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    cost_cny = Column(Float, nullable=False, default=0.0)          # 估算成本（元）

    user_id = Column(Integer, nullable=True, index=True)
    ctx_meta = Column(Text, nullable=True)                         # Phase 3 上下文工程元数据（JSON 字符串）
    created_at = Column(DateTime, server_default=func.now(), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "scene": self.scene,
            "model": self.model,
            "ok": self.ok,
            "error": self.error,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "cost_cny": round(self.cost_cny or 0.0, 6),
            "user_id": self.user_id,
            "ctx_meta": _safe_loads(self.ctx_meta),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TraceSpan(Base):
    """通用调用段：API 入口 / 编排步骤 / 工具调用，用于还原调用链"""
    __tablename__ = "trace_span"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(32), nullable=False, index=True)
    span_id = Column(String(32), nullable=False)
    parent_span_id = Column(String(32), nullable=True)
    name = Column(String(64), nullable=False)                      # 段名：POST /api/v1/sessions、agent.step 等
    kind = Column(String(16), nullable=False, default="span")      # api / agent / tool / db
    ok = Column(Integer, nullable=False, default=1)
    latency_ms = Column(Integer, nullable=False, default=0)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvalRun(Base):
    """一次量化评测运行的汇总结论"""
    __tablename__ = "eval_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=True)
    scene = Column(String(32), nullable=False, default="score_answer")
    sample_count = Column(Integer, nullable=False, default=0)
    repeat = Column(Integer, nullable=False, default=1)
    offline = Column(Integer, nullable=False, default=1)           # 1=离线注入假 LLM（不烧钱、可复现）

    success_rate = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    p95_latency_ms = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_cny = Column(Float, nullable=True)
    # 评分稳定性：同一批样本重复跑，分数的标准差与极差（越小越稳定）
    score_std = Column(Float, nullable=True)
    score_range = Column(Float, nullable=True)
    report = Column(Text, nullable=True)                           # 完整报告 JSON
    created_at = Column(DateTime, server_default=func.now(), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "scene": self.scene,
            "sample_count": self.sample_count,
            "repeat": self.repeat,
            "offline": self.offline,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "total_tokens": self.total_tokens,
            "cost_cny": round(self.cost_cny or 0.0, 6),
            "score_std": self.score_std,
            "score_range": self.score_range,
            "report": _safe_loads(self.report),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvalSample(Base):
    """评测样本级结果（每样本 × 每轮重复 = 一行）"""
    __tablename__ = "eval_sample"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, nullable=False, index=True)
    sample_idx = Column(Integer, nullable=False)
    repeat_idx = Column(Integer, nullable=False, default=0)
    sample_name = Column(String(64), nullable=True)
    ok = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=True)
    expected_lo = Column(Float, nullable=True)                     # 期望分数带下界（用于一致性判定）
    expected_hi = Column(Float, nullable=True)
    in_band = Column(Integer, nullable=True)                       # 得分是否落在期望带内
    latency_ms = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    engine = Column(String(16), nullable=True)                     # deepseek / rule / fake
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "sample_idx": self.sample_idx,
            "repeat_idx": self.repeat_idx,
            "sample_name": self.sample_name,
            "ok": self.ok,
            "score": self.score,
            "expected_lo": self.expected_lo,
            "expected_hi": self.expected_hi,
            "in_band": self.in_band,
            "latency_ms": self.latency_ms,
            "total_tokens": self.total_tokens,
            "engine": self.engine,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# trace_id + scene 联合索引：按场景统计与时间窗过滤的高频查询
Index("ix_llm_call_scene_created", LLMCallLog.scene, LLMCallLog.created_at)


def _safe_loads(s):
    """JSON 字段容错解析（脏数据不应让接口 500）。"""
    if not s:
        return None
    try:
        import json
        return json.loads(s)
    except Exception:
        return None

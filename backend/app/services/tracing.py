# -*- coding: utf-8 -*-
"""
全链路追踪层（对应标准④：全链路追踪调用 / 成功率 / 耗时 / Token 成本）

职责边界：
- 承接 Phase 2 `llm_client` 暴露的用量钩子（原本只打日志），把每次 LLM 调用**落库**成 `llm_call_log`；
- 提供 `scene(...)` 场景标记与 `span(...)` 调用段，把「API → 编排 → 工具 → LLM」串在同一条 trace 上；
- 承接 Phase 3 上下文工程产出的 `ctx_meta`，一并落库，让「上下文是否命中/超预算」可量化。

**铁律：观测写入绝不能阻断业务。** 所有落库都在 try/except 中完成，
数据库不可用时只告警（且降频），调用方拿到的业务结果不受任何影响。

用法：
    from app.services.tracing import scene, span, attach_ctx_meta

    with scene("score_answer"), span("score", kind="agent"):
        attach_ctx_meta(ctx["meta"])
        data = llm_client.chat_json(...)     # 调用结束自动落一条 llm_call_log
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger, request_id_var, user_id_var

log = get_logger("tracing")

# —— 请求级上下文 ——
# scene：当前所处业务场景（评分 / 实时反馈 / 群面 / 简历解析...），由 with scene(...) 设置
scene_var: ContextVar[str] = ContextVar("obs_scene", default="-")
# 当前调用段 ID，LLM 落库时挂到 span_id
span_id_var: ContextVar[str] = ContextVar("obs_span_id", default="-")
# 待附加的上下文工程元数据（由 attach_ctx_meta 写入，落库后清除）
_pending_ctx_var: ContextVar[Optional[dict]] = ContextVar("obs_pending_ctx", default=None)

# 落库失败降频开关：避免数据库不可用时每条日志都刷屏
_persist_failed = False


# ————————————————————————————————————————————————
# 基础工具
# ————————————————————————————————————————————————
def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def current_trace_id() -> str:
    """当前链路 ID（由请求中间件写入 contextvar；无请求时为 '-'）。"""
    return request_id_var.get() or "-"


def current_scene() -> str:
    return scene_var.get() or "-"


def attach_ctx_meta(meta: Optional[dict]) -> None:
    """把 Phase 3 上下文元数据挂到下一次 LLM 调用上（落库后自动清除）。"""
    if meta:
        _pending_ctx_var.set(meta)


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """按配置单价估算成本（元）。配置缺失时返回 0，绝不抛错。"""
    try:
        from app.core.config import settings
        pin = float(getattr(settings, "LLM_PRICE_IN_PER_1K", 0.0) or 0.0)
        pout = float(getattr(settings, "LLM_PRICE_OUT_PER_1K", 0.0) or 0.0)
        return round((prompt_tokens / 1000.0) * pin + (completion_tokens / 1000.0) * pout, 8)
    except Exception:
        return 0.0


# ————————————————————————————————————————————————
# 调用段（span）
# ————————————————————————————————————————————————
class Span:
    """一个调用段：记录名称、类型、耗时、成败，并作为子段的父节点。"""

    def __init__(self, name: str, kind: str = "span", trace_id: Optional[str] = None,
                 parent_span_id: Optional[str] = None):
        self.name = name
        self.kind = kind
        self.trace_id = trace_id or current_trace_id()
        self.span_id = new_span_id()
        self.parent_span_id = parent_span_id
        self.t0 = time.time()
        self.latency_ms = 0
        self.ok = True
        self.detail: Optional[str] = None

    def finish(self, ok: bool = True, detail: Optional[str] = None) -> None:
        self.ok = ok
        self.detail = detail[:1000] if detail else None
        self.latency_ms = int((time.time() - self.t0) * 1000)

    def to_row(self):
        from app.models.observability import TraceSpan
        return TraceSpan(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            name=self.name,
            kind=self.kind,
            ok=1 if self.ok else 0,
            latency_ms=self.latency_ms,
            detail=self.detail,
        )


@contextmanager
def scene(name: str) -> Iterator[str]:
    """标记当前业务场景（落库到 llm_call_log.scene，用于分场景统计）。"""
    token = scene_var.set(name or "-")
    try:
        yield name
    finally:
        scene_var.reset(token)


@contextmanager
def span(name: str, kind: str = "span", db: Optional[Session] = None,
         persist: bool = True) -> Iterator[Span]:
    """开启一个调用段：结束时写 trace_span 并打结构化日志。

    db 为空时自动开一个短会话写入（观测用独立会话，不污染请求事务）。
    """
    parent = span_id_var.get()
    sp = Span(name=name, kind=kind, parent_span_id=(parent if parent and parent != "-" else None))
    token = span_id_var.set(sp.span_id)
    try:
        yield sp
    except Exception as e:
        sp.finish(ok=False, detail=f"{type(e).__name__}: {e}")
        if persist:
            _persist_span(sp, db)
        span_id_var.reset(token)
        raise
    else:
        sp.finish(ok=True)
        if persist:
            _persist_span(sp, db)
        span_id_var.reset(token)


def _persist_span(sp: Span, db: Optional[Session] = None) -> None:
    log.info("[span] trace=%s name=%s kind=%s latency_ms=%s ok=%s",
             sp.trace_id, sp.name, sp.kind, sp.latency_ms, sp.ok)
    if not _persist_enabled():
        return
    own = db is None
    try:
        if own:
            from app.core.database import SessionLocal
            db = SessionLocal()
        db.add(sp.to_row())
        db.commit()
    except Exception as e:
        if own and db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        _warn_persist(e)
    finally:
        if own and db is not None:
            try:
                db.close()
            except Exception:
                pass


# ————————————————————————————————————————————————
# LLM 调用明细落库
# ————————————————————————————————————————————————
def _persist_enabled() -> bool:
    try:
        from app.core.config import settings
        return bool(getattr(settings, "OBS_PERSIST", True))
    except Exception:
        return True


def _warn_persist(e: Exception) -> None:
    """落库失败告警，降频（只刷一次），绝不抛出。"""
    global _persist_failed
    if not _persist_failed:
        _persist_failed = True
        log.warning("[obs] 观测数据落库失败（业务不受影响，后续同类告警降频）: %s", e)


def record_llm_call(db: Optional[Session] = None, *, model: str = "",
                    prompt_tokens: int = 0, completion_tokens: int = 0,
                    latency_ms: int = 0, ok: bool = True, error: Optional[str] = None,
                    scene_name: Optional[str] = None, trace_id: Optional[str] = None,
                    ctx_meta: Optional[dict] = None, user_id: Optional[int] = None):
    """写入一条 LLM 调用明细。db 为空时开短会话；任何失败都只告警。"""
    from app.models.observability import LLMCallLog

    pt = int(prompt_tokens or 0)
    ct = int(completion_tokens or 0)
    meta = ctx_meta if ctx_meta is not None else _pending_ctx_var.get()
    if ctx_meta is None:
        # 取走即清除，避免同一次请求里后续调用误挂同一份元数据
        try:
            _pending_ctx_var.set(None)
        except Exception:
            pass

    row = LLMCallLog(
        trace_id=trace_id or current_trace_id(),
        span_id=span_id_var.get(),
        scene=scene_name or current_scene(),
        model=model or "",
        ok=1 if ok else 0,
        error=(error or None),
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=pt + ct,
        latency_ms=int(latency_ms or 0),
        cost_cny=estimate_cost(pt, ct),
        user_id=user_id,
        ctx_meta=json.dumps(meta, ensure_ascii=False) if meta else None,
    )

    if not _persist_enabled():
        return row

    own = db is None
    try:
        if own:
            from app.core.database import SessionLocal
            db = SessionLocal()
        db.add(row)
        db.commit()
    except Exception as e:
        if own and db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        _warn_persist(e)
    finally:
        if own and db is not None:
            try:
                db.close()
            except Exception:
                pass
    return row


def _on_usage(*, model: str, prompt_tokens: int, completion_tokens: int,
              latency_ms: int, ok: bool) -> None:
    """注册到 llm_client 的用量钩子：把调用明细落库（带场景/链路/上下文元数据）。"""
    uid = None
    try:
        raw = user_id_var.get()
        uid = int(raw) if raw and raw not in ("-", "") else None
    except Exception:
        uid = None
    record_llm_call(model=model, prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens, latency_ms=latency_ms,
                    ok=ok, user_id=uid)


def install_usage_hook() -> None:
    """把落库钩子挂到 llm_client（幂等；未挂上时用量只记日志）。"""
    try:
        from app.services import llm_client
        llm_client.register_usage_hook(_on_usage)
    except Exception as e:
        _warn_persist(e)


# ————————————————————————————————————————————————
# 沙箱自测（无外部依赖，纯内存）
# ————————————————————————————————————————————————
if __name__ == "__main__":
    # 1) 场景 / span / 上下文元数据的捕获
    with scene("score_answer"):
        attach_ctx_meta({"included_layers": ["task", "knowledge"], "total_tokens": 320})
        assert current_scene() == "score_answer", current_scene()
        meta_snapshot = _pending_ctx_var.get()
        assert meta_snapshot and "knowledge" in meta_snapshot["included_layers"]
    assert current_scene() == "-", "scene 退出后应复位"

    # 2) 成本核算
    c = estimate_cost(1000, 500)   # 1K 输入 + 0.5K 输出
    assert abs(c - (0.002 + 0.004)) < 1e-9, c

    # 3) span 计时与父子关系
    with span("api", kind="api", persist=False) as s1:
        time.sleep(0.01)
        with span("llm", kind="tool", persist=False) as s2:
            pass
        assert s2.parent_span_id == s1.span_id, "子段应挂到父段"
    assert s1.latency_ms >= 10, s1.latency_ms
    assert s1.ok is True

    # 4) 异常段应标记失败并继续抛出
    try:
        with span("boom", persist=False) as s3:
            raise ValueError("x")
    except ValueError:
        assert s3.ok is False and "ValueError" in (s3.detail or "")

    print("TRACING_SELFTEST_OK")

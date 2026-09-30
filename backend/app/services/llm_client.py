# -*- coding: utf-8 -*-
"""
加固版 LLM 客户端（对应标准②：Agent 核心能力 — 失败重试 / 结果校验 / 多步可控）

相对原 services/llm.py 中朴素的 `_chat_json`（失败即返回 None 降级），本模块补齐：
1. 网络层重试 + 退避：超时 / 连接错误 / 5xx / 429 触发指数退避重试（tenacity 优先，缺失则内置手动退避）；
2. 结构化输出校验-重试（validate-retry）：调用 `structured()` 时先用 Pydantic / 可调用 / 字段清单
   校验模型返回，校验不通过则追加「纠正指令」重新请求，最多 `max_struct_retries` 次；
3. Token 用量埋点：通过 `register_usage_hook` 暴露 (model, prompt_tokens, completion_tokens, latency_ms, ok)，
   供 Phase 4 可观测性接入（本模块只记日志，不做持久化）；
4. 失败语义清晰：网络/校验重试耗尽抛出 `UpstreamError`（调用方据此降级，例如群面退回模板生成）。

设计约束：
- 对调用方保持「返回 None 即降级」的兼容语义（`chat_json` 在重试耗尽/无 Key 时返回 None），
  因此原 llm.py 的评分/反馈链路无需改动即可获得重试与用量埋点；
- httpx 与 settings 延迟导入（函数内），使本模块在无 fastapi/pydantic 的沙箱中也**可被 import**，
  便于对 `structured` 的校验-重试逻辑做单测（注入假 call）。
"""
from __future__ import annotations

import json
import time
import logging
from typing import Any, Callable, Optional, Union

from app.core.errors import UpstreamError
from app.core.logging_config import get_logger

log = get_logger("llm")

# —— 可观测性钩子（Phase 4 会注册持久化实现）——
_USAGE_HOOKS: list[Callable] = []


def register_usage_hook(fn: Callable) -> None:
    """注册一个用量回调：fn(model, prompt_tokens, completion_tokens, latency_ms, ok)。"""
    if callable(fn) and fn not in _USAGE_HOOKS:
        _USAGE_HOOKS.append(fn)


def _emit_usage(model: str, prompt_tokens: int, completion_tokens: int,
                latency_ms: int, ok: bool) -> None:
    log.info("[llm:usage] model=%s prompt=%d completion=%d latency_ms=%d ok=%s",
             model, prompt_tokens, completion_tokens, latency_ms, ok)
    for h in _USAGE_HOOKS:
        try:
            h(model=model, prompt_tokens=prompt_tokens,
              completion_tokens=completion_tokens, latency_ms=latency_ms, ok=ok)
        except Exception:  # 钩子异常不应影响主流程
            pass


# —— 重试基础设施（tenacity 可选）——
try:
    import tenacity  # type: ignore
    _HAVE_TENACITY = True
except Exception:  # pragma: no cover - 无 tenacity 时走内置手动退避
    tenacity = None  # type: ignore
    _HAVE_TENACITY = False


class _NoKeyError(Exception):
    """无 API Key，不算网络错误，不重试。"""


class _BadJSONError(Exception):
    """返回内容无法解析为 JSON，在 structured 层处理，不在网络层重试。"""


def _retry_exceptions() -> tuple:
    """网络层可重试异常（不含 4xx 业务错误与无 Key）。"""
    excs: list[type] = [ConnectionError, OSError]
    try:
        import httpx
        excs.append(httpx.HTTPError)
    except Exception:
        pass
    return tuple(excs)


def _safe_json(content: str) -> Optional[dict]:
    """容错解析：模型偶尔在 JSON 外包裹 markdown 代码块。"""
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        pass
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        return json.loads(content[start:end])
    except Exception:
        return None


def _one_attempt(system: str, user: str, timeout: Optional[int],
                 temperature: float, max_tokens: int, json_mode: bool) -> dict:
    """单次网络请求；失败时抛出（由重试层捕获）。不在此层做业务降级。"""
    from app.core.config import settings  # 延迟导入：避免无 pydantic 环境 import 失败
    import httpx  # 延迟导入

    api_key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        raise _NoKeyError("DEEPSEEK_API_KEY 未配置")

    url = settings.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    t0 = time.time()
    with httpx.Client(timeout=timeout or settings.LLM_TIMEOUT_S) as client:
        resp = client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        # 429 / 5xx 视为可重试；其余 4xx 直接按上游错误抛出（不重试）
        if resp.status_code in (429, 500, 502, 503, 504):
            try:
                resp.raise_for_status()
            except Exception:
                raise
        raise UpstreamError(f"LLM 返回 {resp.status_code}: {resp.text[:200]}")
    try:
        payload_json = resp.json()
    except Exception:
        raise _BadJSONError("响应体非 JSON")
    try:
        content = payload_json["choices"][0]["message"]["content"]
    except Exception:
        raise _BadJSONError("响应结构异常")
    parsed = _safe_json(content)
    if parsed is None:
        raise _BadJSONError("无法解析为 JSON 对象")
    usage = payload_json.get("usage") or {}
    if usage:
        _emit_usage(
            settings.DEEPSEEK_MODEL,
            int(usage.get("prompt_tokens", 0) or 0),
            int(usage.get("completion_tokens", 0) or 0),
            int((time.time() - t0) * 1000),
            True,
        )
    return parsed


def _with_retry(fn: Callable, attempts: int):
    """网络层重试：tenacity 优先，缺失则手动指数退避。"""
    if _HAVE_TENACITY and tenacity is not None:
        @tenacity.retry(
            stop=tenacity.stop_after_attempt(attempts),
            wait=tenacity.wait_exponential(multiplier=0.4, min=0.4, max=4),
            retry=tenacity.retry_if_exception_type(_retry_exceptions()),
            reraise=True,
        )
        def _w():
            return fn()
        return _w()
    # 手动退避（无 tenacity 时）
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 退避后重抛最后一次
            last = e
            if i < attempts - 1:
                time.sleep(min(0.4 * (2 ** i), 4))
    raise last  # type: ignore[misc]


def chat_json(system: str, user: str, *, timeout: Optional[int] = None,
              temperature: float = 0.3, max_tokens: int = 1200,
              json_mode: bool = True, attempts: int = 3) -> Optional[dict]:
    """调用大模型并解析 JSON。

    返回：
      - dict：成功解析
      - None：无 Key / 网络重试耗尽 / 返回无法解析 / 上游错误 —— 调用方据此降级
    """
    def _go():
        return _one_attempt(system, user, timeout, temperature, max_tokens, json_mode)
    try:
        return _with_retry(_go, attempts)
    except (_NoKeyError, UpstreamError):
        return None
    except Exception as e:  # 任何意外都降级，绝不让 LLM 故障拖垮业务
        log.warning("[llm] chat_json 异常降级: %s", e)
        return None


# —— schema 校验 ——
def validate_schema(schema: Any, data: Any):
    """校验数据是否符合 schema。

    支持三种 schema：
      - pydantic v1 BaseModel 子类：用 parse_obj，返回 .dict()
      - callable：调用它，返回其返回值（抛异常视为不通过）
      - list/tuple：要求 data 含全部这些顶层键
    返回 (ok, value, err)。
    """
    if schema is None:
        return True, data, None
    # pydantic v1 模型（缺失 pydantic 时安全跳过该分支）
    try:
        from pydantic import BaseModel as _BM, ValidationError as _VE
    except Exception:  # pragma: no cover - 无 pydantic 环境
        _BM = None
        _VE = None
    if _BM is not None and isinstance(schema, type) and issubclass(schema, _BM):
        try:
            model = schema.parse_obj(data)
            return True, model.dict(), None
        except _VE as e:  # noqa: F821
            return False, None, str(e)
    if callable(schema):
        try:
            r = schema(data)
        except Exception as e:  # noqa: BLE001 - 抛异常即视为不通过
            return False, None, str(e)
        if r is True:
            return True, data, None          # 布尔校验器：True=通过，保留原数据
        if r is False:
            return False, None, "校验未通过"   # False=不通过
        return True, r, None                  # 返回的是校验后/转换后的值
    if isinstance(schema, (list, tuple)):
        missing = [k for k in schema if k not in (data or {})]
        if missing:
            return False, None, f"缺少字段: {missing}"
        return True, data, None
    return True, data, None


def structured(system: str, user: str, schema: Any, *,
               temperature: float = 0.2, max_tokens: int = 800,
               timeout: Optional[int] = None, max_struct_retries: int = 2,
               call: Optional[Callable] = None) -> dict:
    """带 schema 校验的结构化调用：校验失败自动追加纠正指令并重试。

    参数 call 用于注入 LLM 调用（默认 chat_json），便于单测不依赖网络/Key。
    call 签名需兼容：call(system, user, *, temperature, max_tokens, timeout, json_mode) -> dict | None。

    成功返回校验后的 dict；重试耗尽抛出 UpstreamError（调用方据此降级）。
    """
    call = call or chat_json
    base_user = user
    last_err = ""
    for attempt in range(1, max_struct_retries + 1):
        data = call(system, base_user, temperature=temperature,
                    max_tokens=max_tokens, timeout=timeout, json_mode=True)
        if data is None:
            last_err = "LLM 返回为空或无法解析为 JSON"
            base_user = user + ("\n\n[纠正 %d] 你必须只输出一个可被解析的 JSON 对象，"
                                "不要包含 markdown 代码块或任何多余文字。" % attempt)
            continue
        ok, val, err = validate_schema(schema, data)
        if ok:
            return val
        last_err = err or "校验未通过"
        base_user = user + ("\n\n[纠正 %d] 上次输出不符合要求：%s。"
                            "请严格按要求的 JSON 结构重新输出。" % (attempt, last_err))
    raise UpstreamError(f"structured 校验重试耗尽: {last_err}")

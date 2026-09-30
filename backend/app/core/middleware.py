# -*- coding: utf-8 -*-
"""
请求上下文中间件

职责：
1. 每个请求分配/透传 trace_id（支持上游通过 X-Trace-Id 传入，便于网关侧串联）；
2. 记录访问日志：方法 / 路径 / 状态码 / 耗时（ms），这是可观测性的基础指标；
3. 把 trace_id 写回响应头 X-Trace-Id，前端排障时可回传。
"""
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import request_id_var, get_logger

log = get_logger("access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:16]
        token_rid = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            # 异常会交由异常 handler 转成统一响应，这里只记录访问日志并放行
            dur_ms = round((time.perf_counter() - start) * 1000, 1)
            log.warning(
                "access %s %s -> 500(E) cost=%sms",
                request.method,
                request.url.path,
                dur_ms,
            )
            request_id_var.reset(token_rid)
            raise
        dur_ms = round((time.perf_counter() - start) * 1000, 1)
        log.info(
            "access %s %s -> %s cost=%sms",
            request.method,
            request.url.path,
            response.status_code,
            dur_ms,
        )
        response.headers["X-Trace-Id"] = rid
        request_id_var.reset(token_rid)
        return response

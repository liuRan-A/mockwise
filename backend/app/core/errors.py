# -*- coding: utf-8 -*-
"""
应用异常体系

为什么需要它：
- 原来只有一个 catch-all handler，且把 `f"服务器内部错误: {exc}"` 原始异常直接回传前端（信息泄露）；
- 业务/校验/未找到/无权限/上游不可用等错误应当被分级处理，返回 `{code,msg,data,trace_id}` 的统一结构，
  且不暴露堆栈与内部细节（安全），只给前端一个 trace_id 便于排查（可观测性）。

约定：
- 业务代码统一 `raise AppError 子类(...)`，不要在响应里拼装错误信息；
- 未知异常走 unhandled_handler，返回 500 + 安全提示 + trace_id，并记录完整堆栈。
"""
from __future__ import annotations

from app.core.logging_config import request_id_var, get_logger

log = get_logger("error")


class AppError(Exception):
    """所有业务异常的基类。"""

    code: int = 1
    status: int = 400
    msg: str = "业务错误"

    def __init__(self, msg: str | None = None, status: int | None = None,
                 code: int | None = None, data=None):
        self.msg = msg or self.msg
        self.status = status or self.status
        self.code = code or self.code
        self.data = data


class BadRequestError(AppError):
    status = 400
    msg = "请求参数错误"


class UnauthorizedError(AppError):
    status = 401
    msg = "未认证或登录已过期"


class ForbiddenError(AppError):
    status = 403
    msg = "没有权限执行该操作"


class NotFoundError(AppError):
    status = 404
    msg = "资源不存在"


class ConflictError(AppError):
    status = 409
    msg = "资源状态冲突，请刷新后重试"


class UpstreamError(AppError):
    """上游（如大模型/讯飞）不可用。"""

    status = 502
    msg = "上游服务暂不可用，请稍后重试"


def _body(msg: str, code: int, trace_id: str, data=None) -> dict:
    return {"code": code, "msg": msg, "data": data, "trace_id": trace_id}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """已知业务异常：记录 warn 级日志，返回安全且结构统一的响应。"""
    from fastapi.responses import JSONResponse
    log.warning(
        "app_error %s %s [%s] %s",
        request.method, request.url.path, exc.status, exc.msg,
    )
    return JSONResponse(
        status_code=exc.status,
        content=_body(exc.msg, exc.code, request_id_var.get(), exc.data),
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """未知异常：记完整堆栈，返回 500 + 安全提示 + trace_id（绝不泄露原始异常）。"""
    from fastapi.responses import JSONResponse
    log.exception("unhandled %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_body(
            "服务器内部错误，请稍后重试或联系管理员",
            500,
            request_id_var.get(),
        ),
    )

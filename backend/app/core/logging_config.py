# -*- coding: utf-8 -*-
"""
结构化日志配置

设计目标：
1. 统一 JSON 行格式，便于后续接入 ELK / Loki 等日志系统做可观测性（对应标准④地基）；
2. 通过 contextvars 注入请求级上下文（trace_id / uid），让一条请求的所有日志串成链；
3. 业务代码只需 `from app.core.logging_config import get_logger` 即可拿到带上下文的 logger。
"""
import json
import logging
import sys
from contextvars import ContextVar

# —— 请求级上下文（由 middleware 写入）——
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class RequestContextFilter(logging.Filter):
    """把请求级上下文塞进每一条日志记录，方便全链路追踪。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = request_id_var.get()
        record.uid = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """单行 JSON 格式，含时间/级别/模块/trace_id/uid/消息/异常栈。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "uid": getattr(record, "uid", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """初始化根日志：JSON 输出 + 上下文 filter。幂等，只生效一次。"""
    global _configured
    root = logging.getLogger()
    # 替换掉 logging.basicConfig 产生的默认 handler，避免重复输出
    root.handlers = []
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    # 注意：filter 必须挂在 handler 上，子 logger 的日志经 propagate 到 root 的
    # handler 时才会统一注入 trace_id/uid；挂在 logger 上不会跨 logger 生效。
    handler.addFilter(RequestContextFilter())
    root.addHandler(handler)
    root.setLevel(level)
    _configured = True

    # 降噪：第三方访问日志太吵，只保留 warning 以上
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    return root


def get_logger(name: str) -> logging.Logger:
    """获取一个业务 logger（自动继承根配置的 JSON 格式与上下文 filter）。"""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)

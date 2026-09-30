"""Mockwise API · FastAPI 入口"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.errors import AppError, app_error_handler, unhandled_handler
from app.api.v1.router import api_router
from app.api.ws_asr import router as ws_asr_router
from app.core.database import Base, engine
from app.models import user, position, question, session, group, report  # noqa: F401  注册所有模型（Resume 在 position 内）
from app.models.audit import AdminAudit  # noqa: F401  注册审计表
from app.models.memory import CandidateMemory  # noqa: F401  注册候选人长期记忆表
from app.models.observability import LLMCallLog, TraceSpan, EvalRun, EvalSample  # noqa: F401  可观测性表
from app.models.approval import ContentApproval  # noqa: F401  人工审批卡点表
from app.models.cms import Announcement, Category, Carousel  # noqa: F401  CMS 运营内容表

# 工程化日志（JSON + 请求上下文），替换原来的 basicConfig
configure_logging(level=logging.INFO if settings.DEBUG else logging.INFO)
log = get_logger("startup")

# 简历等上传文件目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "resumes"), exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表（如果未执行 schema.sql）
    Base.metadata.create_all(bind=engine)
    # 可观测性：把 LLM 用量钩子挂上，调用明细自动落 llm_call_log（失败不影响启动）
    try:
        from app.services.tracing import install_usage_hook
        install_usage_hook()
    except Exception:
        log.exception("可观测性钩子安装失败（业务不受影响）")
    log.info("Mockwise 启动完成，已注册 %s 张表", len(Base.metadata.tables))
    yield


app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 请求上下文（trace_id / 访问日志）中间件
app.add_middleware(RequestContextMiddleware)

# 分级异常 handler（替代原来泄露原始异常的 catch-all）
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_handler)


@app.get("/", tags=["root"])
def root():
    return {"code": 0, "msg": "ok", "data": {"name": settings.APP_NAME, "version": "v1.0"}}


@app.get("/health", tags=["root"])
def health():
    return {"code": 0, "msg": "ok", "data": {"status": "up"}}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_asr_router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

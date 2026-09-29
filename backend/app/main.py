"""Mockwise API · FastAPI 入口"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1.router import api_router
from app.api.ws_asr import router as ws_asr_router
from app.core.database import Base, engine
from app.models import user, position, question, session, group, report  # noqa: F401  注册所有模型（Resume 在 position 内）

logging.basicConfig(level=logging.INFO)

# 简历等上传文件目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "resumes"), exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动建表（如果未执行 schema.sql）
    Base.metadata.create_all(bind=engine)
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


@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 1, "msg": f"服务器内部错误: {exc}", "data": None},
    )


@app.get("/", tags=["root"])
def root():
    return {"code": 0, "msg": "ok", "data": {"name": settings.APP_NAME, "version": "v1.0"}}


@app.get("/health", tags=["root"])
def health():
    return {"code": 0, "msg": "ok", "data": {"status": "up"}}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_asr_router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

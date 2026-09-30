"""Mockwise AI 模拟面试助手 · 后端配置"""
import os
from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "Mockwise API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # MySQL 数据库
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "root")
    DB_NAME: str = os.getenv("DB_NAME", "mockwise")

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # JWT
    SECRET_KEY: str = "mockwise-dev-secret-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8h

    # 科大讯飞 语音听写（流式 IAT）WebAPI
    IFLY_APP_ID: str = ""
    IFLY_API_KEY: str = ""
    IFLY_API_SECRET: str = ""

    # DeepSeek 大模型（评分 / 反馈 / 追问）。未配置时自动降级为规则评分，业务不中断
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_S: int = 40

    # —— 可观测性：单价（元 / 1K tokens），用于估算单次调用成本 ——
    # DeepSeek 官方定价约 输入 ¥2 / 百万 tokens、输出 ¥8 / 百万 tokens，换算即 0.002 / 0.008 每 1K
    LLM_PRICE_IN_PER_1K: float = 0.002
    LLM_PRICE_OUT_PER_1K: float = 0.008
    # 是否把 LLM 调用明细落库（关闭则只记结构化日志，不写表）
    OBS_PERSIST: bool = True

    # —— 人机协同：高危操作人工审核卡点 ——
    # 关闭后所有内容变更即时生效（仅留审计），开启后命中动作进入「草稿 → 待审」状态机
    APPROVAL_ENABLED: bool = True
    # 需要人工复核的动作（逗号分隔）。delete 会连带删除关联题目，publish/unpublish 直接影响线上题库
    APPROVAL_ACTIONS: str = "delete,publish,unpublish"
    # 是否允许提交人自行审批（单人部署时为 True；团队部署应设 False 实现真正的双人复核）
    APPROVAL_ALLOW_SELF: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()

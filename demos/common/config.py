# -*- coding: utf-8 -*-
"""
配置加载：优先从 backend/.env 读取 DeepSeek 凭证（不把密钥写死在代码里、不提交到 Git）。
也可通过环境变量覆盖。
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # python-dotenv 未装时降级
    def load_dotenv(*_a, **_k):
        return False


# 从 demos/common 向上查找 backend/.env（不把密钥写死、不提交）
_HERE = Path(__file__).resolve().parent
_ENV_CANDIDATES = []
_root = _HERE
for _ in range(4):
    _ENV_CANDIDATES.append(_root / "backend" / ".env")
    _ENV_CANDIDATES.append(_root / ".env")
    _root = _root.parent

for _p in _ENV_CANDIDATES:
    if _p.exists():
        load_dotenv(_p)
        break

DEEPSEEK_API_KEY = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
DEEPSEEK_BASE_URL = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = (os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S") or "40")


def has_key() -> bool:
    return bool(DEEPSEEK_API_KEY)

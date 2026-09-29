# -*- coding: utf-8 -*-
"""
DeepSeek 客户端封装（OpenAI 兼容接口）。
- chat(): 普通对话
- chat_json(): 结构化 JSON 输出（带 markdown 容错）
- chat_with_tools(): 支持 function calling，返回完整 message（含 tool_calls）

任何异常都向上抛出，由调用方决定如何处理（demo 中直接打印友好提示）。
"""
from __future__ import annotations
from typing import Optional

from openai import OpenAI

import config


def get_client() -> "OpenAI":
    if not config.has_key():
        raise RuntimeError(
            "未找到 DEEPSEEK_API_KEY。请在 backend/.env 中填写，或设置环境变量 DEEPSEEK_API_KEY。"
        )
    return OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    timeout: Optional[int] = None,
) -> str:
    client = get_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout or config.LLM_TIMEOUT_S,
    )
    return resp.choices[0].message.content or ""


def chat_json(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    timeout: Optional[int] = None,
) -> dict:
    """请求 JSON 输出并做容错解析（兼容模型偶尔包裹的 markdown 代码块）。"""
    msgs = list(messages)
    if msgs and msgs[0].get("role") == "system":
        msgs[0] = dict(msgs[0], content=msgs[0]["content"] + "\n只输出 JSON，不要包含任何额外文字或 markdown。")
    else:
        msgs = [{"role": "system", "content": "只输出 JSON。"}] + msgs
    content = chat(msgs, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    return _safe_json(content)


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    tool_choice: str = "auto",
    temperature: float = 0.3,
    max_tokens: int = 1200,
    timeout: Optional[int] = None,
):
    """带 function calling 的对话。返回 OpenAI message 对象（可能含 tool_calls）。"""
    client = get_client()
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout or config.LLM_TIMEOUT_S,
    )
    return resp.choices[0].message


def _safe_json(content: str) -> dict:
    if not content:
        return {}
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lstrip().lower().startswith("json"):
            content = content.lstrip()[4:]
    try:
        return __import__("json").loads(content)
    except Exception:
        pass
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        return __import__("json").loads(content[start:end])
    except Exception:
        return {}

# -*- coding: utf-8 -*-
"""
Agent Demo 的工具集（被 function calling 调度）。
每个工具都是纯本地能力，保证离线可跑、可解释。
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "common"))

from retrieval import Retriever, load_docs

KB_DIR = os.path.join(_HERE, "..", "kb")
_retriever = Retriever(load_docs(KB_DIR))


# —— 工具 1：知识检索 ——
def knowledge_search(query: str, k: int = 3) -> str:
    hits = _retriever.search(query, k=k)
    if not hits:
        return "未检索到相关内容。"
    return "\n\n".join(
        f"[来源：{h.source}]\n{h.text}" for h in hits
    )


# —— 工具 2：安全计算 ——
def calc(expression: str) -> str:
    allowed = set("0123456789.+-*/() ")
    if not expression or any(c not in allowed for c in expression):
        return "表达式含非法字符，仅支持数字与 + - * / () 。"
    try:
        return f"{expression} = {eval(expression, {'__builtins__': {}}, {})}"
    except Exception as e:
        return f"计算失败：{e}"


# —— 给大模型的工具声明（OpenAI function calling 格式）——
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": "在面试/FDE 知识库中检索相关片段，用于回答知识类问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索问题"},
                    "k": {"type": "integer", "description": "返回条数，默认 3"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "安全计算四则运算表达式，仅支持数字与 + - * / 和括号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "如 '(12+8)*3'"},
                },
                "required": ["expression"],
            },
        },
    },
]


def dispatch(name: str, args: dict) -> str:
    """按工具名执行，返回结果字符串。"""
    if name == "knowledge_search":
        return knowledge_search(str(args.get("query", "")), int(args.get("k", 3)))
    if name == "calc":
        return calc(str(args.get("expression", "")))
    return f"未知工具：{name}"

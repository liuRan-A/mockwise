# -*- coding: utf-8 -*-
"""
MCP Demo 服务端：用官方 mcp SDK 暴露工具（知识检索 / 计算 / 面试技巧）。
这就是标准的 Model Context Protocol —— 服务端把能力注册为 tool，由任意兼容客户端按协议调用。
运行：python server.py   （作为子进程由 client.py 拉起，无需手动启动）
"""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "common"))

from mcp.server.fastmcp import FastMCP
from retrieval import Retriever, load_docs

KB_DIR = os.path.join(_HERE, "..", "kb")
_retriever = Retriever(load_docs(KB_DIR))

mcp = FastMCP("mockwise-kb")


@mcp.tool()
def search_knowledge(query: str, k: int = 3) -> str:
    """在面试/FDE 知识库中检索相关片段，返回 top-k 文本与出处。"""
    hits = _retriever.search(query, k=k)
    if not hits:
        return "未检索到相关内容。"
    return "\n\n".join(
        f"[来源：{h.source} 相似度：{h.score:.2f}]\n{h.text}" for h in hits
    )


@mcp.tool()
def calc(expression: str) -> str:
    """安全计算四则运算表达式（仅支持数字与 + - * / 和括号）。"""
    allowed = set("0123456789.+-*/() ")
    if not expression or any(c not in allowed for c in expression):
        return "表达式含非法字符，仅支持数字与 + - * / () 。"
    try:
        val = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {val}"
    except Exception as e:
        return f"计算失败：{e}"


@mcp.tool()
def interview_tip(topic: str) -> str:
    """根据主题返回面试技巧要点（基于知识库检索）。"""
    return search_knowledge(f"{topic} 面试技巧", k=2)


if __name__ == "__main__":
    mcp.run()

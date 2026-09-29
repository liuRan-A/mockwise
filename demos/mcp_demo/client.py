# -*- coding: utf-8 -*-
"""
MCP Demo 客户端：通过 stdio 启动服务端，按 MCP 协议 列出工具 -> 调用工具。
这证明大模型/应用可以「按统一协议」接入任意工具，无需为每个工具单独对接。

运行（在项目根 ai模拟作业/ 下，用已装 mcp 的 Python）：
    python demos/mcp_demo/client.py
"""
from __future__ import annotations
import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "common"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER = os.path.join(_HERE, "server.py")


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== MCP 服务端暴露的工具 ===")
            for t in tools.tools:
                print(f"- {t.name}：{t.description}")

            # 调用示例 1：知识检索
            r1 = await session.call_tool(
                "search_knowledge", {"query": "FDE 岗位核心职责", "k": 2}
            )
            print("\n=== 调用 search_knowledge('FDE 岗位核心职责') ===")
            print(_text(r1))

            # 调用示例 2：计算
            r2 = await session.call_tool("calc", {"expression": "(12 + 8) * 3"})
            print("\n=== 调用 calc('(12 + 8) * 3') ===")
            print(_text(r2))


def _text(result) -> str:
    if not result.content:
        return ""
    return "\n".join(
        b.text for b in result.content if getattr(b, "type", "") == "text"
    )


if __name__ == "__main__":
    asyncio.run(main())

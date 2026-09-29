# -*- coding: utf-8 -*-
"""
Agent Demo：工具调用型自主代理（ReAct 思路）
给定目标，模型自主决定调用哪些工具、按什么顺序，循环执行直到得出最终答案。
这展示「Agent 任务拆解与工作流编排」：模型 = 大脑，工具 = 手脚。

运行（项目根 ai模拟作业/ 下，需配置 DEEPSEEK_API_KEY）：
    python demos/agent_demo/main.py
"""
from __future__ import annotations
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "common"))

import config
from llm import chat_with_tools
from tools import TOOL_SCHEMAS, dispatch


SYSTEM = (
    "你是一个任务求解 Agent。对于用户目标，先思考需要哪些步骤，"
    "必要时调用工具获取信息或计算结果，再综合给出最终答案。"
    "每次只调用当前最需要的工具，最多调用 5 次。"
)

DEFAULT_GOAL = (
    "帮我准备 FDE 岗位面试：1) 这个岗位核心看什么能力；"
    "2) 我有一段持续 4 个月的门店接管经历，换算成天数是多少；"
    "3) 给我一条『岗位匹配』类问题的答题框架。"
)


def run(goal: str, max_steps: int = 5) -> None:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": goal},
    ]
    print(f"目标：{goal}\n")

    for step in range(1, max_steps + 1):
        msg = chat_with_tools(messages, TOOL_SCHEMAS)

        # 模型没有再要工具 -> 这是最终答案
        if not msg.tool_calls:
            print(f"[第 {step} 步] 模型给出最终答案：\n{msg.content}")
            return

        # 模型要求调用工具
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})
        print(f"[第 {step} 步] 模型决定调用 {len(msg.tool_calls)} 个工具：")
        for call in msg.tool_calls:
            fn = call.function
            args = json.loads(fn.arguments or "{}")
            print(f"   → {fn.name}({args})")
            result = dispatch(fn.name, args)
            print(f"     工具返回：{result[:120]}{'...' if len(result) > 120 else ''}")
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    print("（已达到最大步数，停止循环）")


def main() -> None:
    if not config.has_key():
        print("[中止] 未配置 DEEPSEEK_API_KEY，无法运行 Agent。请先在 backend/.env 填写密钥。")
        return
    goal = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GOAL
    run(goal)


if __name__ == "__main__":
    main()

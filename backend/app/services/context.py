# -*- coding: utf-8 -*-
"""
上下文构建器（对应标准③：上下文工程）。

解决「每次把整份简历 / 整个知识库一股脑塞进 prompt」的问题：
- 把上下文拆成有层级的「片段」（系统 / 任务 / 用户记忆 / 知识 / 工具 / 历史）；
- 每个片段带有优先级；在给定 token 预算内，**优先保留高优先级片段**，
  超出预算的低优先级片段被裁剪（让模型只读取需要的信息）；
- 相同 key 的片段去重；
- assemble() 返回 {system, user, meta}，meta 含各层是否纳入、估算 token，
  直接喂给 P4 可观测性做量化。

纯标准库实现，可在无 fastapi/sqlalchemy 的沙箱中 self-test（python -m app.services.context）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ContextLayer(str, Enum):
    SYSTEM = "system"          # 角色 / 评测规则（通常由 system 段承载）
    TASK = "task"              # 本次任务：题目 + 候选人作答
    USER_MEMORY = "user_memory"  # 候选人长期记忆（按需召回）
    KNOWLEDGE = "knowledge"    # 知识库片段（仅本题参考答案）
    TOOL = "tool"              # 工具返回结果
    HISTORY = "history"        # 历史对话 / 过往轮次


# 优先级 >= 此值的片段被视为「必需」，即使超出预算也保留（如 TASK 承载候选人作答）。
# 预算只用于裁剪【可选】上下文（知识/记忆/历史），实现「模型只读取需要的信息」。
MANDATORY_PRIORITY = 9


def estimate_tokens(text: str) -> int:
    """混合中英文的 token 估算（非精确，用于预算裁剪足够）。
    经验：CJK 字符约 1 token/字；其它字符约 4 字 1 token。"""
    if not text:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    non_cjk = len(text) - cjk
    return cjk + max(0, round(non_cjk / 4))


@dataclass
class ContextPiece:
    content: str
    layer: ContextLayer
    priority: int = 5          # 数值越大越优先保留（10=必须，1=可丢弃）
    key: Optional[str] = None  # 去重键；相同 key 只保留第一个


class ContextBuilder:
    """
    分层上下文装配器。

    用法：
        b = ContextBuilder(max_tokens=1500, system_prompt=SYS)
        b.add(题目+作答, ContextLayer.TASK, priority=9)
        b.add(知识片段, ContextLayer.KNOWLEDGE, priority=7)
        b.add(用户记忆, ContextLayer.USER_MEMORY, priority=6)
        ctx = b.assemble()   # {"system","user","meta"}
    """

    def __init__(self, max_tokens: int = 1500, system_prompt: str = ""):
        self.max_tokens = max(0, int(max_tokens))
        self.system_prompt = system_prompt or ""
        self._pieces: list[ContextPiece] = []

    def add(self, content, layer: ContextLayer, *, priority: int = 5,
            key: Optional[str] = None) -> "ContextBuilder":
        """追加一个片段；空内容会被忽略。返回 self 以便链式。"""
        if content is None:
            return self
        s = str(content).strip()
        if not s:
            return self
        self._pieces.append(ContextPiece(s, layer, int(priority), key))
        return self

    def assemble(self) -> dict:
        sys_tokens = estimate_tokens(self.system_prompt)
        budget = max(0, self.max_tokens - sys_tokens)

        # 先按优先级降序、再保持加入顺序（插入序稳定）
        ordered = sorted(enumerate(self._pieces), key=lambda t: -t[1].priority)

        included: list[ContextPiece] = []
        dropped_layers: list[str] = []
        seen_keys: set[str] = set()
        used = 0
        over_budget = False

        for _idx, p in ordered:
            if p.key and p.key in seen_keys:
                dropped_layers.append(p.layer.value)   # 去重视为丢弃
                continue
            t = estimate_tokens(p.content)
            mandatory = p.priority >= MANDATORY_PRIORITY
            if used + t <= budget or mandatory:
                # 必需片段超预算也保留（保证任务上下文不丢）；否则只在有预算时纳入
                included.append(p)
                used += t
                if p.key:
                    seen_keys.add(p.key)
                if used > budget:
                    over_budget = True
            else:
                dropped_layers.append(p.layer.value)

        # 输出时按优先级降序，同优先级保持插入序（还原可读结构）
        included.sort(key=lambda p: -p.priority)

        return {
            "system": self.system_prompt,
            "user": "\n\n".join(p.content for p in included),
            "meta": {
                "system_tokens": sys_tokens,
                "context_tokens": used,
                "total_tokens": sys_tokens + used,
                "max_tokens": self.max_tokens,
                "over_budget": over_budget,
                "included_layers": sorted({p.layer.value for p in included}),
                "dropped_layers": sorted(set(dropped_layers)),
            },
        }


if __name__ == "__main__":
    # —— 沙箱自测（无外部依赖） ——
    SYS = "评委" * 10  # 很短，约 20 token，避免占满预算
    # 场景 A：预算充足，TASK/知识/记忆都应纳入，只有低优先级历史被裁剪
    b = ContextBuilder(max_tokens=600, system_prompt=SYS)
    b.add("【任务】题目：xxx\n作答原文：" + ("候选人回答内容。" * 30),
          ContextLayer.TASK, priority=9, key="task")
    b.add("【知识】本题采分点：A；常见失分点：B。",
          ContextLayer.KNOWLEDGE, priority=7, key="know")
    b.add("【记忆】候选人在「逻辑结构」历史偏弱。",
          ContextLayer.USER_MEMORY, priority=6, key="mem")
    b.add("【历史】很久以前的一段长上下文。" * 200,
          ContextLayer.HISTORY, priority=3, key="hist")
    b.add("【记忆】重复内容", ContextLayer.USER_MEMORY, priority=6, key="mem")  # 去重

    ctx = b.assemble()
    print("A total_tokens=", ctx["meta"]["total_tokens"], "max=", ctx["meta"]["max_tokens"])
    print("A included=", ctx["meta"]["included_layers"], "dropped=", ctx["meta"]["dropped_layers"])
    assert "task" in ctx["meta"]["included_layers"], "必需 TASK 必须保留"
    assert "knowledge" in ctx["meta"]["included_layers"], "有预算时知识应注入"
    assert "user_memory" in ctx["meta"]["included_layers"], "有预算时记忆应注入"
    assert "history" in ctx["meta"]["dropped_layers"], "低优先级历史应被裁剪"
    assert "偏弱" in ctx["user"] and "重复内容" not in ctx["user"], "去重失败：重复 key 不应出现"

    # 场景 B：预算极小，TASK(必需) 超预算也保留，其余全部被裁剪
    b2 = ContextBuilder(max_tokens=10, system_prompt=SYS)
    b2.add("x" * 100, ContextLayer.TASK, priority=9, key="task")
    b2.add("【知识】y", ContextLayer.KNOWLEDGE, priority=7, key="know")
    c2 = b2.assemble()
    print("B included=", c2["meta"]["included_layers"], "over_budget=", c2["meta"]["over_budget"])
    assert "task" in c2["meta"]["included_layers"]
    assert "knowledge" in c2["meta"]["dropped_layers"], "超预算时可选知识应被裁剪"
    assert c2["meta"]["over_budget"] is True

    print("CONTEXT_SELFTEST_OK")

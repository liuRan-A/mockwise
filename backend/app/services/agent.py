# -*- coding: utf-8 -*-
"""
轻量 Agent 编排层（框架无关）

对应标准②：Agent 核心能力 —— 任务拆解 / 步骤规划 / 失败重试 / 结果校验 / 多步协同。
不引入 langchain / autogen / crewai 等框架，保持后端可控、可观测、可测试。

核心概念：
- AgentContext：跨步骤共享的可变状态容器（继承 dict），步骤之间传递中间产物；
- AgentStep：单个可重试步骤，含「执行 + 校验 + 重试次数 + 退避 + 失败策略 + 兜底」；
- Plan：把若干步骤编排成计划，按顺序执行；某步失败按 on_fail 决定「继续 / 抛错」，
  并优先执行该步的 fallback（兜底）保证整体不中断（与 MockWise 既有的降级哲学一致）。

多智能体协作：本层是「单计划多步骤」的最小引擎；标准⑤要求的「多 Agent 按需协作」在
services/group_agent.py 中基于本引擎派生（每个虚拟候选人 = 一个 AgentStep / 子 Agent），
不盲目堆多智能体。
"""
from __future__ import annotations

import time
import logging
from typing import Any, Callable, Optional

from app.core.logging_config import get_logger

log = get_logger("agent")


class AgentError(Exception):
    """编排层通用错误。"""


class ValidationFailed(AgentError):
    """步骤产出未通过校验。"""


class StepResult:
    """单步执行结果。"""

    def __init__(self, name: str, ok: bool, data: Any, attempts: int,
                 error: Optional[str], duration_ms: int, fallback_used: bool = False):
        self.name = name
        self.ok = ok
        self.data = data
        self.attempts = attempts
        self.error = error
        self.duration_ms = duration_ms
        self.fallback_used = fallback_used

    def __repr__(self) -> str:
        return (f"<Step {self.name} ok={self.ok} attempts={self.attempts} "
                f"fb={self.fallback_used} ms={self.duration_ms}>")


class AgentContext(dict):
    """跨步骤共享状态。用法同 dict，额外可在步骤间挂载中间结果。"""


class AgentStep:
    """一个可重试、可校验的步骤。

    run(ctx) -> 产出（任意可校验对象）；
    validate(data) -> bool（可选）；
    on_fail: "continue"（默认，失败也继续后续步骤）| "raise"（失败即中断计划）；
    fallback(ctx) -> data（重试耗尽后的兜底，优先级高于 on_fail 中断）。
    """

    def __init__(self, name: str, run: Callable[[AgentContext], Any], *,
                 validate: Optional[Callable[[Any], bool]] = None,
                 max_retries: int = 2, backoff_s: float = 0.3,
                 on_fail: str = "continue", fallback: Optional[Callable[[AgentContext], Any]] = None,
                 description: str = ""):
        self.name = name
        self.run = run
        self.validate = validate
        self.max_retries = max(1, int(max_retries))
        self.backoff_s = backoff_s
        self.on_fail = on_fail
        self.fallback = fallback
        self.description = description


class PlanResult:
    def __init__(self, name: str, results: list[StepResult], ctx: AgentContext):
        self.name = name
        self.results = results
        self.ctx = ctx

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def get(self, step_name: str) -> Any:
        for r in self.results:
            if r.name == step_name:
                return r.data
        return None

    def summary(self) -> dict:
        return {
            "plan": self.name,
            "ok": self.ok,
            "steps": [
                {"name": r.name, "ok": r.ok, "attempts": r.attempts,
                 "fallback_used": r.fallback_used, "ms": r.duration_ms,
                 "error": r.error}
                for r in self.results
            ],
        }


def _execute_step(step: AgentStep, ctx: AgentContext) -> StepResult:
    """执行单步：重试 max_retries 次，每次都做校验；耗尽后尝试 fallback。"""
    last_err: Optional[str] = None
    for attempt in range(1, step.max_retries + 1):
        t0 = time.time()
        try:
            data = step.run(ctx)
            if step.validate is not None and not step.validate(data):
                raise ValidationFailed(f"step '{step.name}' 校验未通过 (attempt {attempt})")
            return StepResult(step.name, True, data, attempt, None,
                              int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001 - 记录后按策略处理
            last_err = str(e)
            log.warning("[agent] step '%s' attempt %d 失败: %s", step.name, attempt, e)
            if attempt < step.max_retries:
                time.sleep(step.backoff_s)
    # 重试耗尽
    if step.fallback is not None:
        try:
            t0 = time.time()
            data = step.fallback(ctx)
            return StepResult(step.name, True, data, step.max_retries, None,
                              int((time.time() - t0) * 1000), fallback_used=True)
        except Exception as e2:  # noqa: BLE001
            log.error("[agent] step '%s' 兜底也失败: %s", step.name, e2)
            return StepResult(step.name, False, None, step.max_retries, str(e2), 0)
    return StepResult(step.name, False, None, step.max_retries,
                      last_err or "unknown", 0)


class Plan:
    """顺序执行一组步骤；支持 on_fail=raise 中断、步骤兜底。"""

    def __init__(self, name: str, steps: list[AgentStep], ctx: Optional[AgentContext] = None):
        self.name = name
        self.steps = steps
        self.ctx = ctx or AgentContext()

    def run(self) -> PlanResult:
        results: list[StepResult] = []
        for step in self.steps:
            r = _execute_step(step, self.ctx)
            results.append(r)
            log.info("[agent] plan '%s' step '%s' -> %s", self.name, step.name, r)
            if not r.ok and step.on_fail == "raise":
                raise AgentError(f"step '{step.name}' 失败: {r.error}")
        return PlanResult(self.name, results, self.ctx)


def run_plan(name: str, steps: list[AgentStep], ctx: Optional[AgentContext] = None) -> PlanResult:
    """便捷入口：构建并执行一个计划。"""
    return Plan(name, steps, ctx).run()


if __name__ == "__main__":
    # —— 自测：验证「先失败后成功」「校验失败走兜底」——
    calls = {"a": 0}

    def flaky(ctx):
        calls["a"] += 1
        if calls["a"] < 2:
            raise RuntimeError("boom")
        return {"x": calls["a"]}

    def always_bad(ctx):
        return {"x": -1}

    def validator(d):
        return d.get("x", 0) > 0

    def fallback(ctx):
        return {"x": 0, "fallback": True}

    plan = Plan("test", [
        AgentStep("flaky", flaky, max_retries=3, backoff_s=0.01),
        AgentStep("bad-with-fallback", always_bad, validate=validator,
                  max_retries=2, backoff_s=0.01, fallback=fallback),
        AgentStep("ok", lambda c: {"y": 1}, on_fail="raise"),
    ])
    res = plan.run()
    print("plan.ok =", res.ok)
    for r in res.results:
        print(" ", r)
    assert res.results[0].ok and res.results[0].attempts == 2, "flaky 应第2次成功"
    assert res.results[1].ok and res.results[1].fallback_used, "bad 应走兜底"
    assert res.results[2].ok
    print("AGENT_SELFTEST_OK")

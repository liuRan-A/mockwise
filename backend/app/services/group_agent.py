# -*- coding: utf-8 -*-
"""
群面多智能体编排（对应标准②：多 Agent 协作按需使用；直接修复「AI 互怼不流畅」）

现状问题（见 ENGINEERING_ROADMAP 审计）：原群面 AI 轮次 `crud.peer.generate_peer_talk`
是**纯模板拼接**，候选人从预写话术里 .format() 抽一句，既没有真实 LLM、也没有统一编排，
导致「各说各话、缺乏来回、不衔接上下文」。

本模块提供后端编排层：
- PeerAgent：把一个人设（PeerPersona）包装成一个子 Agent，携带其风格/简介/抢话倾向；
- GroupOrchestrator：管理「开场陈述 → 自由讨论 → 总结陈词」三阶段与轮次调度，
  为每位发言者构建「系统提示 + 任务提示 + 最近上下文窗口」；
- 每次轮次通过 services.llm_client.structured 生成，并用 PeerTurn(Pydantic v1) 做
  schema 校验 + 校验失败重试（validate-retry），要求输出 content/intent/cites，
  其中 cites 强制引用场上其他候选人姓名 → 形成真正的「来回」；
- LLM 不可用 / 校验重试耗尽时，自动降级到原模板 generate_peer_talk（保持业务不中断）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.logging_config import get_logger
from app.services.llm_client import structured

log = get_logger("group_agent")

# pydantic 可能为 v1（项目锁定 1.10.13）。此处兼容导入，导入失败仅影响 schema 强校验，
# 运行时 structured() 会退化为字段清单校验 + 模板兜底。
try:
    from pydantic import BaseModel, validator  # type: ignore

    _HAVE_PYDANTIC = True
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore
    validator = lambda *a, **k: lambda f: f  # type: ignore
    _HAVE_PYDANTIC = False


class PeerTurn(BaseModel):  # type: ignore[valid-type]
    """一次群面发言的强约束结构（用于 LLM 输出校验）。"""
    content: str
    intent: str
    cites: list[str] = []

    @validator("content")  # type: ignore[attr-defined]
    def _content_min(cls, v):  # noqa: N805
        s = (v or "").strip()
        if len(s) < 15:
            raise ValueError("发言过短，需 >= 15 字")
        return s

    @validator("intent")  # type: ignore[attr-defined]
    def _intent_in(cls, v):  # noqa: N805
        allowed = {"立论", "反驳", "补充", "总结", "追问"}
        if (v or "").strip() not in allowed:
            return "立论"
        return v.strip()


# 阶段中文标签
_PHASE_LABELS = {"opening": "开场陈述", "debate": "自由讨论", "summary": "总结陈词"}
_PHASE_ORDER = ["opening", "debate", "summary"]


class PeerAgent:
    """一个虚拟候选人子 Agent。"""

    def __init__(self, persona, member_names: list[str]):
        self.persona = persona
        self.name = getattr(persona, "name", "候选人")
        self.style = getattr(persona, "style", "稳健理性")
        self.color = getattr(persona, "color", "#4f7cff")
        self.bio = getattr(persona, "bio", "") or ""
        self.aggressiveness = getattr(persona, "aggressiveness", 0) or 0
        self.member_names = list(member_names)
        self.turns = 0

    def system_prompt(self, phase_label: str, topic: str, stance: str) -> str:
        return (
            f"你是无领导小组讨论中的一名虚拟候选人。\n"
            f"姓名：{self.name}\n"
            f"人设风格：{self.style or '稳健理性'}\n"
            f"人物简介：{self.bio or '一位有想法的面试候选人'}\n"
            f"本轮阶段：{phase_label}\n"
            f"讨论主题：{topic or '面试官给定议题'}\n"
            f"你的立场/论点：{stance or '（按你对议题的理解发表看法）'}\n"
            "发言要求：\n"
            "1. 像真实候选人在面试现场自然说出来，口语化、有观点、有逻辑，80-200字；\n"
            "2. 必须紧扣主题，不跑题、不喊口号；\n"
            "3. 若场上已有他人观点，用 cites 引用对方姓名进行呼应或反驳，形成「来回」，不要各说各话；\n"
            "4. 严禁复述本提示，只输出要求的 JSON。\n"
            '输出 JSON：{"content":"你的发言正文","intent":"立论/反驳/补充/总结/追问","cites":["你回应或引用的其他候选人姓名，无则[]"]}'
        )


class GroupOrchestrator:
    """群面讨论编排器：阶段 + 轮次 + 上下文构建 + 引用校验。"""

    def __init__(self, member_names: list[str], topic: str = ""):
        self.member_names = list(member_names)
        self.topic = topic
        self.phase = "opening"
        self.round = 0

    def advance(self) -> None:
        if self.phase in _PHASE_ORDER:
            i = _PHASE_ORDER.index(self.phase)
            if i < len(_PHASE_ORDER) - 1:
                self.phase = _PHASE_ORDER[i + 1]

    def next_speaker(self, agents: list[PeerAgent]) -> Optional[PeerAgent]:
        if not agents:
            return None
        if self.phase == "debate":
            return sorted(agents, key=lambda a: -a.aggressiveness)[self.round % len(agents)]
        return agents[self.round % len(agents)]

    @staticmethod
    def _history_text(recent: list[dict]) -> str:
        if not recent:
            return ""
        items = []
        for m in recent[-6:]:
            who = m.get("who")
            name = m.get("name") or ("你" if who == "me" else "对方")
            text = (m.get("text") or "").strip().replace("\n", " ")
            if text:
                items.append(f"【{name}】{text[:120]}")
        return "\n".join(reversed(items))

    def generate_turn(self, agent: PeerAgent, *, phase: str, topic: str,
                      stance: str = "", recent_context: Optional[list[dict]] = None,
                      respond_to: str = "me", target_name: str = "",
                      user_text: str = "", other_name: str = "",
                      candidate_brief: str = "") -> dict:
        """生成一条发言：优先 LLM（校验后），失败降级模板。返回 {content, intent, cites, engine}。"""
        phase = phase if phase in _PHASE_LABELS else "debate"
        phase_label = _PHASE_LABELS[phase]
        sys_p = agent.system_prompt(phase_label, topic, stance)
        hist = self._history_text(recent_context or [])
        if respond_to and respond_to not in ("me", "你", "", "user"):
            who = f"另一位候选人「{respond_to}」"
        else:
            who = "真人候选人（你）"
        usr_p = (
            f"当前阶段：{phase_label}\n"
            f"本次你主要回应：{who}\n"
        )
        # 上下文工程：把真人候选人的长期薄弱点注入，让 AI 群面「有针对性」地追问/反驳
        if candidate_brief:
            usr_p += (
                f"【真人候选人背景提示（仅你可见，用于更有针对性地交锋）】\n{candidate_brief}\n"
            )
        usr_p += (
            f"最近讨论记录（倒序，可能为空）：\n{hist or '（暂无，请直接立论）'}\n"
            "请生成你这一轮的自然发言，并严格只输出 JSON。"
        )
        try:
            from app.services.tracing import scene
            with scene("group_turn"):
                data = structured(sys_p, usr_p, PeerTurn,
                                  temperature=0.6, max_tokens=320, max_struct_retries=2)
            cites = [c for c in (data.get("cites") or []) if c in self.member_names]
            return {
                "content": (data.get("content") or "").strip(),
                "intent": data.get("intent") or phase,
                "cites": cites,
                "engine": "llm",
            }
        except Exception as e:  # noqa: BLE001 - 任何失败都降级，不中断群面
            log.warning("[group_agent] LLM 生成失败，降级模板: %s", e)
            from app.crud.peer import generate_peer_talk
            text = generate_peer_talk(
                stage=phase, persona=agent.persona, stance=stance, topic=topic,
                target_name=target_name, user_text=user_text or "",
                other_name=other_name or "",
                recent_context=recent_context or [], respond_to=respond_to or "me",
            )
            return {"content": text, "intent": phase, "cites": [], "engine": "template"}


def generate_group_turn(*, persona, stage: str, topic: str = "", stance: str = "",
                        target_name: str = "", other_name: str = "",
                        user_text: str = "", recent_context: Optional[list[dict]] = None,
                        respond_to: str = "me", member_names: Optional[list[str]] = None,
                        candidate_brief: str = "") -> dict:
    """便捷入口：为单个虚拟候选人生成一轮发言。供 sessions.peer_talk 调用。"""
    member_names = list(member_names or [])
    agent = PeerAgent(persona, member_names)
    orch = GroupOrchestrator(member_names=member_names, topic=topic)
    return orch.generate_turn(
        agent, phase=stage, topic=topic, stance=stance,
        recent_context=recent_context or [], respond_to=respond_to or "me",
        target_name=target_name, user_text=user_text, other_name=other_name,
        candidate_brief=candidate_brief,
    )

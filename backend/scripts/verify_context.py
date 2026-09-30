# -*- coding: utf-8 -*-
"""
Phase 3（上下文工程）量化验证脚本 —— 对应标准③「让模型只读取需要的信息」。

用可复核的数字证明三件事：
  A. 上下文分层预算生效：预算内保留高优先级、裁剪低优先级；必需层不丢。
  B. 按需注入 vs 全量注入的 token 对比：给出节省比例（这是「只读取需要的信息」的直接证据）。
  C. 用户记忆闭环：多场得分累积 → 按需只召回「与当前维度相关」的片段。
  D. 知识片段按需检索：只抽本题采分点，绝不把全库塞进 prompt。

运行：cd backend && python scripts/verify_context.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证可以直接 `python scripts/verify_context.py` 运行（把 backend/ 加入 sys.path）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.context import ContextBuilder, ContextLayer, estimate_tokens  # noqa: E402
from app.services.knowledge import get_question_knowledge  # noqa: E402

OK = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    tag = OK if cond else FAIL
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        _failures.append(name)


def _sep(title: str) -> None:
    print(f"\n{'=' * 62}\n{title}\n{'=' * 62}")


# ---------------------------------------------------------------- A. 预算裁剪
def test_budget() -> None:
    _sep("A. 上下文分层预算（高优先级保留 / 低优先级裁剪）")
    SYS = "你是一名资深面试评委。" * 8
    b = ContextBuilder(max_tokens=700, system_prompt=SYS)
    b.add("【题目】请讲讲线上服务大量超时的排查思路。\n【作答】" + "我先止血再定位根因。" * 40,
          ContextLayer.TASK, priority=9, key="task")
    b.add("【知识】本题采分点：先止血；评估影响面；复盘沉淀。", ContextLayer.KNOWLEDGE, priority=7, key="know")
    b.add("【记忆】候选人在「逻辑结构」历史偏弱（均分 61）。", ContextLayer.USER_MEMORY, priority=6, key="mem")
    b.add("【历史】很久以前的冗长历史记录。" * 300, ContextLayer.HISTORY, priority=3, key="hist")
    ctx = b.assemble()
    m = ctx["meta"]
    print(f"  预算 max={m['max_tokens']}  实际 total={m['total_tokens']}  over_budget={m['over_budget']}")
    print(f"  纳入层: {m['included_layers']}")
    print(f"  裁剪层: {m['dropped_layers']}")
    check("必需层 TASK 一定保留", "task" in m["included_layers"])
    check("有预算时 KNOWLEDGE 注入", "knowledge" in m["included_layers"])
    check("有预算时 USER_MEMORY 注入", "user_memory" in m["included_layers"])
    check("低优先级 HISTORY 被裁剪", "history" in m["dropped_layers"])

    # 极小预算：必需层仍在，可选层被裁
    b2 = ContextBuilder(max_tokens=10, system_prompt=SYS)
    b2.add("x" * 200, ContextLayer.TASK, priority=9, key="task")
    b2.add("【知识】y", ContextLayer.KNOWLEDGE, priority=7, key="know")
    c2 = b2.assemble()
    check("极小预算时 TASK 仍保留（任务上下文不丢）", "task" in c2["meta"]["included_layers"])
    check("极小预算时可选知识被裁剪", "knowledge" in c2["meta"]["dropped_layers"])
    check("超预算被如实标记（供 P4 观测）", c2["meta"]["over_budget"] is True)


# ------------------------------------------------- B. 按需注入 vs 全量注入
def test_token_saving() -> None:
    _sep("B. 按需注入 vs 全量注入：token 对比（只读取需要的信息）")

    resume_full = (
        "候选人简历全文：姓名李某，5 年后端经验，熟悉 Python/Go/MySQL/Redis/Kafka，"
        "主导过订单系统重构、风控规则引擎、埋点数据平台三个项目，"
        "其中订单重构将 P99 从 800ms 降到 220ms，风控引擎日均处理 3000 万次请求，"
        "数据平台支撑 200+ 报表。曾负责团队 8 人，主导技术方案评审与排期。\n"
    ) * 3  # 真实简历更长，这里模拟「每次把整份简历塞进去」
    all_ref_answers = "\n".join(
        f"第{i + 1}题参考答案要点：{'内容要点内容要点' * 12}" for i in range(10)
    )  # 模拟「把整个题库参考答案全塞进去」
    task = "【题目】线上服务突然大量超时，你怎么处理？\n【作答】" + "我先降级止血，再看监控定位根因，最后复盘。" * 20

    # 全量注入（改造前的做法）
    naive_user = f"{resume_full}\n【全量题库参考答案】{all_ref_answers}\n{task}"
    naive_tokens = estimate_tokens(naive_user)

    # 按需注入（本次改造后）
    know = get_question_knowledge(
        ref_detail={"key_points": ["先止血控制影响面", "评估影响范围与优先级", "复盘沉淀机制"],
                    "common_traps": ["一上来就找根因忽略止血"]},
        ref_answer=None,
    )
    memory = "候选人在「应急应变」历史多次得分偏低（均分约 62），请重点考察。"
    b = ContextBuilder(max_tokens=3200, system_prompt=_SCORE_SYS_LITE)
    b.add(task, ContextLayer.TASK, priority=9, key="task")
    b.add(know or "", ContextLayer.KNOWLEDGE, priority=7, key="know")
    b.add(memory, ContextLayer.USER_MEMORY, priority=6, key="mem")
    ctx = b.assemble()
    smart_tokens = ctx["meta"]["total_tokens"]

    saved = naive_tokens - smart_tokens
    pct = (saved / naive_tokens * 100) if naive_tokens else 0.0
    print(f"  全量注入（简历全文 + 全库参考）: {naive_tokens} tokens")
    print(f"  按需注入（本题知识 + 相关记忆）: {smart_tokens} tokens")
    print(f"  节省: {saved} tokens（{pct:.1f}%）")
    check(f"按需注入显著更省（节省 {pct:.1f}% ≥ 30%）", pct >= 30.0, f"{naive_tokens} → {smart_tokens}")
    check("按需注入仍包含任务上下文", "【题目】" in ctx["user"])
    check("按需注入包含本题知识片段", "采分点" in ctx["user"])
    check("按需注入包含相关记忆", "应急应变" in ctx["user"])
    check("按需注入不含整份简历全文", "订单系统重构" not in ctx["user"])
    check("按需注入不含全库参考答案", "第10题参考答案要点" not in ctx["user"])


_SCORE_SYS_LITE = "你是一名资深面试评委，请严格输出 JSON 评分。"


# ------------------------------------------------------------ C. 记忆闭环
def test_memory_roundtrip() -> None:
    _sep("C. 用户记忆闭环：多场累积 → 按需只召回相关片段")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.models.memory import CandidateMemory  # noqa: F401  确保表注册
    from app.crud.memory import update_from_session, retrieve_relevant

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine, tables=[CandidateMemory.__table__])
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    uid = 1001
    check("无记忆时不召回（不污染上下文）", retrieve_relevant(db, uid, dimension="逻辑结构") is None)

    # 第 1 场：逻辑结构 58（弱）、应急应变 85（强）
    update_from_session(db, uid, [
        {"name": "逻辑结构", "score": 58, "comment": "结构松散"},
        {"name": "应急应变", "score": 85, "comment": "处置得当"},
    ], form_type="structured")
    # 第 2 场：逻辑结构 62（仍弱）
    update_from_session(db, uid, [
        {"name": "逻辑结构", "score": 62, "comment": "有改进"},
    ], form_type="structured")
    db.commit()

    mem_logic = retrieve_relevant(db, uid, dimension="逻辑结构")
    print(f"  召回（维度=逻辑结构）: {mem_logic}")
    check("命中维度时优先点名该维度", bool(mem_logic) and "逻辑结构" in mem_logic)
    check("并给出历史均分供评委参考", bool(mem_logic) and "均分" in mem_logic)

    mem_emerg = retrieve_relevant(db, uid, dimension="应急应变")
    print(f"  召回（维度=应急应变）: {mem_emerg}")
    check("优势维度同样能被点名（提高考察深度）", bool(mem_emerg) and "应急应变" in mem_emerg)

    # 关键：按需 = 只给相关的那一条，不把全部记忆倒出来
    check("只召回相关维度，不输出无关维度",
          bool(mem_logic) and "应急应变" not in mem_logic)
    check("召回片段长度受控（<=240 字）", bool(mem_logic) and len(mem_logic) <= 240, f"len={len(mem_logic or '')}")

    db.close()


# ------------------------------------------------------------ D. 知识片段
def test_knowledge() -> None:
    _sep("D. 知识片段：只抽本题采分点（RAG-lite）")
    k1 = get_question_knowledge(
        ref_detail={"key_points": ["紧扣题目给结论", "用数据支撑"], "common_traps": ["空泛无细节"]},
        ref_answer=None,
    )
    print(f"  抽取结果: {k1}")
    check("结构化参考 → 抽出采分点 + 失分点", bool(k1) and "采分点" in k1 and "失分点" in k1)

    k2 = get_question_knowledge(ref_detail=None, ref_answer="参考答案要点：先界定问题边界。")
    check("无结构化参考时退化为要点", bool(k2) and "参考答案要点" in k2)

    k3 = get_question_knowledge(ref_detail=None, ref_answer=None)
    check("无参考时返回 None（不注入空上下文）", k3 is None)

    long_kp = ["采分点内容" * 30 for _ in range(10)]
    k4 = get_question_knowledge(ref_detail={"key_points": long_kp, "common_traps": []}, ref_answer=None)
    check("知识片段长度受控（<=360 字）", bool(k4) and len(k4) <= 360, f"len={len(k4 or '')}")


def main() -> int:
    print("\nPhase 3 上下文工程 —— 量化验证")
    test_budget()
    test_token_saving()
    test_memory_roundtrip()
    test_knowledge()
    _sep("结论")
    if _failures:
        print(f"  失败 {len(_failures)} 项: {_failures}")
        return 1
    print("  全部通过 —— CONTEXT_ENGINEERING_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

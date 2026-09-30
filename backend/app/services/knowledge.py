# -*- coding: utf-8 -*-
"""
知识片段按需检索（对应标准③：知识库片段，模型只读取需要的那一块）。

问题背景：评分时模型本应拿「本题的评分参考」作为依据，但原实现完全没把参考
答案喂给评分模型，等于让评委盲评。这里从「本题」的结构化参考答案中抽取
「采分点 + 常见失分点」作为知识片段注入——只注入当前题，绝不全库塞入。
"""
from typing import Optional

from app.core.logging_config import get_logger

log = get_logger("knowledge")


def get_question_knowledge(*, ref_detail: dict | None, ref_answer: str | None,
                           max_chars: int = 360) -> str | None:
    """从本题参考答案抽取知识片段。ref_detail 为结构化参考答案 dict（含 key_points/common_traps）。"""
    if not ref_detail and not ref_answer:
        return None
    pieces: list[str] = []
    if isinstance(ref_detail, dict):
        kp = ref_detail.get("key_points") or []
        traps = ref_detail.get("common_traps") or []
        if kp:
            pieces.append("本题采分点：" + "；".join(str(k) for k in kp[:5]))
        if traps:
            pieces.append("本题常见失分点：" + "；".join(str(t) for t in traps[:3]))
    # 结构化参考缺失时，退化用规则参考答案要点
    if not pieces and ref_answer:
        pieces.append("参考答案要点：" + str(ref_answer)[:200])
    if not pieces:
        return None
    text = "\n".join(pieces)
    return text[:max_chars] if len(text) > max_chars else text


if __name__ == "__main__":
    # 沙箱自测
    r1 = get_question_knowledge(
        ref_detail={"key_points": ["紧扣题目给结论", "用数据支撑"], "common_traps": ["空泛无细节"]},
        ref_answer=None,
    )
    assert r1 and "采分点" in r1 and "失分点" in r1, r1
    r2 = get_question_knowledge(ref_detail=None, ref_answer="参考答案要点：先界定问题边界。")
    assert r2 and "参考答案要点" in r2, r2
    r3 = get_question_knowledge(ref_detail=None, ref_answer=None)
    assert r3 is None, "无参考应返回 None"
    print("KNOWLEDGE_SELFTEST_OK")

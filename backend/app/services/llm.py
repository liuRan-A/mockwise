# -*- coding: utf-8 -*-
"""
DeepSeek 大模型服务：面试作答评分 + 实时反馈/追问

设计原则：
1. 密钥只在后端 .env 配置，前端永不接触；
2. 任何异常（未配置 Key / 网络超时 / 限流 / 返回格式错误）都返回 None，
   由调用方降级到规则评分，保证「提交作答 → 出分 → 生成报告」业务闭环不被外部服务打断；
3. 严格 JSON 输出（response_format=json_object），并做字段校验与 clamp。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DIMENSIONS = ["专业深度", "逻辑结构", "语言表达", "应急应变", "岗位匹配"]

# —— 评分用系统提示 ——
_SCORE_SYS = """你是一名有 10 年经验的资深面试评委，正在评估候选人的模拟面试作答。
请严格按以下要求输出（必须是 JSON，不要输出任何多余文字）：
{
  "total_score": 0-100 的数字,  // 本题综合得分
  "dim_scores": {"专业深度": 0-100数字, "逻辑结构": 数字, "语言表达": 数字, "应急应变": 数字, "岗位匹配": 数字},
  "dim_comments": {"专业深度": "12字以内简短评语", "逻辑结构": "...", "语言表达": "...", "应急应变": "...", "岗位匹配": "..."},
  "understanding": "一句话概括你对候选人回答的理解（30-60字）",
  "strengths": [
    {"point": "答得好的地方（20字内，说清楚好在哪）", "quote": "对应的回答原句或精炼概括（40字内）"}
  ],
  "gaps": [
    {"point": "欠缺/答得不好的地方（20字内）", "why": "为什么这是问题（30字内）", "how": "具体怎么改（35字内）"}
  ],
  "highlights": ["回答中真实存在的亮点原句或精炼概括，2-3条，每条不超过40字"],
  "suggestions": ["针对性改进建议，2-3条，每条不超过40字"],
  "followup": "一道基于回答细节的追问问题（半结构化面试用，25字以内）"
}
评分标准：跑题/内容空洞 45-59；基本切题但缺细节 60-69；结构完整有案例 70-79；
有数据/有深度/逻辑清晰 80-89；非常出色 90-95。分数必须与回答质量匹配，禁止全部给高分。

strengths 与 gaps 的要求（这两项是复盘核心，务必认真区分）：
- strengths 写「确实做得对的点」，每条都要能对应到回答中的具体内容，禁止空泛夸奖；
- gaps 写「明确没做到位的点」，必须指出为什么是问题、以及具体怎么补；
- 若回答整体优秀，gaps 也要给出 1 条可继续拔高的点，不要留空；
- 若回答整体较差，strengths 至少保留 1 条真实存在的可取之处（哪怕只是态度或方向对）。
所有内容必须来自候选人的真实回答，不要编造。"""

# —— 实时反馈用系统提示（不打分，更快）——
_FEEDBACK_SYS = """你是一名面试教练，正在听候选人作答。请严格输出 JSON：
{
  "understanding": "一句话复述候选人表达的核心观点（30-60字）",
  "highlights": ["回答中的亮点，1-3条，每条不超过40字，必须来自真实回答"],
  "suggestions": ["可立即改进的建议，1-3条，每条不超过40字"],
  "followup": "一道顺着回答细节的追问（25字以内）",
  "dim_scores": {"专业深度": 0-100数字, "逻辑结构": 数字, "语言表达": 数字, "应急应变": 数字, "岗位匹配": 数字}
}
不要输出 JSON 以外的任何文字。"""


def _chat_json(system_prompt: str, user_prompt: str, timeout: Optional[int] = None) -> Optional[dict]:
    """调用 DeepSeek chat 接口并解析 JSON。任何失败返回 None（降级）。

    实现已委托给加固客户端 services.llm_client.chat_json，获得：
    - 网络层重试 + 退避（超时/限流/5xx）；
    - LLM 调用 token 用量埋点（供 Phase 4 可观测性消费）；
    失败语义与原实现一致：返回 None 触发调用方的规则评分兜底。
    """
    from app.services.llm_client import chat_json
    return chat_json(
        system_prompt, user_prompt,
        timeout=timeout, temperature=0.3, max_tokens=1200, json_mode=True,
    )


def _safe_json(content: str) -> Optional[dict]:
    """模型偶尔会在 JSON 外包裹 markdown，做容错提取"""
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        pass
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        return json.loads(content[start:end])
    except Exception:
        return None


def _clamp(v, lo=40.0, hi=96.0, default=65.0) -> float:
    try:
        f = float(v)
        return round(max(lo, min(hi, f)), 1)
    except Exception:
        return default


def _norm_dim_scores(raw: dict | None) -> dict:
    out = {}
    raw = raw or {}
    for d in DIMENSIONS:
        out[d] = _clamp(raw.get(d), lo=40, hi=96, default=65)
    return out


def _norm_str_list(raw, limit=3, max_len=40) -> list[str]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        s = str(item).strip().replace("\n", " ")
        if s:
            out.append(s[:max_len])
        if len(out) >= limit:
            break
    return out


def _norm_point_list(raw, limit=3) -> list[dict]:
    """规范化「答得好 / 欠缺」这类带说明的对象数组。
    兼容两种模型输出：对象数组 [{"point":..}] 或纯字符串数组 ["…"]。"""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, dict):
            d = {k: str(v).strip().replace("\n", " ") for k, v in item.items() if v}
            if d.get("point"):
                out.append(d)
        else:
            s = str(item).strip().replace("\n", " ")
            if s:
                out.append({"point": s[:60]})
        if len(out) >= limit:
            break
    return out


def score_answer(
    question_content: str,
    dimension: str,
    category: str,
    transcript: str,
    form_type: str = "structured",
    user_memory: str | None = None,
    knowledge: str | None = None,
) -> Optional[dict]:
    """
    大模型评分。返回：
    {
      "total_score": float,
      "dim_scores": {dim: score},
      "dim_comments": {dim: comment},
      "understanding": str,
      "highlights": [str],
      "suggestions": [str],
      "followup": str,
      "engine": "deepseek",
      "ctx_meta": {...}   # 上下文工程元数据（供 P4 可观测性消费）
    }
    失败返回 None。

    上下文工程：用 ContextBuilder 分层装配——
      TASK(9)   题目+作答（必保）
      KNOWLEDGE(7) 本题参考答案要点（仅本题，按需）
      USER_MEMORY(6) 候选人在该维度的长期记忆（按需）
    在 token 预算内优先保留高优先级片段，超出则裁剪低优先级。
    """
    if not transcript or len(transcript.strip()) < 8:
        return None

    form_label = {"structured": "结构化面试", "group": "无领导小组讨论", "semi": "半结构化面试"}.get(form_type, "结构化面试")

    from app.services.context import ContextBuilder, ContextLayer
    builder = ContextBuilder(max_tokens=3200, system_prompt=_SCORE_SYS)
    builder.add(
        f"【面试形式】{form_label}\n"
        f"【题目类别】{category or '通用'}\n"
        f"【考察维度】{dimension or '综合'}\n"
        f"【面试题目】{question_content or '（见候选人作答）'}\n"
        f"【候选人作答原文】\n{transcript[:2200]}\n"
        f"请以评委身份评分并输出 JSON。",
        ContextLayer.TASK, priority=9, key="task",
    )
    if knowledge:
        builder.add(
            "【评分参考（仅本题，供把握给分尺度）】\n" + knowledge,
            ContextLayer.KNOWLEDGE, priority=7, key="knowledge",
        )
    if user_memory:
        builder.add(
            "【候选人长期记忆（按需召回，仅作参考）】\n" + user_memory,
            ContextLayer.USER_MEMORY, priority=6, key="memory",
        )
    ctx = builder.assemble()
    # 可观测性：标记场景并把上下文元数据挂到本次调用（落库后可用于统计上下文命中率/超预算率）
    from app.services.tracing import scene, attach_ctx_meta
    with scene("score_answer"):
        attach_ctx_meta(ctx["meta"])
        data = _chat_json(ctx["system"], ctx["user"])
    if not data:
        return None

    dim_scores = _norm_dim_scores(data.get("dim_scores"))
    total = _clamp(data.get("total_score"), lo=40, hi=96,
                   default=round(sum(dim_scores.values()) / len(dim_scores), 1))

    comments_raw = data.get("dim_comments") or {}
    dim_comments = {}
    for d in DIMENSIONS:
        c = str(comments_raw.get(d) or "").strip()
        dim_comments[d] = c[:24] if c else f"{d}表现{('优秀' if dim_scores[d] >= 80 else '良好' if dim_scores[d] >= 70 else '待提升')}"

    return {
        "total_score": total,
        "dim_scores": dim_scores,
        "dim_comments": dim_comments,
        "understanding": str(data.get("understanding") or "").strip()[:120] or "候选人围绕题目给出了作答，具体表现见各维度评分。",
        "strengths": _norm_point_list(data.get("strengths"), limit=3),
        "gaps": _norm_point_list(data.get("gaps"), limit=3),
        "highlights": _norm_str_list(data.get("highlights"), limit=3, max_len=40),
        "suggestions": _norm_str_list(data.get("suggestions"), limit=3, max_len=40),
        "followup": str(data.get("followup") or "").strip()[:60],
        "engine": "deepseek",
        "ctx_meta": ctx["meta"],
    }


def analyze_answer(
    transcript: str,
    dimension: str = "",
    question_content: str = "",
    user_memory: str | None = None,
    knowledge: str | None = None,
) -> Optional[dict]:
    """大模型实时反馈（理解/亮点/建议/追问）。失败返回 None。

    上下文工程：与 score_answer 同一套 ContextBuilder 分层装配，但预算更小
    （实时反馈走快路径，宁可少给上下文也要低延迟）：
      TASK(9)       题目 + 作答（必保，作答截断更短以控延迟）
      KNOWLEDGE(7)  本题参考答案要点（可选，预算内才注入）
      USER_MEMORY(6) 候选人在该维度的长期记忆（可选）
    """
    if not transcript or len(transcript.strip()) < 8:
        return None

    from app.services.context import ContextBuilder, ContextLayer
    builder = ContextBuilder(max_tokens=1600, system_prompt=_FEEDBACK_SYS)
    builder.add(
        f"【考察维度】{dimension or '综合'}\n"
        f"【面试题目】{question_content or '（通用面试题）'}\n"
        f"【候选人作答】\n{transcript[:1800]}\n"
        f"请输出反馈 JSON。",
        ContextLayer.TASK, priority=9, key="task",
    )
    if knowledge:
        builder.add(
            "【本题参考要点（供判断亮点/建议，勿直接复述）】\n" + knowledge,
            ContextLayer.KNOWLEDGE, priority=7, key="knowledge",
        )
    if user_memory:
        builder.add(
            "【候选人长期记忆（按需召回）】\n" + user_memory,
            ContextLayer.USER_MEMORY, priority=6, key="memory",
        )
    ctx = builder.assemble()
    from app.services.tracing import scene, attach_ctx_meta
    with scene("analyze_answer"):
        attach_ctx_meta(ctx["meta"])
        data = _chat_json(ctx["system"], ctx["user"], timeout=30)
    if not data:
        return None
    return {
        "understanding": str(data.get("understanding") or "").strip()[:120] or "候选人已表达核心观点。",
        "highlights": _norm_str_list(data.get("highlights"), limit=3, max_len=40),
        "suggestions": _norm_str_list(data.get("suggestions"), limit=3, max_len=40),
        "followup": str(data.get("followup") or "").strip()[:60],
        "dim_scores": _norm_dim_scores(data.get("dim_scores")),
        "engine": "deepseek",
        "ctx_meta": ctx["meta"],
    }


# —— 简历分析 ——
_RESUME_SYS = """你是一名资深 HR 和技术面试官。请分析候选人简历，严格输出 JSON（不要多余文字）：
{
  "candidate_name": "姓名（简历中没有则空字符串）",
  "target_position": "求职意向/目标岗位",
  "years_exp": "工作年限数字（字符串，如 3）",
  "summary": "候选人画像概述（60-100字，含背景、核心优势）",
  "skills": ["核心技能3-6项"],
  "projects": ["代表项目/经历，2-4项，每项含角色与成果，不超过50字"],
  "highlights": ["简历亮点2-3项"],
  "weaknesses": ["可能被面试官追问或质疑的薄弱点2-3项"],
  "suggested_questions": ["基于简历内容的个性化面试题5-6道，围绕项目细节、技术决策、成果真实性、岗位匹配，每题不超过45字"]
}
suggested_questions 必须具体引用简历中的项目/技能/数据，不要泛泛而谈。"""

_RESUME_RULE_SKILLS = ["项目管理", "数据分析", "沟通协作", "问题解决", "团队协作"]


def analyze_resume(resume_text: str) -> Optional[dict]:
    """大模型分析简历生成画像。失败返回 None（调用方做规则兜底）。"""
    if not resume_text or len(resume_text.strip()) < 20:
        return None
    from app.services.tracing import scene
    with scene("resume"):
        data = _chat_json(_RESUME_SYS, f"【候选人简历】\n{resume_text[:4000]}\n请输出画像 JSON。", timeout=45)
    if not data:
        return None
    return {
        "candidate_name": str(data.get("candidate_name") or "").strip()[:32],
        "target_position": str(data.get("target_position") or "").strip()[:64],
        "years_exp": str(data.get("years_exp") or "").strip()[:8],
        "summary": str(data.get("summary") or "").strip()[:200] or "候选人简历已解析。",
        "skills": _norm_str_list(data.get("skills"), limit=6, max_len=24),
        "projects": _norm_str_list(data.get("projects"), limit=4, max_len=60),
        "highlights": _norm_str_list(data.get("highlights"), limit=3, max_len=50),
        "weaknesses": _norm_str_list(data.get("weaknesses"), limit=3, max_len=50),
        "suggested_questions": _norm_str_list(data.get("suggested_questions"), limit=6, max_len=60),
        "engine": "deepseek",
    }


def rule_analyze_resume(resume_text: str) -> dict:
    """规则兜底画像（DeepSeek 不可用时）。题目必须引用简历真实内容（项目/技能/量化数据），避免泛泛模板。"""
    text = resume_text or ""
    # 简单技能关键词命中
    skill_kw = {
        "Python": ["python"], "Java": ["java"], "前端": ["vue", "react", "前端", "javascript"],
        "数据分析": ["数据分析", "sql", "报表"], "项目管理": ["项目管理", "负责", "主导"],
        "AI/算法": ["ai", "算法", "模型", "机器学习", "大模型"],
        "运营": ["运营", "增长", "用户"], "产品": ["产品", "需求", "原型"],
    }
    skills = [name for name, kws in skill_kw.items() if any(k in text.lower() for k in kws)]

    # 目标岗位 / 年限提取
    target = ""
    m = re.search(r"求职意向[:：]\s*([^\s，,。；;]{2,20})", text)
    if m:
        target = m.group(1)
    years = ""
    m = re.search(r"(\d+)\s*年[^。\n]{0,6}(经验|工作)", text)
    if m:
        years = m.group(1)

    # 项目/经历行：优先含动作词的行
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 12]
    proj_kws = ["项目", "负责", "主导", "设计", "搭建", "优化", "上线", "系统", "开发", "实现", "建设"]
    proj_lines = [l for l in lines if any(k in l for k in proj_kws)] or lines
    projects = proj_lines[:3] if proj_lines else ["（简历中未提取到结构化项目经历）"]

    # 量化数据（如 "召回率提升15%" "62%提升到78%"）
    nums = [n[:16] for n in re.findall(r"[\u4e00-\u9fa5A-Za-z]{1,10}?\d+(?:\.\d+)?(?:%|万|倍)", text)][:2]

    name = ""
    for line in text.split("\n")[:5]:
        m = re.search(r"([\u4e00-\u9fa5]{2,4})(?=\s|$|简历|的|，|,)", line.strip())
        if m and len(m.group(1)) >= 2:
            name = m.group(1)
            break

    # —— 基于简历内容的个性化问题（引用真实项目/技能/数据） ——
    p1 = _proj_short(projects[0])
    qs = [f"你在简历里写到「{p1}」，请讲讲你承担的具体角色和最大的挑战？"]
    if nums:
        qs.append(f"简历中提到「{nums[0]}」，这个数字是怎么测出来的？如何证明是你的贡献？")
    if skills:
        qs.append(f"你提到熟悉{skills[0]}，说说你用它解决过的最棘手的一个问题？")
    if len(projects) > 1:
        qs.append(f"关于「{_proj_short(projects[1])}」，如果让你重新做一次，你会改进哪一点？")
    if len(nums) > 1:
        qs.append(f"「{nums[1]}」这个结果花了多久达成？中间遇到的最大阻力是什么？")
    qs.append("这些经历里最有成就感的一件事是什么？它如何支撑你的求职目标？")
    # 兜底补足 5 题
    fallback_qs = [
        "请用 STAR 法则展开你简历中最核心的一段经历。",
        "简历中团队协作的角色分工是怎样的？出现分歧时你如何推进？",
    ]
    for f in fallback_qs:
        if len(qs) >= 5:
            break
        qs.append(f)

    return {
        "candidate_name": name,
        "target_position": target,
        "years_exp": years,
        "summary": (f"{'约 ' + years + ' 年经验、' if years else ''}{'目标岗位 ' + target + '。' if target else ''}"
                    f"已基于简历关键词生成画像（规则引擎），核心技能：{'、'.join(skills[:4]) if skills else '见简历'}。"),
        "skills": skills or _RESUME_RULE_SKILLS[:4],
        "projects": projects,
        "highlights": (["有可量化的项目成果" if nums else "具备相关岗位项目经历"]
                       + [f"掌握 {skills[0]}" if skills else "简历结构完整"])[:2],
        "weaknesses": (["项目成果的数据口径可能被追问"] if nums else []) +
                      ["经历集中于单一公司/方向，转型动机会被问", "部分技能缺少项目佐证"],
        "suggested_questions": qs[:6],
        "engine": "rule",
    }


def _proj_short(s: str, n: int = 18) -> str:
    """从简历行中截取可读的项目引用片段（去序号/标签前缀，优先从动作词截取）"""
    s = re.sub(r"^\d+[.、）)]\s*", "", (s or "").strip())
    s = re.sub(r"^[\u4e00-\u9fa5A-Za-z]{1,8}[:：]", "", s)  # 去掉「工作经历：」「项目：」等前缀
    for kw in ["主导", "独立设计", "负责", "设计", "搭建", "建设", "开发", "优化", "上线", "项目"]:
        i = s.find(kw)
        if i >= 0:
            s = s[i:]
            break
    else:
        s = re.sub(r"\d{4}\s*[-—至/年.]\s*[\d]{0,4}\s*[-—至/月]?\s*[\d月]{0,4}", "", s).strip() or s
    return s[:n].strip()


def _resume_ref_answer(content: str, profile: dict) -> str:
    """为简历动态题生成参考答案要点"""
    projects = profile.get("projects") or [""]
    proj = _proj_short(str(projects[0]))
    if "数据" in content or "证明" in content or "数字" in content:
        body = ("说明统计口径与基线 → 拆解你的具体贡献边界 → 给出测量方法（如 A/B、埋点、监控大盘）"
                f"→ 举一个数据背后的具体动作（结合「{proj}」）。")
    elif "角色" in content or "挑战" in content or "承担" in content:
        body = (f"STAR 展开——情境：交代「{proj}」的背景与目标；任务：明确你的角色与职责边界；"
                "行动：分 2-3 步讲关键决策与执行细节；结果：量化成果 + 复盘改进。")
    elif "改进" in content or "重新" in content:
        body = ("先肯定原方案的合理性 → 指出 1-2 个真实的局限（数据/成本/扩展性）→ 给出改进方案与预期收益，"
                "体现反思深度而不是全盘否定。")
    elif "技能" in content or "棘手" in content or "熟悉" in content:
        body = ("选一个真实难题：问题现象 → 排查过程 → 你的解决方案 → 最终效果（含量化数据），"
                "突出该技能在其中的关键作用。")
    else:
        body = "结论先行 → 分点展开（每点配案例或数据）→ 总结回扣问题，控制在 2 分钟内。"
    return f"参考答案要点：{body}"


# —— 参考答案生成 ——
_REF_ANSWER_SYS = """你是一名资深面试官，正在为模拟面试题撰写「标准参考答案」，供考生对照复盘。
请严格输出 JSON（不要多余文字）：
{
  "key_points": ["面试官最想听到的采分点，3-5条，每条25字内，必须紧扣本题"],
  "outline": ["推荐的答题框架，3-4步，每条30字内，体现先后顺序"],
  "sample": "一段完整的示范作答，250-400字，第一人称、口语化，像真人在面试现场说出来，要贴合本题场景",
  "common_traps": ["本题常见失分点，2-3条，每条30字内"]
}
要求：
1. 所有内容必须围绕【面试题目】展开，禁止输出通用模板；
2. key_points 是评分时的给分依据，要具体、可检验；
3. sample 要能直接朗读，有细节、有数据占位（如「提升了约 20%」），不要写成提纲；
4. 若题目来自候选人简历，示范作答要贴合其背景。"""


def _norm_ref_answer(data: dict | None) -> dict | None:
    """校验参考答案结构：四项至少要有实质内容才算有效"""
    if not isinstance(data, dict):
        return None
    key_points = _norm_str_list(data.get("key_points"), limit=5, max_len=60)
    outline = _norm_str_list(data.get("outline"), limit=4, max_len=70)
    sample = str(data.get("sample") or "").strip()
    traps = _norm_str_list(data.get("common_traps"), limit=3, max_len=70)
    if not key_points or len(sample) < 40:
        return None
    return {
        "key_points": key_points,
        "outline": outline,
        "sample": sample[:900],
        "common_traps": traps,
        "engine": "deepseek",
    }


def generate_reference_answer(
    question_content: str,
    category: str = "",
    dimension: str = "",
    form_type: str = "structured",
    resume_profile: dict | None = None,
) -> dict:
    """
    生成结构化参考答案：采分点 / 答题框架 / 示范作答 / 常见失分点。
    大模型优先，失败降级规则生成（保证永不返回 None，业务不中断）。
    """
    if question_content and len(question_content.strip()) >= 6:
        profile_hint = ""
        if resume_profile:
            skills = resume_profile.get("skills") or []
            projects = resume_profile.get("projects") or []
            if skills or projects:
                profile_hint = (
                    f"\n【候选人背景】技能：{'、'.join(str(s) for s in skills[:4])}；"
                    f"经历：{str(projects[0])[:60] if projects else '（无）'}"
                )
        form_label = {"structured": "结构化面试", "group": "无领导小组讨论",
                      "semi": "半结构化面试"}.get(form_type, "结构化面试")
        user_prompt = (
            f"【面试形式】{form_label}\n"
            f"【题目类别】{category or '通用'}\n"
            f"【考察维度】{dimension or '综合'}\n"
            f"【面试题目】{question_content}\n"
            f"{profile_hint}\n"
            f"请输出参考答案 JSON。"
        )
        try:
            from app.services.tracing import scene
            with scene("ref_answer"):
                parsed = _norm_ref_answer(_chat_json(_REF_ANSWER_SYS, user_prompt, timeout=45))
            if parsed:
                return parsed
        except Exception as e:
            logger.warning("[llm] 参考答案生成失败，降级规则: %s", e)
    return _rule_reference_answer(question_content, category, dimension)


def _topic_of(content: str, n: int = 14) -> str:
    """从题目里提炼一个能自然嵌进示范作答的短主题。
    例：「如果线上服务突然出现大量超时，你会怎么处理？」→「线上服务突然出现大量超时」"""
    s = re.sub(r"^[0-9]+[.、）)]\s*", "", (content or "").strip())
    s = re.sub(r"^(?:如果|假如|假设|请问|请|谈谈|谈一谈|说说|说一说|讲讲|讲一讲"
               r"|描述一下|描述|你)+", "", s)
    s = re.sub(r"(你会怎么|你怎么|该怎么|如何处理|怎么处理|怎么办|怎么应对|怎么解决"
               r"|有什么思路|有哪些思路|是什么|有哪些|请展开|请说明).*$", "", s)
    s = s.strip(" ，。？?！!、,;；:：")
    return (s[:n].strip() or "这类问题")


def _rule_reference_answer(question_content: str, category: str, dimension: str) -> dict:
    """规则兜底参考答案：按题目类别/维度给出差异化的采分点、框架、示范与失分点"""
    content = question_content or ""
    cat = category or ""
    dim = dimension or ""

    # 从题目里提炼一个短主题，让示范作答读起来是「针对这道题」的，而不是套模板
    topic = _topic_of(content)

    if "自我介绍" in cat or "自我介绍" in content or "介绍你自己" in content:
        key_points = [
            "30 秒内交代身份与核心方向，不背简历",
            "挑 2 个与目标岗位强相关的代表作",
            "每个成果带一个可验证的量化结果",
            "结尾一句话点明与岗位的匹配点",
        ]
        outline = ["背景定位（身份 + 方向 + 年限）", "代表作一（角色 + 动作 + 数据）",
                   "代表作二（难点 + 解法 + 结果）", "回扣岗位：为什么我适合"]
        sample = (
            "面试官您好，我是 X，做 Y 方向 N 年，主要在 A 和 B 两块。\n"
            "最近一段我主导了 ____ 这个项目：当时面临的核心是 ____，"
            "我把它拆成三步推进——先 ____，再 ____，最后 ____，"
            "最终把核心指标从 ____ 提升到 ____，大概提升了 20%。\n"
            "另外我还做过 ____，沉淀了一套可复用的 ____ 方法。\n"
            "我关注到贵岗位需要 ____，这正好和我前面两段经历吻合，所以很想深入聊聊。"
        )
        traps = ["把简历从头背一遍，没有重点", "成果没有数据，全是形容词", "自我介绍超过 2 分钟，抢了后续提问时间"]

    elif "简历深挖" in cat or "项目" in cat or "项目" in content or "经历" in cat:
        key_points = [
            "说清项目背景与目标，界定问题边界",
            "明确「我」的角色与职责边界，区分团队贡献",
            "讲关键决策的取舍理由，而不只是做了什么",
            "给出可验证的量化结果与复盘反思",
        ]
        outline = ["情境 S：项目背景与目标", "任务 T：我的角色与职责边界",
                   "行动 A：2-3 个关键决策与执行细节", "结果 R：量化成果 + 复盘改进"]
        sample = (
            "这个项目（%s）当时的背景是 ____，目标是 ____，我负责的是 ____ 这一块。\n"
            "最大的难点在 ____。我评估后有两个方案：方案一 ____ 成本低但扩展性差，"
            "方案二 ____ 前期投入大但能支撑后续 ____，我选了方案二，理由是 ____。\n"
            "执行上分三步：先 ____，再 ____，最后 ____。中间踩过的坑是 ____，我通过 ____ 解决。\n"
            "最终结果是 ____，核心指标提升了约 ____%%。如果重来一次，我会在 ____ 上更早 ____。"
        ) % topic
        traps = ["全程说「我们」，说不清个人贡献", "只讲流程不讲决策取舍", "结果没有数据或数据口径经不起追问"]

    elif "情景" in cat or dim == "应急应变" or "突发" in content or "怎么办" in content:
        key_points = [
            "第一时间止血：先控制影响面，不急着找根因",
            "快速评估影响范围与优先级，给出判断依据",
            "给出具体可执行的处置步骤与时间预期",
            "事后复盘沉淀机制，避免同类问题再发",
        ]
        outline = ["止血（降级/熔断/回滚，先恢复服务）", "定位根因并评估影响面",
                   "给出修复方案与灰度/回滚预案", "复盘沉淀：监控、预案、流程"]
        sample = (
            "遇到「%s」这种情况，我第一步一定是先止血，控制影响面——"
            "比如先 ____（降级/回滚/切流量），让业务先恢复可用，预计 ____ 分钟内生效。\n"
            "第二步同步评估影响：看 ____ 指标和 ____ 日志，确认受影响的用户量级和数据是否需要补偿。\n"
            "第三步定位根因并修复：我的排查顺序是 ____，同时保留 ____ 便于回溯。\n"
            "修复后灰度上线观察 ____ 分钟，确认指标正常再全量，并保留回滚开关。\n"
            "最后复盘：补上 ____ 的监控告警，把这次的处置步骤沉淀成 runbook，并做一次故障演练。"
        ) % topic
        traps = ["一上来就找根因，忽略了先止血", "只说要排查，没有时间预期和判断依据", "答完就结束，没有复盘和机制沉淀"]

    elif dim == "专业深度" or "专业" in cat or "技术" in cat:
        key_points = [
            "先给结论或方案全景，让面试官知道你要讲什么",
            "分层拆解（如数据/模型/工程/成本）并给选型理由",
            "讲清关键参数的权衡与踩过的坑",
            "用核心指标收尾，量化效果或代价",
        ]
        outline = ["结论先行：整体方案是什么", "分层拆解并说明每层的技术选型",
                   "关键权衡：为什么这么选、放弃了什么", "效果与代价：指标表现 + 已知局限"]
        sample = (
            "关于「%s」，我的整体思路是 ____。\n"
            "拆开看分三层：数据层 ____，核心层 ____，工程层 ____。"
            "选型上我选 ____ 而不是 ____，主要考虑 ____（性能/成本/可维护性）。\n"
            "这里有个关键权衡：____ 会增加 ____ 的开销，但能换来 ____，"
            "结合我们的场景（____），这笔交换是划算的。\n"
            "实际上线后指标是 ____，相比之前提升了 ____%%；目前的局限在 ____，"
            "后续我计划通过 ____ 优化。"
        ) % topic
        traps = ["堆砌名词但说不清为什么这么选", "只讲优点不提局限和代价", "缺少量化指标，无法判断真实水平"]

    elif dim == "逻辑结构":
        key_points = ["结论先行，第一句就给出核心判断",
                      "分点之间有清晰的逻辑关系（并列/递进/时间）",
                      "每一点都有论据或案例支撑",
                      "结尾回扣题目，不跑题"]
        outline = ["结论：我的判断是什么", "理由一 + 论据", "理由二 + 论据", "总结回扣 + 补充边界条件"]
        sample = (
            "我的结论是 ____。\n"
            "主要有三方面理由。第一，____，比如 ____ 这个案例就能说明。"
            "第二，____，从数据上看 ____。第三，____，风险在于 ____，可以用 ____ 对冲。\n"
            "所以综合来看 ____。当然这个结论的前提是 ____，"
            "如果 ____ 发生变化，我会调整为 ____。"
        )
        traps = ["先讲半天铺垫，结论放在最后", "分点之间逻辑重叠或跳跃", "只列观点不给论据"]

    elif dim == "语言表达":
        key_points = ["观点明确，一句话说清立场",
                      "用数据或事实支撑观点",
                      "主动交代风险与预案，体现周全",
                      "控制时长，重点前置"]
        outline = ["观点（一句话）", "数据支撑", "风险与预案", "一句话总结"]
        sample = (
            "我的看法是 ____。\n"
            "支撑这个判断的数据是 ____（说明口径：____）。\n"
            "需要注意的风险是 ____，我的预案是 ____，触发条件是 ____。\n"
            "所以简单说，____。"
        )
        traps = ["口头禅多、表达绕", "有观点没数据", "没提风险和边界，显得不周全"]

    elif dim == "岗位匹配" or "匹配" in cat or "为什么" in content:
        key_points = ["先说清对岗位要求的理解",
                      "逐条对照自己的能力项，给出对应经历",
                      "每个能力项配一个量化结果",
                      "说明职业规划与岗位的长期契合"]
        outline = ["我对岗位要求的理解", "能力项一 → 对应经历 + 数据",
                   "能力项二 → 对应经历 + 数据", "规划契合：短期能做什么、长期想成长为什么"]
        sample = (
            "我理解这个岗位核心要看三块：____、____ 和 ____。\n"
            "第一块我有直接经验：在 ____ 项目里我 ____，结果是 ____。"
            "第二块我做过 ____，虽然没有那么深，但 ____ 这个方法是相通的，我上手会比较快。\n"
            "第三块目前是我的短板，我的补齐计划是 ____。\n"
            "短期我能马上贡献的是 ____；长期我希望在 ____ 方向深耕，这和岗位的发展路径是一致的。"
        )
        traps = ["空喊「我很匹配」但拿不出证据", "只讲过去不讲岗位需要什么", "对岗位理解停留在 JD 字面"]

    else:
        key_points = ["先界定问题边界，确认理解一致",
                      "给出分步骤的可执行方案",
                      "说明预期效果与衡量方式",
                      "预设风险与应对"]
        outline = ["明确问题边界与目标", "分步方案（每步的动作与产出）",
                   "预期效果 + 衡量指标", "风险与预案"]
        sample = (
            "关于「%s」，我先确认一下目标：我们要解决的是 ____，衡量标准是 ____。\n"
            "我的方案分三步：第一步 ____，产出是 ____；第二步 ____，产出是 ____；"
            "第三步 ____，产出是 ____。\n"
            "预期效果是 ____，我会用 ____ 这个指标来跟踪。\n"
            "主要风险是 ____，我的预案是 ____。如果资源只够做一件事，我会优先 ____，因为 ____。"
        ) % topic
        traps = ["没确认问题就开始答，容易跑题", "只有方向没有具体步骤", "没说怎么衡量效果"]

    return {
        "key_points": key_points,
        "outline": outline,
        "sample": sample,
        "common_traps": traps,
        "engine": "rule",
    }


def generate_resume_questions(profile: dict, count: int = 5) -> list[dict]:
    """
    基于简历画像生成半结构化面试题（用于动态出题）。
    返回 [{content, dimension, category, time_limit_s, ref_answer}]
    """
    questions = []
    projects = profile.get("projects") or []
    skills = profile.get("skills") or []
    suggested = profile.get("suggested_questions") or []

    dims = ["专业深度", "逻辑结构", "应急应变", "岗位匹配", "语言表达"]

    # 优先采用大模型/规则引擎给的个性化题（含简历真实内容）
    for i, q in enumerate(suggested[:count]):
        q = q.strip()
        if q:
            questions.append({
                "content": q,
                "dimension": dims[i % len(dims)],
                "category": "简历深挖",
                "time_limit_s": 180,
            })
    # 不足则用项目/技能模板补（引用简历真实内容）
    tpls = []
    if projects:
        p0 = _proj_short(str(projects[0]), 20)
        tpls.append((f"结合你的项目经历「{p0}」，请讲讲你当时面临的核心问题和你的解决思路。", "专业深度"))
    if skills:
        tpls.append((f"你在简历中提到熟悉{skills[0]}，能否举一个用它解决实际问题的具体例子？", "岗位匹配"))
    tpls.append(("请用 STAR 法则（情境-任务-行动-结果）介绍一段你最能体现能力的经历。", "逻辑结构"))

    for content, dim in tpls:
        if len(questions) >= count:
            break
        questions.append({"content": content, "dimension": dim, "category": "简历深挖", "time_limit_s": 180})

    out = questions[:count]
    for q in out:
        q["ref_answer"] = _resume_ref_answer(q["content"], profile)
    return out

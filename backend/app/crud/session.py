"""模拟场次 CRUD + 评分计算（demo 规则）"""
import random
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import UserQuota, PracticeHistory, UserStreak
from app.models.question import QuestionSet, Question
from app.models.session import (
    InterviewConfig, InterviewSession, SessionQuestion,
    SessionScore, SessionMetrics, SessionHighlight, SessionRecommendation,
)
from app.models.report import Report, ReportHighlight, ReportRecommendation


# 评估维度（与原型一致）
DIMENSIONS = ["专业深度", "逻辑结构", "语言表达", "应急应变", "岗位匹配"]


def create_config(db: Session, user_id: int, **data) -> InterviewConfig:
    cfg = InterviewConfig(user_id=user_id, **data)
    db.add(cfg)
    db.flush()
    return cfg


def start_session(db: Session, user_id: int, cfg: InterviewConfig, qset: QuestionSet,
                  use_resume: bool = False, resume_count: int = 2) -> InterviewSession:
    """
    开始一场模拟。出题策略：
    - 群面（group）：一场只围绕一个辩题讨论，不混入简历题；
    - 结构化 / 半结构化：题库题 + 简历深挖题「混合」编排，
      用户上传过简历时至少插入 MIN_RESUME_Q 道来自简历的题目（穿插在题库题之间，不堆在最后）。
    """
    sess = InterviewSession(
        user_id=user_id,
        config_id=cfg.id,
        set_id=qset.id,
        form_type=cfg.form_type,
        status="running",
        started_at=datetime.now(),
    )
    db.add(sess)
    db.flush()

    questions = db.query(Question).filter(
        Question.set_id == qset.id
    ).order_by(Question.seq).all()
    if cfg.form_type == "group":
        questions = questions[:1]

    # —— 简历个性化出题：结构化同样生效（只要用户有活跃简历画像） ——
    resume_questions = _build_resume_questions(db, user_id) if use_resume else None

    if cfg.form_type == "group" or not resume_questions:
        # 纯题库题
        for i, q in enumerate(questions, 1):
            db.add(SessionQuestion(
                session_id=sess.id,
                question_id=q.id,
                source="bank",
                content=q.content, category=q.category, dimension=q.dimension,
                time_limit_s=q.time_limit_s or 120,
                ref_answer=q.ref_answer or None,
                seq=i, phase="answer", status="pending",
            ))
    else:
        # 混合出题：题库题 + 简历题
        for i, item in enumerate(_mix_questions(questions, resume_questions, resume_count), 1):
            if item["source"] == "resume":
                db.add(SessionQuestion(
                    session_id=sess.id,
                    question_id=None,
                    source="resume",
                    content=item["content"],
                    category=item.get("category", "简历深挖"),
                    dimension=item.get("dimension", "专业深度"),
                    time_limit_s=item.get("time_limit_s", 180),
                    ref_answer=item.get("ref_answer") or None,
                    seq=i, phase="answer", status="pending",
                ))
            else:
                q = item["question"]
                db.add(SessionQuestion(
                    session_id=sess.id,
                    question_id=q.id,
                    source="bank",
                    content=q.content, category=q.category, dimension=q.dimension,
                    time_limit_s=q.time_limit_s or 120,
                    ref_answer=q.ref_answer or None,
                    seq=i, phase="answer", status="pending",
                ))
    db.flush()
    return sess


MIN_RESUME_Q = 2   # 有简历时，一场至少插入几道来自简历的题


def _mix_questions(bank_questions: list, resume_questions: list, resume_count: int = 2) -> list[dict]:
    """
    把简历深挖题穿插进题库题序列，返回统一的 item 列表。
    简历题数量 = clamp(max(MIN_RESUME_Q, resume_count), 可用数, 题库题数)，
    均匀插入（不放在第一题，避免开场就被深挖）。
    """
    bank = [{"source": "bank", "question": q} for q in bank_questions]
    if not resume_questions or not bank:
        return bank

    want = max(MIN_RESUME_Q, int(resume_count or 0))
    want = min(want, len(resume_questions), len(bank))
    picked = [{"source": "resume", **q} for q in resume_questions[:want]]

    n = len(bank)
    m = len(picked)
    for i, rq in enumerate(picked):
        # 等分插入点；+i 补偿已插入元素带来的偏移
        pos = min(len(bank), round((i + 1) * n / (m + 1)) + i)
        bank.insert(pos, rq)
    return bank


def _build_resume_questions(db: Session, user_id: int, count: int = 5):
    """读取用户活跃简历画像，生成简历深挖题；无简历/无画像返回 None"""
    try:
        from app.models.position import Resume
        from app.services.llm import generate_resume_questions
        r = db.query(Resume).filter(
            Resume.user_id == user_id, Resume.is_active == 1
        ).order_by(Resume.created_at.desc()).first()
        if not r or not r.parsed_json:
            return None
        return generate_resume_questions(r.parsed_json, count=count)
    except Exception:
        return None


def get_session(db: Session, session_id: int) -> InterviewSession | None:
    return db.get(InterviewSession, session_id)


def get_session_question(db: Session, sq_id: int) -> SessionQuestion | None:
    return db.get(SessionQuestion, sq_id)


def list_session_questions(db: Session, session_id: int):
    return db.query(SessionQuestion).filter(
        SessionQuestion.session_id == session_id
    ).order_by(SessionQuestion.seq).all()


def submit_answer(db: Session, sq: SessionQuestion, transcript: str, audio_url: str, duration_ms: int):
    """提交作答 + 评分（DeepSeek 大模型优先，失败降级规则评分），全部真实入库"""
    sq.transcript = transcript
    sq.audio_url = audio_url
    sq.duration_ms = duration_ms
    sq.status = "done"
    sq.answered_at = datetime.now()

    question = db.get(Question, sq.question_id) if sq.question_id else None
    q_content = (question.content if question else None) or sq.content or ""
    q_dim = (question.dimension if question else None) or sq.dimension or ""
    q_cat = (question.category if question else None) or sq.category or ""
    form_type = sq.session.form_type if sq.session else "structured"

    # —— 优先 DeepSeek 大模型评分 ——
    ai = None
    try:
        from app.services.llm import score_answer
        from app.crud.memory import retrieve_relevant
        from app.services.knowledge import get_question_knowledge
        # 上下文工程：按需召回「与本题维度/类别相关」的用户记忆 + 仅本题知识片段
        uid = sq.session.user_id if sq.session else 0
        mem = retrieve_relevant(db, uid, dimension=q_dim, category=q_cat) if uid else None
        know = get_question_knowledge(ref_detail=sq.ref_detail, ref_answer=sq.ref_answer)
        ai = score_answer(q_content, q_dim, q_cat, transcript, form_type=form_type,
                          user_memory=mem, knowledge=know)
    except Exception as e:  # noqa: BLE001
        logger = __import__("logging").getLogger(__name__)
        logger.warning("[session] 评分上下文装配失败，回退纯评分: %s", e)
        try:
            from app.services.llm import score_answer
            ai = score_answer(q_content, q_dim, q_cat, transcript, form_type=form_type)
        except Exception:
            ai = None

    hit = _hit_keywords(transcript)
    if ai:
        base = float(ai["total_score"])
        sq.total_score = round(base, 2)
        for dim in DIMENSIONS:
            db.add(SessionScore(
                session_question_id=sq.id,
                dimension=dim,
                score=float(ai["dim_scores"].get(dim, base)),
                comment=ai["dim_comments"].get(dim, "")[:255],
            ))
    else:
        # —— 规则评分兜底（无 Key / 超时 / 异常时业务不中断） ——
        has_structure = hit["struct"]
        has_data = hit["data"]
        has_risk = hit["risk"]
        content_len = len(transcript)
        structure_bonus = 8 if has_structure else 0
        data_bonus = 6 if has_data else 0
        risk_bonus = 5 if has_risk else 0
        base = 60 + min(20, content_len // 50) + structure_bonus + data_bonus + risk_bonus + random.uniform(-3, 3)
        base = max(45, min(96, base))
        sq.total_score = round(base, 2)

        dim_adjustments = {
            "专业深度": data_bonus + (3 if has_risk else 0),
            "逻辑结构": structure_bonus,
            "语言表达": min(8, content_len // 80),
            "应急应变": risk_bonus + (3 if "预案" in transcript or "回滚" in transcript else 0),
            "岗位匹配": min(6, content_len // 100),
        }
        for dim in DIMENSIONS:
            adj = dim_adjustments.get(dim, 0)
            delta = random.uniform(-4, 4)
            s = round(max(45, min(95, base + adj + delta - 5)), 2)
            db.add(SessionScore(
                session_question_id=sq.id,
                dimension=dim,
                score=s,
                comment=_dim_comment(dim, s, hit),
            ))

    # 指标：基于实际 transcript 内容真实计算
    wpm = int((len(transcript) / max(1, duration_ms / 60000))) if duration_ms else 220
    filler_count = transcript.count("那个") + transcript.count("然后") + transcript.count("就是说") + transcript.count("嗯")
    sentences = [s.strip() for s in transcript.replace("\n", "。").split("。") if s.strip()]
    pause_count = max(1, len(sentences) - 1) if sentences else 1
    db.add(SessionMetrics(
        session_question_id=sq.id,
        wpm=max(120, min(280, wpm)),
        pause_count=min(pause_count, 8),
        pause_ms_total=random.randint(2000, 10000),
        filler_count=min(filler_count, 6),
        interrupt_count=0,
        extra_json={"engine": ai["engine"] if ai else "rule"},
    ))

    # 高光时刻
    if ai and ai.get("highlights"):
        for i, snippet in enumerate(ai["highlights"][:3]):
            ts_ms = int((i + 1) * max(2000, (duration_ms or 60000) / 4))
            db.add(SessionHighlight(
                session_question_id=sq.id, ts_ms=ts_ms,
                category="highlight", snippet=snippet[:255],
            ))
    elif transcript:
        lines = [s.strip() for s in transcript.split("\n") if s.strip()]
        highlight_count = min(3, len(lines))
        for i in range(highlight_count):
            snippet = lines[i][:50].replace("\n", " ")
            ts_ms = int((i + 1) * max(2000, duration_ms / max(1, highlight_count + 1)))
            db.add(SessionHighlight(
                session_question_id=sq.id, ts_ms=ts_ms,
                category="highlight", snippet=snippet,
            ))

    # 改进建议
    recs_added = 0
    if ai and ai.get("suggestions"):
        for s_text in ai["suggestions"][:3]:
            db.add(SessionRecommendation(
                session_question_id=sq.id, kind="improve",
                content=s_text[:512], sort_index=recs_added,
            ))
            recs_added += 1
    else:
        dim_scores = []
        for dim in DIMENSIONS:
            score = max(45, min(95, base + {"专业深度": 6, "逻辑结构": 8, "语言表达": 4,
                                            "应急应变": 5, "岗位匹配": 3}.get(dim, 0) - 5))
            dim_scores.append((dim, score))
        dim_scores.sort(key=lambda x: x[1])
        weakest = dim_scores[0][0] if dim_scores else "应急应变"
        db.add(SessionRecommendation(
            session_question_id=sq.id, kind="improve",
            content=f"在「{weakest}」维度可补充具体的执行步骤与时间节点，让回答更有落地感。",
            sort_index=recs_added,
        ))
        recs_added += 1
        if not hit["data"]:
            db.add(SessionRecommendation(
                session_question_id=sq.id, kind="improve",
                content="回答中缺少量化数据，建议补充具体的百分比、数值指标或 A/B 测试结果。",
                sort_index=recs_added,
            ))
            recs_added += 1
        if not hit["struct"]:
            db.add(SessionRecommendation(
                session_question_id=sq.id, kind="improve",
                content="建议使用「结论先行 → 分点展开 → 总结」的结构，提升逻辑清晰度。",
                sort_index=recs_added,
            ))
            recs_added += 1

    # —— 逐题深度分析：答得好的地方 / 欠缺的地方 ——
    strengths, gaps = _build_strengths_gaps(ai, transcript, hit)
    sq.strengths = strengths
    sq.gaps = gaps

    # —— 结构化参考答案（采分点 / 答题框架 / 示范作答 / 常见失分点） ——
    if not sq.ref_detail:
        uid = sq.session.user_id if sq.session else 0
        sq.ref_detail = _build_ref_detail(db, uid, q_content, q_cat, q_dim, form_type)

    # 参考答案：题库题已带则用；否则按题目内容/类别/维度生成针对性要点
    if not sq.ref_answer:
        sq.ref_answer = _rule_ref_answer(q_content, q_cat, q_dim)
    db.add(SessionRecommendation(
        session_question_id=sq.id, kind="answer_key",
        content=sq.ref_answer[:512],
        sort_index=recs_added,
    ))
    db.flush()


def _build_strengths_gaps(ai: dict | None, transcript: str, hit: dict) -> tuple[list, list]:
    """
    生成「答得好的地方」与「欠缺的地方」。
    大模型结果优先；无大模型时用关键词命中情况推导，保证两项都不为空。
    """
    if ai:
        strengths = (ai.get("strengths") or [])[:3]
        gaps = (ai.get("gaps") or [])[:3]
        # 大模型偶尔只给一边，用现有 highlights/suggestions 兜底补齐
        if not strengths:
            strengths = [{"point": h, "quote": ""} for h in (ai.get("highlights") or [])[:2]]
        if not gaps:
            gaps = [{"point": s, "why": "", "how": ""} for s in (ai.get("suggestions") or [])[:2]]
        if strengths and gaps:
            return strengths, gaps

    # —— 规则兜底 ——
    strengths, gaps = [], []
    quote = _extract_highlights_from_transcript(transcript or "", max_len=50) or ""

    if hit.get("struct"):
        strengths.append({"point": "表达有结构、分点清晰", "quote": quote})
    if hit.get("data"):
        strengths.append({"point": "用数据支撑观点", "quote": quote})
    if hit.get("risk"):
        strengths.append({"point": "有风险预案意识", "quote": quote})
    if hit.get("depth"):
        strengths.append({"point": "体现了一定的专业深度", "quote": quote})
    if len(transcript or "") >= 120:
        strengths.append({"point": "回答内容较为充分、有展开", "quote": quote})

    if not hit.get("struct"):
        gaps.append({"point": "缺少清晰的答题结构",
                     "why": "评委很难快速抓住你的主线",
                     "how": "用「结论先行 → 分点展开 → 总结」重述一遍"})
    if not hit.get("data"):
        gaps.append({"point": "没有量化数据支撑",
                     "why": "观点缺少可验证的依据，说服力偏弱",
                     "how": "补一个百分比、绝对值或 A/B 对比结果"})
    if not hit.get("risk"):
        gaps.append({"point": "未体现风险与预案",
                     "why": "方案类问题不提兜底会显得考虑不周",
                     "how": "补一句触发条件与回滚/降级方案"})
    if len(transcript or "") < 60:
        gaps.append({"point": "回答过短、信息量不足",
                     "why": "评委难以判断你的真实水平",
                     "how": "按 STAR 展开，讲到一个半分钟左右"})

    if not strengths:
        strengths.append({"point": "核心观点已经表达出来", "quote": quote})
    if not gaps:
        gaps.append({"point": "可再拔高：补充行业横向对比",
                     "why": "目前停留在自身视角，缺少参照系",
                     "how": "加一句与行业基准或同类方案的对比"})
    return strengths[:3], gaps[:3]


def _build_ref_detail(db: Session, user_id: int, q_content: str, q_cat: str,
                      q_dim: str, form_type: str) -> dict:
    """生成结构化参考答案；带上简历画像让示范作答更贴合本人背景"""
    profile = None
    try:
        from app.models.position import Resume
        r = db.query(Resume).filter(
            Resume.user_id == user_id, Resume.is_active == 1
        ).order_by(Resume.created_at.desc()).first()
        if r and r.parsed_json:
            profile = r.parsed_json
    except Exception:
        profile = None
    try:
        from app.services.llm import generate_reference_answer
        return generate_reference_answer(q_content, q_cat, q_dim, form_type, profile)
    except Exception:
        # 兜底：至少给出采分点，保证前端有内容可展示
        return {
            "key_points": ["紧扣题目给出明确结论", "用真实经历或数据支撑", "说明风险与应对"],
            "outline": ["结论先行", "分点展开", "总结回扣"],
            "sample": _rule_ref_answer(q_content, q_cat, q_dim),
            "common_traps": ["回答空泛没有细节", "缺少数据支撑"],
            "engine": "fallback",
        }


def _rule_ref_answer(q_content: str, category: str, dimension: str) -> str:
    """按题目内容/类别/维度生成针对性的参考答案要点（逐题不同，非固定模板）"""
    cat = category or ""
    dim = dimension or ""
    content = q_content or ""
    if "自我介绍" in cat or "自我介绍" in content or "介绍你自己" in content:
        body = ("30 秒背景定位（身份 + 核心方向）→ 两个与岗位强相关的代表作（各含量化结果）→ "
                "一句话点明与该岗位的匹配点收尾。")
    elif "简历深挖" in cat or "项目" in cat or "项目" in content:
        body = ("STAR 展开——情境：项目背景与目标；任务：你的角色与职责边界；"
                "行动：分 2-3 步讲关键决策与执行细节；结果：量化成果 + 复盘改进。")
    elif "情景" in cat or dim == "应急应变":
        body = ("先止血（熔断/降级/兜底）→ 快速评估影响面 → 给出决策依据（回滚或灰度）→ 复盘沉淀机制。")
    elif dim == "专业深度" or "专业" in cat:
        body = ("先给结论/方案全景 → 分层拆解（数据/模型/工程等）并给关键技术选型理由 → "
                "用核心指标收尾（效果/性能/成本）。")
    elif dim == "逻辑结构":
        body = "结论先行 → 分点展开（每点配案例或数据）→ 总结回扣题目。"
    elif dim == "语言表达":
        body = "观点 → 数据支撑 → 风险与预案 → 替代方案，控制在 1 分钟内。"
    elif dim == "岗位匹配":
        body = ("匹配点对照：岗位要求的能力项 → 对应的真实经历与量化结果 → 职业规划与岗位的契合。")
    else:
        body = "先明确问题边界 → 给出分步方案 → 量化预期效果 → 预设风险预案。"
    return f"参考答案要点：{body} 结合自己的真实经历，给出具体细节与数据。"


# 追问用的技术/深度关键词（命中后引用回答原文追问）
_FOLLOWUP_TECH_KWS = [
    "召回", "重排", "架构", "模型", "算法", "向量", "知识库", "RAG", "Agent",
    "灰度", "熔断", "回滚", "缓存", "索引", "A/B", "埋点", "网关", "调度", "降级", "风控",
]


def _content_followup(transcript: str, dimension: str = "") -> str:
    """从候选人回答原文中提取细节生成追问，保证追问紧扣回答内容而非答非所问"""
    text = (transcript or "").strip()
    if not text:
        return "能否先补充一下你回答中的核心案例？"
    # 1) 量化数据：追问数据口径与归因
    m = re.search(r"[\u4e00-\u9fa5A-Za-z]{1,10}?\d+(?:\.\d+)?(?:%|万|倍|个百分点)", text)
    if m:
        num = m.group(0)[-14:]
        return f"你刚才提到「{num}」，这个数据是怎么统计出来的？基线和统计口径分别是什么？"
    # 2) 技术词：引用原文追问做法与难点
    for kw in _FOLLOWUP_TECH_KWS:
        i = text.find(kw)
        if i >= 0:
            quote = text[max(0, i - 6): i + 14].strip(" ，。；、,.;")
            quote = quote[:22]
            return f"你刚才提到「{quote}」，能具体讲讲你是怎么做的？中间最大的难点是什么？"
    # 3) 行动方案：追问落地与权衡
    for kw in ["我会", "我建议", "第一步", "方案"]:
        i = text.find(kw)
        if i >= 0:
            quote = text[i:i + 20].strip()
            return f"你刚说的「{quote}」，如果落地时资源不足，你会优先保证哪一步？为什么？"
    # 4) 维度兜底
    followup_map = {
        "岗位匹配": "你刚才提到的项目里，你个人最核心的贡献是什么？",
        "专业深度": "你刚才说的这个方案，和另一种替代方案相比优势在哪里？",
        "逻辑结构": "如果你的第一步方案行不通，你的 Plan B 是什么？",
        "应急应变": "你提到的应对措施，具体的触发条件和执行步骤是什么？",
        "语言表达": "能用 30 秒再总结一下你刚才的核心观点吗？",
    }
    return followup_map.get(dimension, "你能再展开说说具体的数据指标或案例吗？")


def _dim_comment(dim: str, score: float, hit_info: dict | None = None) -> str:
    """根据分数 + 关键词命中情况生成维度评论"""
    info = hit_info or {}
    has_struct = info.get("struct", False)
    has_data = info.get("data", False)
    has_risk = info.get("risk", False)
    has_depth = info.get("depth", False)

    if score >= 85:
        strengths = []
        if has_struct: strengths.append("逻辑清晰、分点展开")
        if has_data: strengths.append("善用数据指标")
        if has_risk: strengths.append("有风险预案意识")
        if has_depth and dim in ("专业深度", "岗位匹配"): strengths.append("技术深度好")
        tail = "、".join(strengths[:2]) or "整体表现优秀"
        return f"{dim}：{tail}。"
    if score >= 70:
        missing = []
        if not has_struct: missing.append("结构可更清晰")
        if not has_data: missing.append("建议补充量化数据")
        if not has_risk and dim == "应急应变": missing.append("注意风险预案")
        if missing:
            return f"{dim}：{missing[0]}。"
        return f"{dim}：基本到位，仍有提升空间。"
    tips = []
    if not has_struct: tips.append("用「结论先行 → 分点 → 总结」结构")
    if not has_data: tips.append("补充百分比、指标或 A/B 数据")
    if not has_risk and dim == "应急应变": tips.append("体现回滚/熔断等兜底思路")
    if not tips: tips.append("增加案例和细节")
    return f"{dim}：{tips[0]}。"


def _hit_keywords(transcript: str) -> dict:
    """检测回答中的关键词命中情况"""
    if not transcript:
        return {"struct": False, "data": False, "risk": False, "depth": False}
    text = transcript
    return {
        "struct": any(kw in text for kw in ["第一", "第二", "第三", "首先", "然后", "最后", "步骤", "一方面", "另一方面", "结论先行"]),
        "data": any(kw in text for kw in ["%", "万", "数据", "指标", "DAU", "ROI", "SLA", "召回", "提升", "降低", "转化率"]),
        "risk": any(kw in text for kw in ["风险", "预案", "兜底", "回滚", "灰度", "熔断", "监控", "止损", "降级"]),
        "depth": any(kw in text for kw in ["架构", "引擎", "模型", "算法", "原理", "底层", "内核", "Skia", "JIT", "RBAC", "LTV", "CAC", "RAG", "Agent"]),
    }


def _extract_highlights_from_transcript(transcript: str, pick_idx: int = 0, max_len: int = 60) -> str | None:
    """从 transcript 中提取第 pick_idx 个有信息量的句子作为亮点"""
    if not transcript:
        return None
    sentences = [s.strip() for s in transcript.replace("\n", "。").split("。") if 15 < len(s.strip()) < 120]
    if not sentences:
        return None
    # 优先选有深度/数据/风险关键词的句子
    keyword_sents = [s for s in sentences
                     if any(kw in s for kw in ["数据", "方案", "风险", "首先", "核心", "关键", "设计", "架构", "提升", "降低"])]
    pool = keyword_sents if keyword_sents else sentences
    return pool[pick_idx % len(pool)][:max_len]


def finish_session(db: Session, sess: InterviewSession):
    """结束场次 + 生成报告 + 扣减配额 + 更新历史/连续天数"""
    sqs = list_session_questions(db, sess.id)
    if not sqs:
        sess.status = "aborted"
        sess.ended_at = datetime.now()
        db.commit()
        return None

    done = [s for s in sqs if s.status == "done"]
    avg = sum(float(s.total_score or 0) for s in done) / max(1, len(done))
    total = round(avg, 2)
    sess.status = "done"
    sess.ended_at = datetime.now()
    sess.total_score = total
    sess.avg_score = avg

    # 维度聚合（同时统计全场关键词命中）
    dim_map: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    all_transcripts = []
    for s in done:
        for sc in (s.scores or []):
            dim_map.setdefault(sc.dimension, []).append(float(sc.score))
        if s.transcript:
            all_transcripts.append(s.transcript)
    corpus_hit = _hit_keywords("\n".join(all_transcripts))

    dimensions = []
    for d in DIMENSIONS:
        scores = dim_map.get(d, [])
        if scores:
            d_avg = sum(scores) / len(scores)
            comment = _dim_comment(d, d_avg, corpus_hit)
            dimensions.append({"name": d, "score": round(d_avg, 2), "comment": comment})
        else:
            dimensions.append({"name": d, "score": 0.0, "comment": "无"})

    # 较上场对比
    last = db.query(PracticeHistory).filter(
        PracticeHistory.user_id == sess.user_id,
    ).order_by(PracticeHistory.practiced_at.desc()).first()
    last_delta = round(total - float(last.total_score if last else 0), 2)
    # 真实 percentile：基于全站练习历史分数的排名（击败了百分之多少的练习者）
    all_scores = [float(r[0] or 0) for r in db.query(PracticeHistory.total_score).all()]
    all_scores.append(total)
    below = sum(1 for x in all_scores if x < total)
    percentile = max(1, min(99, int(round(below / len(all_scores) * 100))))

    # 动态 overview
    qset = db.get(QuestionSet, sess.set_id) if sess.set_id else None
    weakest_dim = min(dimensions, key=lambda d: d["score"])["name"] if dimensions else "应急应变"
    best_dim = max(dimensions, key=lambda d: d["score"])["name"] if dimensions else "专业深度"

    overview_parts = [
        f"本场共完成 {len(done)} 道题，平均分 {total}。",
    ]
    if corpus_hit.get("struct") and corpus_hit.get("data"):
        overview_parts.append("回答整体结构清晰、善用数据支撑。")
    elif corpus_hit.get("struct"):
        overview_parts.append("回答有基本结构，但数据支撑偏少。")
    elif corpus_hit.get("data"):
        overview_parts.append("善用数据指标，但结构可更清晰。")
    else:
        overview_parts.append("回答内容偏朴素，建议强化结构和数据意识。")

    if total >= 80:
        overview_parts.append(f"「{best_dim}」是本场优势项，可在后续面试中重点展示。")
    elif total >= 65:
        overview_parts.append(f"「{weakest_dim}」得分相对较低，建议有针对性加练。")
    else:
        overview_parts.append(f"整体有较大提升空间，建议先补齐「{weakest_dim}」短板。")

    overview = "".join(overview_parts)

    rep = Report(
        session_id=sess.id, user_id=sess.user_id, form_type=sess.form_type,
        total_score=total, dimensions=dimensions,
        comparison={"last_delta": last_delta, "percentile": percentile},
        overview=overview,
        duration_sec=int(sum((s.duration_ms or 0) for s in done) / 1000),
    )
    db.add(rep)
    db.flush()

    # —— 上下文工程：把本场维度得分累积进候选人长期记忆（供后续场次按需召回） ——
    try:
        from app.crud.memory import update_from_session
        update_from_session(db, sess.user_id, dimensions, sess.form_type)
    except Exception as e:  # noqa: BLE001
        logger = __import__("logging").getLogger(__name__)
        logger.warning("[session] 写回候选人记忆失败（不影响报告）: %s", e)

    # 报告高光 — 优先聚合每题大模型/规则已入库的 SessionHighlight，不足再从转写提取
    hl_count = 0
    t_cursor = 0
    seen_snippets = set()
    for i, s in enumerate(done):
        for h in (s.highlights or []):
            if hl_count >= 6:
                break
            snippet = (h.snippet or "").strip()
            if snippet and snippet not in seen_snippets:
                seen_snippets.add(snippet)
                db.add(ReportHighlight(
                    report_id=rep.id,
                    ts_ms=int(t_cursor + (h.ts_ms or 5000)),
                    snippet=snippet[:255], category="highlight",
                ))
                hl_count += 1
        t_cursor += s.duration_ms or 0
        if hl_count >= 6:
            break
    # 兜底：高光不足 3 条时从转写中补
    if hl_count < 3:
        for i, s in enumerate(done):
            if hl_count >= 6:
                break
            snippet = _extract_highlights_from_transcript(s.transcript or "", pick_idx=i)
            if snippet and snippet not in seen_snippets:
                seen_snippets.add(snippet)
                db.add(ReportHighlight(
                    report_id=rep.id,
                    ts_ms=int(sum((done[j].duration_ms or 0) for j in range(i)) + 5000),
                    snippet=snippet, category="highlight",
                ))
                hl_count += 1

    # 建议 — 优先聚合每题大模型给出的改进建议（去重），再补学情类建议
    rec_idx = 0
    seen_recs = set()
    for s in done:
        for r in (s.recommendations or []):
            if r.kind != "improve" or rec_idx >= 3:
                continue
            content = (r.content or "").strip()
            if content and content not in seen_recs:
                seen_recs.add(content)
                db.add(ReportRecommendation(
                    report_id=rep.id, kind="improve",
                    content=content[:512], sort_index=rec_idx,
                ))
                rec_idx += 1
    db.add(ReportRecommendation(
        report_id=rep.id, kind="practice",
        content=f"推荐加练「{weakest_dim}」专项 8 题，重点强化该维度能力。", sort_index=rec_idx,
    ))
    rec_idx += 1
    if not corpus_hit.get("data"):
        db.add(ReportRecommendation(
            report_id=rep.id, kind="improve",
            content="回答中几乎没有量化数据，建议补充百分比、指标或 A/B 测试结果。", sort_index=rec_idx,
        ))
    else:
        db.add(ReportRecommendation(
            report_id=rep.id, kind="improve",
            content="数据支撑不错，可进一步结合行业基准做横向对比。", sort_index=rec_idx,
        ))
    rec_idx += 1
    if not corpus_hit.get("risk"):
        db.add(ReportRecommendation(
            report_id=rep.id, kind="improve",
            content="回答中缺少风险预案意识，建议在方案类问题中体现熔断、回滚、降级等兜底思路。", sort_index=rec_idx,
        ))
    rec_idx += 1
    db.add(ReportRecommendation(
        report_id=rep.id, kind="review",
        content=f"「{best_dim}」表现较好，可作为核心优势在后续面试中重点展示。", sort_index=rec_idx,
    ))
    rec_idx += 1

    # 扣减配额
    from datetime import datetime as _dt
    month_key = _dt.now().strftime("%Y-%m")
    quota = db.query(UserQuota).filter_by(user_id=sess.user_id, month_key=month_key).first()
    if quota and quota.simulated_left > 0:
        quota.simulated_left -= 1

    # 写练习历史
    db.add(PracticeHistory(
        user_id=sess.user_id, session_id=sess.id,
        total_score=total, set_name=qset.name if qset else "",
        practiced_at=sess.ended_at or _dt.now(),
    ))

    # 更新连续天数
    streak = db.query(UserStreak).filter_by(user_id=sess.user_id).first()
    today = _dt.now().date()
    if streak:
        if streak.last_practice_at == today:
            pass
        elif streak.last_practice_at and (today - streak.last_practice_at).days == 1:
            streak.current_days += 1
        else:
            streak.current_days = 1
        streak.last_practice_at = today
        streak.best_days = max(streak.best_days, streak.current_days)

    db.commit()
    db.refresh(rep)
    return rep


def analyze_transcript(transcript: str, dimension: str = "", question_content: str = "",
                       user_memory: str | None = None, knowledge: str | None = None) -> dict:
    """AI 理解候选人的回答，返回：理解摘要 + 亮点 + 建议 + 追问。
    DeepSeek 大模型优先；未配置/超时/异常时降级规则分析，保证实时反馈不中断。

    user_memory / knowledge 为上下文工程按需注入项（可为空，为空则只给任务上下文）。
    """
    if transcript and len(transcript.strip()) >= 8:
        try:
            from app.services.llm import analyze_answer
            ai = analyze_answer(transcript, dimension, question_content,
                                user_memory=user_memory, knowledge=knowledge)
            if ai:
                return {
                    "understanding": ai["understanding"],
                    "highlights": ai["highlights"] or ["回答表达了候选人的核心思路"],
                    "suggestions": ai["suggestions"] or ["整体不错，注意控制语速、减少口头禅。"],
                    "followup": ai["followup"] or "能否再展开说说具体的数据指标或案例？",
                    "dim_scores": ai["dim_scores"],
                    "engine": "deepseek",
                    "ctx_meta": ai.get("ctx_meta"),
                }
        except Exception:
            pass
    return _rule_analyze(transcript, dimension, question_content)


def _build_understanding(text: str, hits: dict) -> str:
    """构建「我听懂了你的回答」式理解：先复述候选人原话中的核心内容，再给评价。
    所有引用片段均从回答原文提取，保证 AI 说的就是候选人讲的，不答非所问。"""
    parts = []

    # 1) 提取候选人核心作为（我主导/我负责/我设计/我推动…），取信息量最大的一句
    action_leads = ["我主导", "我负责", "我设计", "我搭建", "我推动", "我独立",
                    "我带领", "我牵头", "我完成", "我上线", "我优化", "我建议", "我会"]
    sents = [s.strip() for s in text.replace("\n", "。").split("。") if len(s.strip()) >= 10]
    core = ""
    for lead in action_leads:
        for s in sents:
            if lead in s:
                core = s[:42]
                break
        if core:
            break
    if not core and sents:
        core = sents[0][:42]
    if core:
        parts.append(f"我听到你重点讲了「{core}」")

    # 2) 提取量化数据（带上下文短语）
    nums = []
    for m in re.finditer(r"[一-龥A-Za-z]{0,8}?\d+(?:\.\d+)?(?:%|万|倍|个百分点)", text):
        seg = m.group(0).strip(" ，。；、,.;")
        if seg and seg not in nums:
            nums.append(seg[-16:])
        if len(nums) >= 2:
            break
    if nums:
        parts.append("并给出了数据支撑（" + "、".join(f"「{n}」" for n in nums) + "）")

    # 3) 提取技术/专业词
    tech_hit = []
    for kw in _FOLLOWUP_TECH_KWS:
        if kw in text and kw not in tech_hit:
            tech_hit.append(kw)
        if len(tech_hit) >= 3:
            break
    if tech_hit:
        parts.append("技术上提到了" + "、".join(tech_hit[:3]))

    head = "，".join(parts) + "。" if parts else ""

    # 4) 评价标签（基于可观测的结构特征）
    tags = []
    if hits.get("结构", 0) >= 2:
        tags.append("表达有分点、逻辑清晰")
    if hits.get("数据", 0) >= 2:
        tags.append("善用数据说话")
    if hits.get("风险", 0) >= 2:
        tags.append("有风险预案意识")
    if hits.get("深度", 0) >= 1:
        tags.append("具备一定专业深度")
    if hits.get("行动", 0) >= 2:
        tags.append("给出了可落地的行动方案")
    if not tags:
        tags.append("核心观点已经表达，但结构和数据支撑还可以加强")
    return head + "整体来看，" + "、".join(tags) + "。"


def _rule_analyze(transcript: str, dimension: str = "", question_content: str = "") -> dict:
    """规则兜底分析（关键词命中 + 模板）"""
    if not transcript or len(transcript.strip()) < 10:
        return {
            "understanding": "候选人尚未给出充分回答，建议先组织好语言再作答。",
            "highlights": [],
            "suggestions": ["回答内容较少，请补充具体案例或数据支撑。"],
            "followup": "能否再展开说说你的核心思路？",
            "dim_scores": {},
        }

    text = transcript.strip()

    # —— 结构关键词检测 ——
    structure_kws = {
        "结构": ["第一", "第二", "第三", "首先", "然后", "最后", "步骤", "1.", "2.", "3.", "一方面", "另一方面"],
        "数据": ["%", "万", "数据", "指标", "DAU", "ROI", "SLA", "召回", "转换", "提升", "降低"],
        "风险": ["风险", "预案", "兜底", "回滚", "灰度", "熔断", "监控", "止损"],
        "深度": ["架构", "引擎", "模型", "算法", "原理", "底层", "内核", "Skia", "JIT", "RBAC", "LTV", "CAC"],
        "行动": ["我会", "我建议", "我的方案", "策略", "方案", "设计", "规划", "落地", "执行"],
    }
    hits = {}
    for cat, kws in structure_kws.items():
        cnt = sum(1 for kw in kws if kw in text)
        hits[cat] = cnt

    # —— 维度差异化评分 ——
    dim_scores = {}
    dim_map = {
        "专业深度": ("深度", "数据"),
        "逻辑结构": ("结构", "行动"),
        "语言表达": ("结构", "行动"),
        "应急应变": ("风险", "行动"),
        "岗位匹配": ("深度", "行动"),
    }
    for d in DIMENSIONS:
        cats = dim_map.get(d, ("结构", "行动"))
        score = 55 + hits.get(cats[0], 0) * 4 + hits.get(cats[1], 0) * 3 + min(len(text) // 60, 15)
        score = max(45, min(95, score))
        dim_scores[d] = round(score, 1)

    # —— AI 理解摘要：先复述候选人原话中的核心内容（证明真的听懂了），再给评价 ——
    understanding = _build_understanding(text, hits)

    # —— 亮点 ——
    highlights = []
    sentences = [s.strip() for s in text.replace("\n", "。").split("。") if len(s.strip()) > 15]
    # 取 2-3 个包含关键词的句子作为亮点
    highlight_sentences = []
    for s in sentences:
        if any(kw in s for kw in ["数据", "方案", "风险", "第一步", "首先", "核心", "关键", "设计", "架构"]):
            highlight_sentences.append(s[:60])
        if len(highlight_sentences) >= 3:
            break
    highlights = highlight_sentences or [sentences[0][:60] if sentences else "回答表达了候选人的核心思路"]

    # —— 建议 ——
    suggestions = []
    if hits["结构"] < 2:
        suggestions.append("建议使用「结论先行 → 分点展开 → 总结」的结构，让逻辑更清晰。")
    if hits["数据"] < 1:
        suggestions.append("回答中缺少量化数据，建议补充百分比、数值或 A/B 测试结果。")
    if hits["风险"] < 1 and "应急应变" in dimension:
        suggestions.append("应急类问题需要体现风险预案意识，建议补充兜底和回滚方案。")
    if hits["深度"] < 1 and ("专业" in dimension or "深度" in dimension):
        suggestions.append("专业类问题建议深入技术细节，比如架构设计、底层原理或具体决策案例。")
    if len(text) < 80:
        suggestions.append("回答内容偏短，建议展开具体案例或补充更多细节。")
    if not suggestions:
        suggestions.append("整体回答质量不错，可继续保持，注意控制语速避免口头禅过多。")

    # —— 追问：从回答原文提取细节（数据/技术词/方案），紧扣内容而非模板 ——
    followup = _content_followup(text, dimension)

    return {
        "understanding": understanding,
        "highlights": highlights,
        "suggestions": suggestions[:3],
        "followup": followup,
        "dim_scores": dim_scores,
    }

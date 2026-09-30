# -*- coding: utf-8 -*-
"""
量化评测集与评测执行器（对应标准④：建立量化评测指标）

为什么需要它：
- Phase 2 让 LLM 调用「会重试、会校验」，Phase 3 让上下文「按需注入」，
  但**改动到底有没有变好、稳不稳定、贵不贵**，必须靠固定评测集重复跑才有结论；
- 评测口径固定为 5 个指标：成功率、稳定性（同一样本重复跑的分数标准差/极差）、
  耗时（均值/P95）、Token 成本、降级率。

两种运行模式：
- **离线模式（offline=True，默认）**：注入一个确定性的假 LLM（带可控抖动），
  不联网、不烧钱、结果可复现 —— 用于回归验证「流水线本身」是否正确、稳定；
- **真实模式（offline=False）**：走真实 DeepSeek，Token/成本从 `llm_call_log` 实取
  （按本次 run 的 trace_id 汇总）—— 用于评估「模型效果与真实成本」。

铁律：评测失败不影响业务；所有写库异常只记录不抛出到调用方之外。
"""
from __future__ import annotations

import json
import statistics
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger, request_id_var
from app.models.observability import EvalRun, EvalSample
from app.services.metrics import percentile

log = get_logger("eval")

# 本次评测运行的 trace（真实模式下用于汇总真实 token/成本）
_eval_trace_var: ContextVar[str] = ContextVar("eval_trace", default="-")


# ————————————————————————————————————————————————
# 固定评测样本集
# ————————————————————————————————————————————————
# expected_lo/hi = 期望分数带，用于「一致性」判定（落带内说明评分尺度没有跑偏）；
# 最后一条是**边界样本**（作答过短），期望拿不到分，用来验证评测器能识别出降级/失败。
SAMPLES: list[dict] = [
    {
        "name": "高质量·有数据有结构",
        "question": "请介绍一个你主导过的项目，并说明你的具体贡献。",
        "dimension": "专业深度", "category": "项目经历",
        "transcript": (
            "我主导过一次推荐系统的召回优化。首先我拆分了问题：线上 CTR 连续三周下滑 12%，"
            "排查后定位到召回层类目覆盖率不足。其次我做了两版方案对比，最终选择向量召回加类目兜底，"
            "成本可控且能覆盖长尾。执行上分三步：先补数据、再训练、最后灰度。三周上线后，"
            "核心指标 CTR 从 3.1% 提升到 3.9%，长尾曝光占比提升了 18%。如果重来，我会更早做离线评估。"
        ),
        "expected_lo": 78, "expected_hi": 95,
    },
    {
        "name": "中等·切题但缺数据",
        "question": "如果线上服务突然出现大量超时，你会怎么处理？",
        "dimension": "应急应变", "category": "情景题",
        "transcript": (
            "首先我会先确认影响面，看看是全部用户还是部分用户。然后我会去看监控和日志，"
            "定位是哪一层的问题，可能是数据库或者缓存。定位到之后我会修复，"
            "修复完上线观察一段时间，最后再写复盘。"
        ),
        "expected_lo": 62, "expected_hi": 80,
    },
    {
        "name": "较差·内容空洞跑题",
        "question": "请做一个自我介绍。",
        "dimension": "语言表达", "category": "自我介绍",
        "transcript": "我是一个比较认真的人，平时喜欢学习新东西，我觉得自己适应能力还不错，希望可以得到这个机会。",
        "expected_lo": 45, "expected_hi": 68,
    },
    {
        "name": "中等偏上·有结构无量化",
        "question": "说说你的职业规划。",
        "dimension": "岗位匹配", "category": "求职动机",
        "transcript": (
            "短期我希望先把当前岗位的核心业务吃透，在一年内能够独立负责一个完整模块；"
            "中期我希望在数据分析方向形成自己的方法论；长期我希望能够带团队，"
            "把业务理解和技术能力结合起来。我认为这和贵岗位的成长路径是吻合的。"
        ),
        "expected_lo": 62, "expected_hi": 82,
    },
    {
        "name": "高质量·逻辑清晰有取舍",
        "question": "团队对方案有分歧时你怎么推进？",
        "dimension": "逻辑结构", "category": "团队协作",
        "transcript": (
            "我的做法是先统一目标，再讨论手段。第一，我会把双方方案的目标差异摆出来，"
            "确认我们争论的是手段不是目标；第二，我会要求各自给出判断依据和数据假设；"
            "第三，如果数据不足就用最小成本做一版灰度验证。去年一次选型争议，"
            "我们就是靠两周灰度跑出了结论，避免了长时间扯皮。"
        ),
        "expected_lo": 74, "expected_hi": 92,
    },
    {
        "name": "边界·作答过短（预期无分）",
        "question": "请谈谈你的优点。",
        "dimension": "岗位匹配", "category": "自我认知",
        "transcript": "我还行。",
        "expected_lo": None, "expected_hi": None,
    },
]


# ————————————————————————————————————————————————
# 离线假 LLM（确定性 + 可控抖动）
# ————————————————————————————————————————————————
def _fake_score(system: str, user: str, jitter_seed: int = 0) -> dict:
    """按启发式给出一个「像模型」的评分：结构化/量化/长度都会加分，并带 ±3 抖动。

    抖动用 (seed) 决定，保证同一 repeat 可复现 —— 这样稳定性指标才是有意义的
    （若每次都完全相同，std=0 说明测的是假东西；有微小抖动才能看出真实波动量级）。
    """
    text = user
    n = len(text)
    base = 58.0
    if any(k in text for k in ("首先", "其次", "第一", "最后", "分三步", "短期", "中期")):
        base += 9
    if any(ch.isdigit() for ch in text) or "%" in text:
        base += 8
    if n > 220:
        base += 6
    if any(k in text for k in ("提升", "降低", "结果", "指标", "上线", "复盘")):
        base += 5
    if any(k in text for k in ("如果重来", "局限", "风险", "预案")):
        base += 4

    # 确定性抖动：以 seed 为伪随机源，范围 ±3
    jitter = ((jitter_seed * 2654435761) % 1000 / 1000.0) * 6.0 - 3.0
    total = max(45.0, min(95.0, base + jitter))

    dims = ["专业深度", "逻辑结构", "语言表达", "应急应变", "岗位匹配"]
    dim_scores = {}
    for i, d in enumerate(dims):
        v = total + (((jitter_seed + i) * 37) % 11) - 5
        dim_scores[d] = round(max(45.0, min(96.0, v)), 1)
    return {
        "total_score": round(total, 1),
        "dim_scores": dim_scores,
        "dim_comments": {d: "表现稳定" for d in dims},
        "understanding": "候选人围绕题目给出了较完整的作答，包含具体行动与结果。",
        "strengths": [{"point": "结构清晰", "quote": "分点说明了做法"}],
        "gaps": [{"point": "可补充量化结果", "why": "缺少数据支撑", "how": "补充指标口径"}],
        "highlights": ["有具体行动步骤"],
        "suggestions": ["补充量化数据"],
        "followup": "这个结果持续了多久？",
    }


def _make_fake_chat(jitter_seed_ref: list[int]) -> Callable:
    """返回一个可替换 llm._chat_json 的函数（签名兼容 (system, user, timeout=None)）。"""

    def _chat(system_prompt: str, user_prompt: str, timeout: Optional[int] = None):
        # 作答过短的样本：与真实链路一致地返回 None（触发降级/无分）
        body = user_prompt.split("【候选人作答原文】")[-1]
        if len(body.strip()) < 8:
            return None
        return _fake_score(system_prompt, user_prompt, jitter_seed_ref[0])

    return _chat


@contextmanager
def _patch_chat(fn: Optional[Callable]):
    """临时替换 app.services.llm._chat_json（用于离线评测注入假 LLM）。"""
    from app.services import llm as llm_mod
    if fn is None:
        yield
        return
    old = llm_mod._chat_json
    llm_mod._chat_json = fn  # type: ignore[assignment]
    try:
        yield
    finally:
        llm_mod._chat_json = old  # type: ignore[assignment]


# ————————————————————————————————————————————————
# 评测执行
# ————————————————————————————————————————————————
def run_eval(
    db: Session,
    *,
    name: Optional[str] = None,
    samples: Optional[list[dict]] = None,
    repeat: int = 3,
    offline: bool = True,
    chat_fn_factory: Optional[Callable] = None,
    persist: bool = True,
) -> dict:
    """跑一轮量化评测。

    参数：
      db          数据库会话（评测结果落 eval_run / eval_sample）
      samples     评测样本，默认用内置 SAMPLES
      repeat      每个样本重复跑几次（用于测稳定性）
      offline     True=注入确定性假 LLM（不联网、不烧钱、可复现）；False=真实调用
      chat_fn_factory  自定义假 LLM 工厂（receives jitter_seed_ref list）
    返回：报告 dict（同时落库）
    """
    from app.services.llm import score_answer
    from app.services.context import estimate_tokens

    samples = samples or SAMPLES
    repeat = max(1, int(repeat or 1))
    trace_id = "eval-" + uuid.uuid4().hex[:12]
    token = _eval_trace_var.set(trace_id)
    req_token = request_id_var.set(trace_id)   # 真实模式下让本次 run 的调用共享一条 trace

    seed_ref = [0]
    fake_chat = None
    if offline:
        factory = chat_fn_factory or _make_fake_chat
        fake_chat = factory(seed_ref)

    results: list[dict] = []
    rows: list[EvalSample] = []

    try:
        with _patch_chat(fake_chat):
            for si, s in enumerate(samples):
                scores: list[float] = []
                for ri in range(repeat):
                    seed_ref[0] = si * 100 + ri
                    t0 = time.time()
                    ok = False
                    score = None
                    engine = "rule"
                    err = None
                    try:
                        out = score_answer(
                            s["question"], s.get("dimension", ""), s.get("category", ""),
                            s["transcript"], form_type="structured",
                        )
                        if out:
                            ok = True
                            score = float(out.get("total_score"))
                            engine = "fake" if offline else str(out.get("engine") or "deepseek")
                        else:
                            err = "未返回结果（作答过短或模型不可用）"
                    except Exception as e:  # noqa: BLE001 - 单条失败不中断整轮评测
                        err = f"{type(e).__name__}: {e}"
                    latency_ms = int((time.time() - t0) * 1000)

                    lo, hi = s.get("expected_lo"), s.get("expected_hi")
                    in_band = None
                    # 落带率只在真实模式下有意义：离线用的是启发式假 LLM，
                    # 它的绝对分值不代表真实模型水平，拿它比对期望带只会得出误导性结论。
                    if ok and not offline and lo is not None and hi is not None:
                        in_band = 1 if (lo <= score <= hi) else 0
                    if ok and score is not None:
                        scores.append(score)

                    # 离线模式无法取到真实 usage，按上下文估算 token（报告中标注 estimated）
                    est_tokens = estimate_tokens(s["question"] + s["transcript"]) + 400
                    rows.append(EvalSample(
                        run_id=0, sample_idx=si, repeat_idx=ri, sample_name=s.get("name"),
                        ok=1 if ok else 0, score=score,
                        expected_lo=lo, expected_hi=hi, in_band=in_band,
                        latency_ms=latency_ms, total_tokens=est_tokens if offline else None,
                        engine=engine, error=err,
                    ))
                    results.append({"sample_idx": si, "repeat_idx": ri, "ok": ok,
                                    "score": score, "latency_ms": latency_ms,
                                    "engine": engine, "error": err})

    finally:
        _eval_trace_var.reset(token)
        request_id_var.reset(req_token)

    # —— 汇总 ——
    total_runs = len(rows)
    ok_runs = sum(1 for r in rows if r.ok)
    latencies = [float(r.latency_ms or 0) for r in rows]
    per_sample: list[dict] = []
    stds: list[float] = []
    ranges: list[float] = []
    for si, s in enumerate(samples):
        vals = [r.score for r in rows if r.sample_idx == si and r.ok and r.score is not None]
        std = round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0
        rng = round(max(vals) - min(vals), 2) if vals else None
        if len(vals) > 1:
            stds.append(std)
        if rng is not None:
            ranges.append(rng)
        band_hits = [r.in_band for r in rows if r.sample_idx == si and r.in_band is not None]
        per_sample.append({
            "sample_idx": si, "name": s.get("name"),
            "runs": len(vals), "mean_score": round(sum(vals) / len(vals), 2) if vals else None,
            "std": std, "range": rng,
            "expected": [s.get("expected_lo"), s.get("expected_hi")],
            "in_band_rate": (sum(band_hits) / len(band_hits)) if band_hits else None,
            "engine": next((r.engine for r in rows if r.sample_idx == si), None),
        })

    # 真实模式下从 llm_call_log 取本轮真实 token/成本
    real_tokens = None
    real_cost = None
    if not offline:
        try:
            from app.models.observability import LLMCallLog
            from sqlalchemy import func as _f
            agg = db.query(_f.sum(LLMCallLog.total_tokens), _f.sum(LLMCallLog.cost_cny)).filter(
                LLMCallLog.trace_id == trace_id).first()
            if agg:
                real_tokens = int(agg[0] or 0)
                real_cost = round(float(agg[1] or 0.0), 6)
        except Exception as e:
            log.warning("[eval] 汇总真实用量失败: %s", e)

    est_total_tokens = sum(int(r.total_tokens or 0) for r in rows) if offline else (real_tokens or 0)

    report = {
        "run_trace_id": trace_id,
        "scene": "score_answer",
        "offline": bool(offline),
        "sample_count": len(samples),
        "repeat": repeat,
        "total_runs": total_runs,
        "success_rate": round(ok_runs / total_runs, 4) if total_runs else None,
        "fallback_rate": round((total_runs - ok_runs) / total_runs, 4) if total_runs else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p95_latency_ms": percentile(latencies, 95),
        "score_std_avg": round(sum(stds) / len(stds), 3) if stds else 0.0,
        "score_range_max": round(max(ranges), 2) if ranges else None,
        "total_tokens": est_total_tokens,
        "tokens_estimated": bool(offline),
        "cost_cny": real_cost if real_cost is not None else (
            round(est_total_tokens / 1000.0 * 0.004, 6) if offline else 0.0),
        "in_band_rate": _avg([p["in_band_rate"] for p in per_sample if p["in_band_rate"] is not None]),
        # 解读口径说明：避免把离线跑出来的数字当成真实模型水平
        "in_band_note": ("离线模式使用启发式假 LLM，绝对分值与落带率不代表真实模型水平；"
                         "本轮只用于验证流水线正确性与评分稳定性。"),
        "per_sample": per_sample,
        "runs": results,
    }

    if persist:
        try:
            run = EvalRun(
                name=name or ("离线回归评测" if offline else "真实模型评测"),
                scene="score_answer",
                sample_count=len(samples), repeat=repeat, offline=1 if offline else 0,
                success_rate=report["success_rate"],
                avg_latency_ms=report["avg_latency_ms"],
                p95_latency_ms=report["p95_latency_ms"],
                total_tokens=report["total_tokens"],
                cost_cny=report["cost_cny"],
                score_std=report["score_std_avg"],
                score_range=report["score_range_max"],
                report=json.dumps(report, ensure_ascii=False),
            )
            db.add(run)
            db.flush()
            for r in rows:
                r.run_id = run.id
                db.add(r)
            db.commit()
            report["run_id"] = run.id
        except Exception as e:
            log.exception("[eval] 评测结果落库失败（返回报告不受影响）: %s", e)
            try:
                db.rollback()
            except Exception:
                pass

    log.info("[eval] 完成 offline=%s 样本=%s 重复=%s 成功率=%s 分数std=%s P95=%sms",
             offline, len(samples), repeat, report["success_rate"],
             report["score_std_avg"], report["p95_latency_ms"])
    return report


def _avg(xs: list[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 4) if xs else None


def latest_run(db: Session) -> Optional[dict]:
    row = db.query(EvalRun).order_by(EvalRun.id.desc()).first()
    return row.to_dict() if row else None


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(EvalRun).order_by(EvalRun.id.desc()).limit(max(1, min(int(limit or 20), 100))).all()
    return [r.to_dict() for r in rows]


# —— 沙箱自测：离线模式，不联网不烧钱 ——
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    db = sessionmaker(bind=eng, future=True)()

    rep = run_eval(db, repeat=3, offline=True, persist=True)

    print("成功率:", rep["success_rate"], "| 降级率:", rep["fallback_rate"])
    print("平均耗时:", rep["avg_latency_ms"], "ms | P95:", rep["p95_latency_ms"], "ms")
    print("分数标准差均值:", rep["score_std_avg"], "| 最大极差:", rep["score_range_max"])
    print("落带率:", rep["in_band_rate"], "| 估算 tokens:", rep["total_tokens"])
    for p in rep["per_sample"]:
        print(f"  - {p['name']}: 均分={p['mean_score']} std={p['std']} "
              f"期望={p['expected']} 落带率={p['in_band_rate']} engine={p['engine']}")

    # 断言：边界样本（作答过短）必须被识别为失败，证明评测器能发现问题
    edge = rep["per_sample"][-1]
    assert edge["runs"] == 0, "过短作答不应拿到分数"
    assert rep["success_rate"] == round(5 / 6, 4), rep["success_rate"]
    # 断言：稳定性指标被真实计算出来（有抖动 → std > 0）
    assert rep["score_std_avg"] > 0, "假 LLM 带抖动，std 应大于 0"
    # 断言：结果已落库
    assert rep.get("run_id"), "报告应回写 run_id"
    assert latest_run(db) is not None

    print("EVAL_SELFTEST_OK")

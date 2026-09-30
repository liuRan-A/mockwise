# -*- coding: utf-8 -*-
"""
Phase 4（评估与可观测性）量化验证脚本

不联网、不烧钱、不需要 MySQL：用内存 SQLite 建表，注入假 LLM，
验证「落库 → 指标 → 链路 → 评测」四层是否真的通。

运行：
    cd backend
    python scripts/verify_observability.py          # 或 venv312/Scripts/python.exe

验证项：
    T1 用量钩子落库：一次 LLM 调用 → llm_call_log 一行，含 trace_id / scene / ctx_meta / 成本
    T2 上下文元数据一次性消费：挂一次只生效一次，第二次调用不误挂
    T3 指标聚合：成功率 / P95 耗时 / token / 成本 计算正确
    T4 链路还原：span + LLM 调用按同一 trace_id 串起来
    T5 量化评测：固定样本重复跑，能出成功率/稳定性(std,极差)/耗时/成本，且能识别出失败样本
    T6 成本核算：单价配置生效
"""
from __future__ import annotations

import os
import sys

# 保证可以 import app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as dbmod
from app.core.database import Base
from app.core.logging_config import request_id_var, user_id_var
from app.models.observability import LLMCallLog, TraceSpan
from app.services import llm_client, metrics, eval as eval_svc


def hr(title: str) -> None:
    print("\n" + "=" * 62)
    print(f"  {title}")
    print("=" * 62)


def main() -> int:
    # —— 用内存 SQLite 顶替 MySQL（观测写入走 SessionLocal，这里把它换掉）——
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    dbmod.SessionLocal = TestSession          # tracing 内部延迟导入，故改模块属性即可生效
    db = TestSession()

    checks = 0

    # ——————————————————————————————————————————
    hr("T1  用量钩子 → LLM 调用明细落库")
    from app.services import tracing
    tracing.install_usage_hook()   # 把落库钩子挂到 llm_client（真实启动时在 main.py lifespan 里做）

    request_id_var.set("trace-verify-001")
    user_id_var.set("42")
    with tracing.scene("score_answer"):
        tracing.attach_ctx_meta({
            "included_layers": ["task", "knowledge", "user_memory"],
            "context_tokens": 489, "total_tokens": 1289, "over_budget": False,
        })
        # 模拟一次真实调用结束后的用量上报（llm_client 内部就是这么调的）
        llm_client._emit_usage("deepseek-chat", 800, 489, 1234, True)

    rows = db.query(LLMCallLog).all()
    assert len(rows) == 1, f"应落 1 行，实际 {len(rows)}"
    r = rows[0]
    print(f"trace_id={r.trace_id}  scene={r.scene}  model={r.model}")
    print(f"tokens: prompt={r.prompt_tokens} completion={r.completion_tokens} total={r.total_tokens}")
    print(f"latency_ms={r.latency_ms}  cost_cny={r.cost_cny}  user_id={r.user_id}")
    print(f"ctx_meta={r.ctx_meta}")
    assert r.trace_id == "trace-verify-001"
    assert r.scene == "score_answer"
    assert r.user_id == 42
    assert r.total_tokens == 1289
    assert r.ctx_meta and "knowledge" in r.ctx_meta
    checks += 1
    print("  ✓ T1 通过")

    # ——————————————————————————————————————————
    hr("T2  上下文元数据一次性消费（不误挂到下一次调用）")
    with tracing.scene("analyze_answer"):
        llm_client._emit_usage("deepseek-chat", 300, 120, 500, True)
    rows = db.query(LLMCallLog).order_by(LLMCallLog.id.asc()).all()
    assert len(rows) == 2 and rows[1].scene == "analyze_answer", rows[1].scene
    assert rows[1].ctx_meta is None, "第二次调用不应带上一次的 ctx_meta"
    assert rows[0].ctx_meta is not None
    checks += 1
    print("  ✓ T2 通过：元数据挂一次、消费一次")

    # ——————————————————————————————————————————
    hr("T3  指标聚合（成功率 / 分位耗时 / token / 成本）")
    # 再造 3 条：1 条失败、2 条群面场景（不同耗时）
    tracing.record_llm_call(db, model="deepseek-chat", prompt_tokens=600, completion_tokens=200,
                            latency_ms=2100, ok=False, error="timeout", scene_name="score_answer",
                            trace_id="trace-verify-002")
    for lat in (320, 280):
        tracing.record_llm_call(db, model="deepseek-chat", prompt_tokens=400, completion_tokens=150,
                                latency_ms=lat, ok=True, scene_name="group_turn",
                                trace_id="trace-verify-003",
                                ctx_meta={"included_layers": ["task"], "total_tokens": 550,
                                          "over_budget": True})

    ov = metrics.llm_overview(db, hours=24)
    print(f"总调用={ov['total_calls']} 成功={ov['success_calls']} 失败={ov['failed_calls']} "
          f"成功率={ov['success_rate']}")
    print(f"耗时: 均值={ov['avg_latency_ms']}ms  P50={ov['p50_latency_ms']}ms  P95={ov['p95_latency_ms']}ms")
    print(f"tokens={ov['total_tokens']}  成本=¥{ov['cost_cny']}  单次均值=¥{ov['avg_cost_per_call']}")
    assert ov["total_calls"] == 5, ov
    assert ov["success_rate"] == 0.8, ov            # 4 成功 / 5 总
    assert ov["p95_latency_ms"] > ov["avg_latency_ms"], "P95 应大于均值（长尾存在）"
    assert ov["cost_cny"] > 0
    checks += 1
    print("  ✓ T3 通过")

    by = metrics.by_scene(db, hours=24)
    for s in by:
        print(f"  · {s['scene']}: 调用={s['total_calls']} 成功率={s['success_rate']} "
              f"P95={s['p95_latency_ms']}ms tokens={s['total_tokens']}")
    assert {s["scene"] for s in by} == {"score_answer", "analyze_answer", "group_turn"}
    checks += 1
    print("  ✓ 分场景统计通过")

    # ——————————————————————————————————————————
    hr("T4  链路还原（span + LLM 调用串在同一 trace 上）")
    request_id_var.set("trace-verify-003")
    with tracing.span("POST /api/v1/sessions/peer-talk", kind="api"):
        with tracing.span("group_orchestrator.generate_turn", kind="agent"):
            llm_client._emit_usage("deepseek-chat", 400, 150, 350, True)
    td = metrics.trace_detail(db, "trace-verify-003")
    print(f"trace={td['trace_id']}  span 数={td['totals']['span_count']}  "
          f"LLM 调用数={td['totals']['llm_call_count']}")
    print(f"链路合计 tokens={td['totals']['total_tokens']} 成本=¥{td['totals']['cost_cny']} "
          f"LLM 耗时={td['totals']['llm_latency_ms']}ms")
    # 注意：子段先结束先入库，所以按 id 升序时子段在前；这里按父子关系判定，不依赖顺序
    span_ids = {s["span_id"] for s in td["spans"]}
    child = next(s for s in td["spans"] if s["parent_span_id"])
    parent = next(s for s in td["spans"] if s["span_id"] == child["parent_span_id"])
    print(f"  span 链: {parent['name']} → {child['name']}（kind={child['kind']}）")
    assert td["totals"]["span_count"] == 2, td
    assert child["parent_span_id"] in span_ids
    assert "orchestrator" in child["name"] and child["kind"] == "agent", child
    assert parent["kind"] == "api", parent
    assert td["totals"]["llm_call_count"] >= 3, td["totals"]
    checks += 1
    print("  ✓ T4 通过：父子 span 正确、LLM 调用按 trace 汇总")

    # ——————————————————————————————————————————
    hr("T5  量化评测（固定样本重复跑，出稳定性报告）")
    rep = eval_svc.run_eval(db, repeat=3, offline=True)
    print(f"模式={'离线(不烧钱)' if rep['offline'] else '真实'}  样本={rep['sample_count']}  "
          f"重复={rep['repeat']}  总运行={rep['total_runs']}")
    print(f"成功率={rep['success_rate']}   降级率={rep['fallback_rate']}")
    print(f"耗时: 均值={rep['avg_latency_ms']}ms  P95={rep['p95_latency_ms']}ms")
    print(f"评分稳定性: 标准差均值={rep['score_std_avg']}  最大极差={rep['score_range_max']}")
    print(f"落带率={rep['in_band_rate']}（离线模式不参与：{rep['in_band_note'][:24]}…）")
    print(f"估算 tokens={rep['total_tokens']}(估算={rep['tokens_estimated']})")
    print("  逐样本：")
    for p in rep["per_sample"]:
        print(f"    - {p['name']}: 均分={p['mean_score']} std={p['std']} 极差={p['range']} "
              f"期望={p['expected']} 落带率={p['in_band_rate']} engine={p['engine']}")
    assert rep["total_runs"] == 18, rep["total_runs"]
    assert rep["success_rate"] == round(15 / 18, 4), rep["success_rate"]   # 边界样本拿不到分
    assert rep["score_std_avg"] > 0, "有抖动才能测出真实稳定性"
    assert rep["per_sample"][-1]["runs"] == 0, "过短作答应被识别为失败"
    assert rep.get("run_id"), "评测结果应落库"
    checks += 1
    print("  ✓ T5 通过：能出量化指标，也能识别出失败样本")

    latest = eval_svc.latest_run(db)
    assert latest and latest["id"] == rep["run_id"]
    checks += 1
    print(f"  ✓ 评测报告已落库，run_id={latest['id']}")

    # ——————————————————————————————————————————
    hr("T6  上下文工程效果指标（消费 Phase 3 的 ctx_meta）")
    cs = metrics.ctx_stats(db, hours=24)
    print(f"样本={cs['sample_count']}  平均上下文 tokens={cs['avg_context_tokens']}  "
          f"最大={cs['max_context_tokens']}")
    print(f"超预算率={cs['over_budget_rate']}  各层纳入率={cs['layer_hit_rate']}")
    assert cs["sample_count"] >= 3, cs
    assert "task" in cs["layer_hit_rate"]
    checks += 1
    print("  ✓ T6 通过")

    hr(f"Phase 4 验证通过：{checks} 组断言全部 OK")
    print("提示：真实模式下（offline=False）会用真 DeepSeek，Token/成本从 llm_call_log 实取。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

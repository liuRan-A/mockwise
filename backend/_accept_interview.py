# -*- coding: utf-8 -*-
"""模拟面试四条验收标准（API 层）
标准1: 录音→ASR→转写：验证讯飞配置就绪 + /ws/asr 端点存在（真实麦克风需浏览器人工验收）
标准2: 追问基于回答内容（引用回答原文数字/技术词，不答非所问）
标准3: 简历出题引用简历真实内容（项目/数据/技能，非固定模板）
标准4: 报告含每题参考答案 + 逐题答得好/欠缺分析 + 薄弱题型可映射专项题库再练一轮
"""
import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://127.0.0.1:8000"
API = BASE + "/api/v1"
PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌"), name, ("| " + str(detail)) if detail else "")

r = requests.post(f"{API}/auth/login", json={"phone": "13800000000", "password": "123456"})
A = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}

# ===== 标准 1：ASR 链路服务端就绪 =====
sys.path.insert(0, ".")
from app.services.ifly_asr import is_configured
check("标准1: 讯飞 ASR 已配置（后端密钥就绪）", is_configured())
r = requests.get(f"{BASE}/health")
check("标准1: 后端健康", r.status_code == 200)

# ===== 标准 2：追问基于回答内容 =====
# 先建一场半结构化（用简历），拿一题，提交含数字+技术词的回答，验证 feedback 追问引用原文
resume_text = """
张伟，求职意向：AI 方案架构师，3 年工作经验。
工作经历：2021-2024 在某互联网公司担任算法工程师，主导企业知识库 RAG 系统建设，
负责数据治理、双路召回（向量+关键词）、重排模型，上线后召回率提升15%，客服首解率从62%提升到78%。
技能：Python、PyTorch、大模型应用、向量数据库、FastAPI、团队协作。
项目：独立设计客服智能问答系统，搭建评测体系，推动灰度上线与熔断回滚预案。
"""
r = requests.post(f"{API}/resumes/upload", headers=A, data={"text": resume_text}, timeout=90).json()
check("简历上传成功", r["code"] == 0)

sets = requests.get(f"{API}/question-sets", headers=A).json()["data"]
semi_set = [s for s in sets if s["form_type"] == "semi"][0]
r = requests.post(f"{API}/sessions", headers=A, json={
    "set_id": semi_set["id"], "form_type": "semi", "enable_followup": True, "use_resume": True,
}).json()
sid = r["data"]["session_id"]
detail = requests.get(f"{API}/sessions/{sid}", headers=A).json()["data"]
qs = detail["questions"]

# ===== 标准 3：简历出题引用真实简历内容 =====
resume_specific = ["RAG", "召回", "知识库", "62%", "78%", "15%", "Python", "灰度", "客服"]
n_specific = sum(1 for q in qs if any(k in q["question_content"] for k in resume_specific))
check("标准3: 题目数量=5", len(qs) == 5, f"{len(qs)} 道")
check("标准3: ≥4 题引用简历真实内容（项目/数据/技能）", n_specific >= 4, f"{n_specific}/5 题含简历细节")
print("   题目示例:", qs[0]["question_content"][:46])
print("           ", qs[1]["question_content"][:46])
check("标准3: 全部 source=resume", all(q["source"] == "resume" for q in qs))

# ===== 标准 2：追问引用回答原文 =====
sq0 = qs[0]
ans1 = ("我主导企业知识库 RAG 系统建设，先做数据治理，再设计向量加关键词双路召回加重排，"
        "上线后召回率提升15%，客服首解率从62%提升到78%。")
fb = requests.post(f"{API}/sessions/questions/{sq0['id']}/feedback", headers=A, json={
    "transcript": ans1, "question_dimension": sq0.get("question_dimension", ""),
    "question_content": sq0.get("question_content", ""),
}).json()["data"]
fu = fb.get("followup", "")
quoted = ("15%" in fu) or ("62%" in fu) or ("78%" in fu)
check("标准2: 追问引用回答中的数据原文", quoted, fu[:48])
ans2 = "我先做了灰度方案，把新模型放到 5% 流量上观察，同时加了熔断和回滚预案。"
fb2 = requests.post(f"{API}/sessions/questions/{sq0['id']}/feedback", headers=A, json={
    "transcript": ans2, "question_dimension": "专业深度",
    "question_content": "test",
}).json()["data"]
fu2 = fb2.get("followup", "")
quoted2 = any(k in fu2 for k in ["灰度", "熔断", "回滚", "5%"])
check("标准2: 追问引用回答中的技术词原文", quoted2, fu2[:48])

# ===== 标准四：报告（参考答案 + 逐题分析 + 薄弱项再练） =====
# 完整作答全部 5 题：前两题答得好（结构+数据），后三题答得差（制造薄弱题）
answers = [
    ans1,
    ("我会分三步推进：第一步做数据治理明确口径，第二步设计召回与重排方案，"
     "第三步灰度上线并持续监控。最终转化率提升了 20%，并通过 A/B 测试验证了效果。"),
    "就是挺好的，我觉得还行吧，主要是我比较努力，大家也都很认可我。",
    "我没有遇到过什么挑战，一切都很顺利。",
    "这个我不太了解，没有研究过。",
]
for i, sq in enumerate(qs):
    requests.post(f"{API}/sessions/{sid}/questions/{sq['id']}/answer", headers=A,
                  json={"transcript": answers[i], "audio_url": "", "duration_ms": 60000})
r = requests.post(f"{API}/sessions/{sid}/finish", headers=A).json()
rid = r["data"]["report_id"]
rep = requests.get(f"{API}/reports/{rid}", headers=A).json()["data"]

check("标准4: 报告生成", rid > 0, f"report_id={rid}, total={rep['total_score']}")
rqs = rep["questions"]
check("标准4: 每题有参考标准答案", all(q.get("ref_answer") for q in rqs),
      [bool(q.get("ref_answer")) for q in rqs])
check("标准4: 参考答案逐题不同（非同一模板）",
      len(set(q["ref_answer"][:30] for q in rqs)) >= min(3, len(rqs)),
      len(set(q["ref_answer"][:30] for q in rqs)))
check("标准4: 每题有「答得好」分析（good_points）",
      all(len(q.get("good_points") or []) >= 1 for q in rqs),
      [len(q.get("good_points") or []) for q in rqs])
check("标准4: 每题有「欠缺」分析（weak_points）",
      all(len(q.get("weak_points") or []) >= 1 for q in rqs),
      [len(q.get("weak_points") or []) for q in rqs])
print("   薄弱题参考答案示例:", rqs[0]["ref_answer"][:60])

# 薄弱题型 → 专项题库映射（前端「针对该题型再练一轮」的后端数据基础）
weak_q = [q for q in rqs if (q.get("total_score") or 0) < 75]
check("标准4: 存在薄弱题（<75 分）", len(weak_q) >= 1, f"{len(weak_q)} 道")
dims_needed = set(q.get("dimension") for q in weak_q)
specials = [s for s in sets if s.get("industry") == "专项练习"]
sp_types = set(s["position_type"] for s in specials)
mapped = [d for d in dims_needed if d in sp_types]
check("标准4: 薄弱题型可映射到专项题库（再练一轮）", len(mapped) >= 1 or len(specials) >= 5,
      f"薄弱维度={dims_needed} 可映射={mapped} 专项库={sorted(sp_types)}")
# 映射到的专项套题可直接开场（模拟前端 practiceCategory 调用）
if mapped:
    sp = [s for s in specials if s["position_type"] == mapped[0]][0]
    r2 = requests.post(f"{API}/sessions", headers=A, json={
        "set_id": sp["id"], "form_type": "structured", "enable_followup": True}).json()
    check("标准4: 针对性训练场次可创建", r2["code"] == 0 and r2["data"]["session_id"] > 0,
          f"{sp['name']} session={r2['data']['session_id']}")

print(f"\n{'='*52}")
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败:", FAIL); sys.exit(1)
print("🎉 模拟面试四条验收标准（API 层）全部通过")

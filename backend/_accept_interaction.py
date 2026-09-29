# -*- coding: utf-8 -*-
"""验证：AI 理解引用原话 + 群面三阶段回应引用候选人发言 + 新题库真实入库"""
import sys, io, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://127.0.0.1:8000"; API = BASE + "/api/v1"
PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌"), name, ("| " + str(detail)) if detail else "")

r = requests.post(f"{API}/auth/login", json={"phone": "13800000000", "password": "123456"})
A = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}

# 1) AI 理解必须复述候选人原话内容
ans = ("我主导企业知识库 RAG 系统建设，负责数据治理和双路召回，"
       "上线后召回率提升15%，客服首解率从62%提升到78%。")
sets = requests.get(f"{API}/question-sets", headers=A).json()["data"]
semi_set = [s for s in sets if s["form_type"] == "semi"][0]
sess = requests.post(f"{API}/sessions", headers=A, json={
    "set_id": semi_set["id"], "form_type": "semi", "use_resume": False}).json()["data"]
detail = requests.get(f"{API}/sessions/{sess['session_id']}", headers=A).json()["data"]
sq0 = detail["questions"][0]
fb = requests.post(f"{API}/sessions/questions/{sq0['id']}/feedback", headers=A,
                   json={"transcript": ans, "question_dimension": "专业深度",
                         "question_content": "介绍你的项目"}).json()["data"]
u = fb.get("understanding", "")
print("   理解内容：", u[:110])
check("AI理解引用原话核心内容（RAG/召回/提升）", ("RAG" in u or "召回" in u or "主导" in u), u[:60])
check("AI理解引用原话数据（15%/62%/78%）", any(k in u for k in ["15%", "62%", "78%"]), u[:80])
check("追问仍引用原话", any(k in fb.get("followup", "") for k in ["15%", "62%", "78%", "召回"]),
      fb.get("followup", "")[:50])

# 短回答也要有针对性理解
short = requests.post(f"{API}/sessions/questions/{sq0['id']}/feedback", headers=A,
                      json={"transcript": "我觉得挺好的，大家都很认可我。",
                            "question_dimension": "岗位匹配", "question_content": ""}).json()["data"]
check("弱回答有改进建议", len(short.get("suggestions", [])) >= 1, short.get("suggestions"))

# 2) 群面：个人陈述/总结阶段发言后，人设回应引用原话
group_set = [s for s in sets if s["form_type"] == "group"][0]
gsess = requests.post(f"{API}/sessions", headers=A, json={
    "set_id": group_set["id"], "form_type": "group", "peer_count": 5}).json()["data"]
peers = requests.get(f"{API}/sessions/{gsess['session_id']}/peers", headers=A).json()["data"]
check("群面加载 5 个人设", len(peers) >= 5, f"{len(peers)} 人")
my_opening = "我认为应该优先保障就业稳定，因为员工信任是企业最宝贵的资产，裁员换AI是短视行为。"
resp = requests.post(f"{API}/sessions/{gsess['session_id']}/peer-talk", headers=A, json={
    "stage": "opening", "persona_id": peers[0]["id"], "stance": "我支持优先AI提效",
    "topic": "AI提效与就业稳定", "target_name": "你", "user_text": my_opening}).json()["data"]
t1 = resp["text"]
print("   陈述回应：", t1[:100])
check("个人陈述后回应引用我的原话观点", any(k in t1 for k in ["就业稳定", "员工信任", "裁员", "短视"]), t1[:60])

my_summary = "总结一下，我们的共识是分阶段推进：先用AI提效但同步做员工转型培训，三年过渡期。"
resp2 = requests.post(f"{API}/sessions/{gsess['session_id']}/peer-talk", headers=A, json={
    "stage": "summary", "persona_id": peers[1]["id"], "stance": "稳健",
    "topic": "AI提效与就业稳定", "target_name": "你", "user_text": my_summary}).json()["data"]
t2 = resp2["text"]
print("   总结回应：", t2[:100])
check("总结后回应引用我的总结原话", any(k in t2 for k in ["分阶段", "转型培训", "过渡期", "共识"]), t2[:60])

# 3) 新题库真实入库可查
struct_sets = [s for s in sets if s["form_type"] == "structured"]
check("结构化套题≥10套", len(struct_sets) >= 10, f"{len(struct_sets)} 套")
new_ops = [s for s in sets if "运营实战" in s["name"]]
check("新增运营题库可查", len(new_ops) == 1 and new_ops[0]["question_count"] == 8,
      new_ops[0]["name"] if new_ops else "缺失")
group_sets = [s for s in sets if s["form_type"] == "group"]
check("群面套题≥5套", len(group_sets) >= 5, f"{len(group_sets)} 套")
semi_sets = [s for s in sets if s["form_type"] == "semi"]
check("半结构化套题≥4套", len(semi_sets) >= 4, f"{len(semi_sets)} 套")

# 4) positions 真实入库（经接口验证管理员能看到岗位数据，直接查库）
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from app.models.position import Position
db = SessionLocal()
pc = db.query(Position).count()
check("positions 表有真实记录", pc >= 5, f"{pc} 条")
db.close()

print(f"\n{'='*52}")
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败:", FAIL); sys.exit(1)
print("🎉 实时交互与数据扩充验证全部通过")

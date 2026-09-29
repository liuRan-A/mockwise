# -*- coding: utf-8 -*-
"""验收：简历上传/分析 → 简历个性化出题 → 管理后台 API + 权限"""
import sys, io, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://127.0.0.1:8000/api/v1"
PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌"), name, detail)

# —— admin 登录 ——
r = requests.post(f"{BASE}/auth/login", json={"phone": "13800000000", "password": "123456"})
admin_token = r.json()["data"]["access_token"]
admin_user = r.json()["data"]["user"]
A = {"Authorization": f"Bearer {admin_token}"}
check("admin 登录 role=admin", admin_user.get("role") == "admin", f"role={admin_user.get('role')}")

# —— 1. 粘贴简历文本 → AI/规则分析 ——
resume_text = """
张伟，求职意向：AI 方案架构师，3 年工作经验。
工作经历：2021-2024 在某互联网公司担任算法工程师，主导企业知识库 RAG 系统建设，
负责数据治理、双路召回（向量+关键词）、重排模型，上线后召回率提升15%，客服首解率从62%提升到78%。
技能：Python、PyTorch、大模型应用、向量数据库、FastAPI、团队协作。
项目：独立设计客服智能问答系统，搭建评测体系，推动灰度上线与熔断回滚预案。
"""
r = requests.post(f"{BASE}/resumes/upload", headers=A,
                  data={"text": resume_text}, timeout=90).json()
check("简历上传分析 code=0", r["code"] == 0, r.get("msg", ""))
resume = r["data"]
prof = resume["profile"]
print("  画像引擎:", resume.get("engine"), "| 技能:", prof["skills"][:4])
check("画像-概述", bool(prof["summary"]))
check("画像-技能≥3", len(prof["skills"]) >= 3, f"{len(prof['skills'])} 项")
check("画像-项目经历", len(prof["projects"]) >= 1)
check("画像-建议问题≥4", len(prof["suggested_questions"]) >= 4, f"{len(prof['suggested_questions'])} 道")
check("画像-薄弱点", len(prof["weaknesses"]) >= 1)

# —— 2. 当前简历接口 ——
r = requests.get(f"{BASE}/resumes/active", headers=A).json()
check("当前简历 active", r["data"] is not None and r["data"]["is_active"] == 1)

# —— 3. 半结构化面试 use_resume=true → 题目应来自简历 ——
sets = requests.get(f"{BASE}/question-sets", headers=A).json()["data"]
semi_set = [s for s in sets if s["form_type"] == "semi"][0]
r = requests.post(f"{BASE}/sessions", headers=A, json={
    "set_id": semi_set["id"], "form_type": "semi", "enable_followup": True, "use_resume": True,
}).json()
sid = r["data"]["session_id"]
detail = requests.get(f"{BASE}/sessions/{sid}", headers=A).json()["data"]
qs = detail["questions"]
src_resume = [q for q in qs if q.get("source") == "resume"]
check("简历出题-生成题目", len(qs) >= 4, f"{len(qs)} 道")
check("简历出题-source=resume", len(src_resume) >= 4, f"{len(src_resume)} 道来自简历")
print("  简历题示例:", src_resume[0]["question_content"][:50] if src_resume else "无")
# 简历题不应是题库原半结构化题
check("简历题个性化(含简历特征)",
      any(k in (src_resume[0]["question_content"] if src_resume else "") for k in ["项目", "简历", "经历", "RAG", "知识库", "负责"]),
      src_resume[0]["question_content"][:40] if src_resume else "")

# —— 4. 简历题可正常作答评分入库 ——
q0 = qs[0]
ans = ("我主导 RAG 知识库项目时，先做数据治理，再设计双路召回加重排，"
       "召回率提升15%，并建立熔断回滚预案，灰度上线。")
r = requests.post(f"{BASE}/sessions/{sid}/questions/{q0['id']}/answer", headers=A,
                  json={"transcript": ans, "audio_url": "", "duration_ms": 90000}).json()
check("简历题作答出分", r["code"] == 0 and r["data"]["total_score"] > 0,
      f"score={r['data']['total_score']}")

# —— 5. 不使用简历的半结构化 → 题库题 ——
r = requests.post(f"{BASE}/sessions", headers=A, json={
    "set_id": semi_set["id"], "form_type": "semi", "use_resume": False,
}).json()
sid2 = r["data"]["session_id"]
d2 = requests.get(f"{BASE}/sessions/{sid2}", headers=A).json()["data"]
bank_src = [q for q in d2["questions"] if q.get("source") == "bank"]
check("不用简历走题库", len(bank_src) >= 1, f"{len(bank_src)} 道题库题")

# —— 6. 管理后台统计 ——
r = requests.get(f"{BASE}/admin/stats", headers=A).json()
check("admin 统计 code=0", r["code"] == 0)
st = r["data"]
check("统计-用户数", st["total_users"] >= 1, f"{st['total_users']}")
check("统计-场次数", st["total_sessions"] >= 1, f"{st['total_sessions']}")
check("统计-简历数", st["total_resumes"] >= 1, f"{st['total_resumes']}")
check("统计-7天趋势", len(st["trend"]) == 7)
check("统计-形式分布", len(st["form_distribution"]) >= 1)

r = requests.get(f"{BASE}/admin/users?page=1&page_size=5", headers=A).json()
check("admin 用户列表", r["code"] == 0 and r["data"]["total"] >= 1, f"{r['data']['total']} 人")

r = requests.get(f"{BASE}/admin/sessions?page=1&page_size=5", headers=A).json()
check("admin 场次列表", r["code"] == 0 and r["data"]["total"] >= 1, f"{r['data']['total']} 场")

r = requests.get(f"{BASE}/admin/resumes?page=1&page_size=5", headers=A).json()
check("admin 简历列表", r["code"] == 0 and r["data"]["total"] >= 1, f"{r['data']['total']} 份")

# 禁用/启用用户（找一个非自己的用户，否则跳过）
users = requests.get(f"{BASE}/admin/users?page=1&page_size=20", headers=A).json()["data"]["list"]
other = [u for u in users if u["role"] != "admin"]
if other:
    uid = other[0]["id"]
    r = requests.patch(f"{BASE}/admin/users/{uid}/status?status=paused", headers=A).json()
    check("admin 禁用用户", r["code"] == 0 and r["data"]["status"] == "paused")
    requests.patch(f"{BASE}/admin/users/{uid}/status?status=active", headers=A)
else:
    check("admin 禁用用户（无其他用户，跳过）", True)

# —— 7. 权限：普通用户访问 admin 应 403 ——
requests.post(f"{BASE}/auth/register", json={"phone": "13900000099", "password": "123456", "nickname": "普通用户"})
r = requests.post(f"{BASE}/auth/login", json={"phone": "13900000099", "password": "123456"})
if r.json().get("data"):
    nt = r.json()["data"]["access_token"]
    N = {"Authorization": f"Bearer {nt}"}
    check("普通用户 role=user", r.json()["data"]["user"].get("role") == "user")
    code = requests.get(f"{BASE}/admin/stats", headers=N).status_code
    check("普通用户访问 admin 被拒(403)", code == 403, f"HTTP {code}")
    # 普通用户不能看别人简历列表（admin 简历列表是全局的）
    code2 = requests.get(f"{BASE}/admin/resumes", headers=N).status_code
    check("普通用户访问 admin 简历被拒", code2 == 403, f"HTTP {code2}")

print(f"\n{'='*50}")
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败:", FAIL); sys.exit(1)
print("🎉 简历上传→分析→简历出题闭环 + 管理后台权限全部通过")

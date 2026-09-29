# -*- coding: utf-8 -*-
"""盘点数据库各表真实数据量"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
tables = [
    "users", "user_quotas", "user_streaks", "practice_history",
    "question_sets", "peer_personas", "questions",
    "interview_configs", "interview_sessions", "session_questions",
    "session_scores", "session_metrics", "session_highlights",
    "session_recommendations", "reports", "report_highlights",
    "report_recommendations", "group_discussions", "group_members",
    "group_timeline", "positions", "jd_documents", "resumes",
]
print(f"{'表名':<28}{'记录数':>8}")
print("-" * 40)
for t in tables:
    try:
        n = db.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
        print(f"{t:<28}{n:>8}")
    except Exception as e:
        print(f"{t:<28}  ERR: {str(e)[:40]}")

print("\n=== 套题分布（form_type / industry） ===")
rows = db.execute(text(
    "SELECT form_type, industry, COUNT(*) cnt, SUM(question_count) qc "
    "FROM question_sets GROUP BY form_type, industry ORDER BY form_type, industry"
)).fetchall()
for r in rows:
    print(f"  {r[0]:<12} {r[1]:<12} 套题={r[2]} 题数={r[3]}")

print("\n=== questions 表按 form_type/category 分布 ===")
rows = db.execute(text(
    "SELECT form_type, category, dimension, COUNT(*) FROM questions "
    "GROUP BY form_type, category, dimension ORDER BY form_type, category"
)).fetchall()
for r in rows:
    print(f"  {r[0]:<11} {r[1] or '-':<10} {r[2] or '-':<10} {r[3]} 题")

print("\n=== peer_personas 人设 ===")
rows = db.execute(text("SELECT id, name, style, aggressiveness, set_id FROM peer_personas")).fetchall()
for r in rows:
    print(f"  id={r[0]} {r[1]} <{r[2]}> aggro={r[3]} set_id={r[4]}")

print("\n=== 最近5场会话 ===")
rows = db.execute(text(
    "SELECT id, form_type, status, total_score, created_at FROM interview_sessions "
    "ORDER BY id DESC LIMIT 5")).fetchall()
for r in rows:
    print(f"  session {r[0]} {r[1]} {r[2]} score={r[3]} {r[4]}")
db.close()

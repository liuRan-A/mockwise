# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from app.models.question import PeerPersona

db = SessionLocal()
for p in db.query(PeerPersona).all():
    print(f"===== {p.name} <{p.style}> aggro={p.aggressiveness} =====")
    for key, label in [("openings", "开场"), ("rebuttals", "反驳"), ("summaries", "总结")]:
        data = getattr(p, key) or {}
        lst = data.get("list", []) if isinstance(data, dict) else []
        print(f"  [{label}] {len(lst)} 条")
        for t in lst[:3]:
            has_point = "{point}" in t
            print(f"    {'★' if has_point else '○'} {t[:90]}")
db.close()

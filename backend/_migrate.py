# -*- coding: utf-8 -*-
"""一次性迁移：question_sets 加 form_type 列 + 建 peer_personas 表 + 回填现有题库分类"""
import sys

sys.path.insert(0, ".")

from sqlalchemy import text  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.question import QuestionSet, Question, PeerPersona  # noqa: E402
from app.core.database import Base  # noqa: E402


def main():
    # 1. 建 peer_personas 新表（create_all 只建缺失表，不影响现有表）
    Base.metadata.create_all(engine, tables=[PeerPersona.__table__])
    print("[migrate] peer_personas table ready")

    db = SessionLocal()
    try:
        # 2. question_sets 加 form_type 列（幂等：已存在则跳过）
        cols = db.execute(text("SHOW COLUMNS FROM question_sets LIKE 'form_type'")).fetchall()
        if not cols:
            db.execute(text(
                "ALTER TABLE question_sets ADD COLUMN form_type "
                "ENUM('structured','group','semi') NOT NULL DEFAULT 'structured' "
                "AFTER position_type"
            ))
            db.commit()
            print("[migrate] added column question_sets.form_type")
        else:
            print("[migrate] column question_sets.form_type already exists")

        # 3. 回填：按每套题里题目的 form_type 众数
        sets = db.query(QuestionSet).all()
        for s in sets:
            rows = db.query(Question.form_type).filter(Question.set_id == s.id).all()
            if not rows:
                continue
            counts = {}
            for (ft,) in rows:
                counts[ft] = counts.get(ft, 0) + 1
            majority = max(counts, key=counts.get)
            if s.form_type != majority:
                s.form_type = majority
                print(f"[migrate] set#{s.id} {s.name} -> {majority}")
        db.commit()
        print("[migrate] backfill done")
    finally:
        db.close()


if __name__ == "__main__":
    main()

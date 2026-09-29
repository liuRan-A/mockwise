# -*- coding: utf-8 -*-
"""
迁移 v1.1：逐题深度分析字段

为 session_questions 增加三个字段（幂等，可重复执行）：
  - strengths  JSON   答得好的地方
  - gaps       JSON   欠缺/答得不好的地方
  - ref_detail JSON   结构化参考答案（采分点 / 答题框架 / 示范作答 / 常见失分点）

用法：
    cd backend
    python migrate_v2.py
"""
import sys

sys.path.insert(0, ".")

from sqlalchemy import text  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402

# (列名, DDL 片段)
NEW_COLUMNS = [
    ("strengths", "JSON NULL COMMENT '答得好的地方' AFTER ref_answer"),
    ("gaps", "JSON NULL COMMENT '欠缺/答得不好的地方' AFTER strengths"),
    ("ref_detail", "JSON NULL COMMENT '结构化参考答案' AFTER gaps"),
]


def main():
    db = SessionLocal()
    try:
        for col, ddl in NEW_COLUMNS:
            exists = db.execute(
                text("SHOW COLUMNS FROM session_questions LIKE :c"), {"c": col}
            ).fetchall()
            if exists:
                print(f"[migrate] session_questions.{col} already exists, skip")
                continue
            db.execute(text(f"ALTER TABLE session_questions ADD COLUMN {col} {ddl}"))
            db.commit()
            print(f"[migrate] added column session_questions.{col}")

        # 顺带确保 questions 表有 ref_answer 列（老库可能缺失）
        cols = db.execute(text("SHOW COLUMNS FROM questions LIKE 'ref_answer'")).fetchall()
        if not cols:
            db.execute(text("ALTER TABLE questions ADD COLUMN ref_answer TEXT NULL AFTER attachments"))
            db.commit()
            print("[migrate] added column questions.ref_answer")
        else:
            print("[migrate] questions.ref_answer already exists")
    finally:
        db.close()
    print("[migrate] done.")


if __name__ == "__main__":
    main()

"""题库 CRUD（套题 + 题目）"""
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.question import QuestionSet, Question


# ===== 套题 =====
def list_sets(db: Session, form_type: str | None = None, position_type: str | None = None):
    """前台：仅上架"""
    q = db.query(QuestionSet).filter(QuestionSet.is_published == 1)
    if form_type:
        q = q.filter(QuestionSet.form_type == form_type)
    if position_type:
        q = q.filter(QuestionSet.position_type == position_type)
    return q.order_by(QuestionSet.match_score.desc()).all()


def list_all_sets(db: Session):
    """后台：含下架"""
    return db.query(QuestionSet).order_by(QuestionSet.id.desc()).all()


def create_set(db: Session, data: dict) -> QuestionSet:
    s = QuestionSet(**data, question_count=0)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def update_set(db: Session, set_id: int, data: dict) -> QuestionSet | None:
    s = db.get(QuestionSet, set_id)
    if not s:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


def delete_set(db: Session, set_id: int) -> bool:
    s = db.get(QuestionSet, set_id)
    if not s:
        return False
    db.delete(s)          # cascade 删除关联题目
    db.commit()
    return True


def set_publish(db: Session, set_id: int, published: int) -> QuestionSet | None:
    return update_set(db, set_id, {"is_published": published})


def recalc_count(db: Session, set_id: int) -> int:
    """重算套题题目数（增删题目后调用）"""
    cnt = db.query(func.count(Question.id)).filter(Question.set_id == set_id).scalar() or 0
    s = db.get(QuestionSet, set_id)
    if s:
        s.question_count = cnt
        db.commit()
    return cnt


# ===== 题目 =====
def list_questions(db: Session, set_id: int):
    return db.query(Question).filter(Question.set_id == set_id).order_by(Question.seq).all()


def max_seq(db: Session, set_id: int) -> int:
    return db.query(func.max(Question.seq)).filter(Question.set_id == set_id).scalar() or 0


def create_question(db: Session, set_id: int, data: dict) -> Question:
    seq = data.get("seq") or (max_seq(db, set_id) + 1)
    q = Question(set_id=set_id, **{k: v for k, v in data.items() if k != "seq"}, seq=seq)
    db.add(q)
    db.commit()
    db.refresh(q)
    recalc_count(db, set_id)
    return q


def update_question(db: Session, qid: int, data: dict) -> Question | None:
    q = db.get(Question, qid)
    if not q:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q


def delete_question(db: Session, qid: int) -> bool:
    q = db.get(Question, qid)
    if not q:
        return False
    sid = q.set_id
    db.delete(q)
    db.commit()
    # 重排 seq 保持连续
    for i, qq in enumerate(list_questions(db, sid), 1):
        qq.seq = i
    db.commit()
    recalc_count(db, sid)
    return True


def get_set(db: Session, set_id: int) -> QuestionSet | None:
    return db.get(QuestionSet, set_id)


def get_set_detail(db: Session, set_id: int):
    s = db.get(QuestionSet, set_id)
    if not s:
        return None
    questions = db.query(Question).filter(
        Question.set_id == set_id
    ).order_by(Question.seq).all()
    return s, questions

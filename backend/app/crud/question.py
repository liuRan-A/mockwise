"""题库 CRUD"""
from sqlalchemy.orm import Session
from app.models.question import QuestionSet, Question


def list_sets(db: Session, form_type: str | None = None, position_type: str | None = None):
    q = db.query(QuestionSet).filter(QuestionSet.is_published == 1)
    if form_type:
        q = q.filter(QuestionSet.form_type == form_type)
    if position_type:
        q = q.filter(QuestionSet.position_type == position_type)
    return q.order_by(QuestionSet.match_score.desc()).all()


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

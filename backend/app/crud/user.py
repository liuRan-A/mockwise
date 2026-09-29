"""用户 / 鉴权 CRUD"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User, UserQuota, UserStreak
from app.core.security import hash_password, verify_password, create_access_token


def get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.query(User).filter(User.phone == phone).first()


def authenticate(db: Session, phone: str, password: str) -> User | None:
    user = get_user_by_phone(db, phone)
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, phone: str, password: str, nickname: str = "") -> User:
    user = User(
        phone=phone,
        password_hash=hash_password(password),
        nickname=nickname or f"用户{phone[-4:]}",
    )
    db.add(user)
    db.flush()
    # 初始化本月配额（3 次/月）+ 连续天数
    month_key = datetime.now().strftime("%Y-%m")
    db.add(UserQuota(user_id=user.id, month_key=month_key, simulated_left=3, simulated_total=3))
    db.add(UserStreak(user_id=user.id, current_days=0, best_days=0))
    db.commit()
    db.refresh(user)
    return user


def issue_token(user: User) -> str:
    return create_access_token(str(user.id))


def touch_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now()
    db.commit()


def set_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    db.commit()


def _month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def get_or_create_quota(db: Session, user_id: int, month_key: str | None = None) -> "UserQuota":
    month_key = month_key or _month_key()
    q = db.query(UserQuota).filter_by(user_id=user_id, month_key=month_key).first()
    if not q:
        q = UserQuota(user_id=user_id, month_key=month_key, simulated_left=3, simulated_total=3)
        db.add(q)
        db.commit()
        db.refresh(q)
    return q


def get_quota(db: Session, user_id: int) -> dict:
    q = get_or_create_quota(db, user_id)
    return {
        "month_key": q.month_key,
        "simulated_left": q.simulated_left,
        "simulated_total": q.simulated_total,
    }


def add_quota(db: Session, user_id: int, amount: int) -> dict:
    q = get_or_create_quota(db, user_id)
    q.simulated_left += amount
    q.simulated_total += amount
    db.commit()
    db.refresh(q)
    return {
        "month_key": q.month_key,
        "simulated_left": q.simulated_left,
        "simulated_total": q.simulated_total,
    }

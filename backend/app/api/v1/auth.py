"""鉴权路由：登录 / 注册 / 当前用户"""
import random
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import R
from app.schemas.user import UserLogin, UserCreate, UserOut, TokenOut, ForgotCodeIn, ResetPasswordIn, RechargeIn
from app.crud import user as user_crud

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- demo：重置验证码内存存储（生产应走短信 + Redis）----
_reset_codes: dict[str, tuple[str, float]] = {}  # phone -> (code, expire_ts)
_CODE_TTL = 300  # 5 分钟有效期

# ---- 充值套餐（demo：确认即到账，无真实支付）----
RECHARGE_PACKAGES = [
    {"id": "starter", "name": "入门包", "amount": 10, "price": 9.9},
    {"id": "standard", "name": "标准包", "amount": 30, "price": 24.9},
    {"id": "pro", "name": "专业包", "amount": 100, "price": 69.9},
]


@router.post("/login", response_model=R, summary="手机号 + 密码登录（demo）")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = user_crud.authenticate(db, payload.phone, payload.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "手机号或密码错误")
    token = user_crud.issue_token(user)
    user_crud.touch_login(db, user)
    return R.ok(TokenOut(access_token=token, user=UserOut.from_orm(user)).dict())


@router.post("/register", response_model=R, summary="注册")
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if user_crud.get_user_by_phone(db, payload.phone):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "手机号已注册")
    user = user_crud.create_user(db, payload.phone, payload.password, payload.nickname)
    token = user_crud.issue_token(user)
    return R.ok(TokenOut(access_token=token, user=UserOut.from_orm(user)).dict())


@router.post("/forgot-code", response_model=R, summary="获取重置验证码(demo)")
def forgot_code(payload: ForgotCodeIn, db: Session = Depends(get_db)):
    if not user_crud.get_user_by_phone(db, payload.phone):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该手机号未注册")
    code = f"{random.randint(100000, 999999)}"
    _reset_codes[payload.phone] = (code, time.time() + _CODE_TTL)
    # demo 模式直接返回验证码；生产环境应改为短信下发
    return R.ok({"code": code, "demo": True}, msg="验证码已发送（demo 直接返回）")


@router.post("/reset-password", response_model=R, summary="验证码重置密码")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    rec = _reset_codes.get(payload.phone)
    if not rec or rec[1] < time.time():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    if rec[0] != payload.code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误")
    user = user_crud.get_user_by_phone(db, payload.phone)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该手机号未注册")
    user_crud.set_password(db, user, payload.new_password)
    _reset_codes.pop(payload.phone, None)
    return R.ok(msg="密码已重置，请使用新密码登录")


@router.get("/quota", response_model=R, summary="当前用户配额")
def quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return R.ok(user_crud.get_quota(db, user.id))


@router.get("/recharge-packages", response_model=R, summary="充值套餐列表")
def recharge_packages():
    return R.ok(RECHARGE_PACKAGES)


@router.post("/recharge", response_model=R, summary="充值次数")
def recharge(payload: RechargeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pkg = next((p for p in RECHARGE_PACKAGES if p["id"] == payload.package_id), None)
    if not pkg:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "套餐不存在")
    quota = user_crud.add_quota(db, user.id, pkg["amount"])
    return R.ok(quota, msg=f"成功充值 {pkg['amount']} 次")


@router.get("/me", response_model=R, summary="当前用户")
def me(user: User = Depends(get_current_user)):
    return R.ok(UserOut.from_orm(user).dict())

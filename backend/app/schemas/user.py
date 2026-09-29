"""用户 / 鉴权 schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    phone: str = Field(..., description="手机号")
    code: str = Field("", description="短信验证码（demo 可空）")
    password: str = Field("", description="密码（可选，demo 用")


class UserCreate(BaseModel):
    phone: str
    password: str
    nickname: str = ""


class ForgotCodeIn(BaseModel):
    phone: str


class ResetPasswordIn(BaseModel):
    phone: str
    code: str
    new_password: str = Field(..., min_length=6, description="新密码（至少 6 位）")


class RechargeIn(BaseModel):
    package_id: str


class UserOut(BaseModel):
    id: int
    phone: str
    nickname: str
    avatar_url: str
    target_position: str
    role: str = "user"
    status: str
    last_login_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

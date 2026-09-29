"""通用响应封装"""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class R(BaseModel):
    """统一响应结构 {code, msg, data}"""
    code: int = 0
    msg: str = "ok"
    data: Optional[Any] = None

    @classmethod
    def ok(cls, data: Any = None, msg: str = "ok") -> "R":
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, msg: str = "fail", code: int = 1, data: Any = None) -> "R":
        return cls(code=code, msg=msg, data=data)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20

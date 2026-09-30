"""数据库连接 / SQLAlchemy 会话

并发安全要点：
- 通过 pool_size / max_overflow / pool_timeout 显式控制连接池规模，
  让多用户并发时不会因为「默认 5 连接 + 无溢出上限」而被悄悄拖慢或阻塞；
- pool_pre_ping 在借出连接前做心跳，自动剔除被 MySQL 服务端断开的死连接；
- pool_use_lifo=True 减少空闲连接数，配合 pool_recycle 避免 8h 超时断连；
- get_db 每请求一会话，用完即关，不跨请求复用。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 连接池规模：demo 级单机可支撑数十并发用户；如需更高并发按需调大
POOL_SIZE = int(getattr(settings, "DB_POOL_SIZE", 10))
MAX_OVERFLOW = int(getattr(settings, "DB_MAX_OVERFLOW", 20))
POOL_TIMEOUT = int(getattr(settings, "DB_POOL_TIMEOUT", 30))

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_use_lifo=True,
    echo=settings.DEBUG,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：每请求一个 DB 会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
数据库服务 - SQLAlchemy ORM
支持 SQLite（默认）或 MySQL（通过 DATABASE_URL 配置）
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from config import DATABASE_URL


# 创建数据库引擎
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """
    用户模型
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    nickname = Column(String(50), nullable=False)
    avatar = Column(String(255), nullable=True)  # 头像URL
    age = Column(Integer, nullable=True)  # 年龄
    profession = Column(String(100), nullable=True)  # 职业
    hashed_password = Column(String(255), nullable=False)
    verification_code = Column(String(10), nullable=True)  # 验证码
    verification_code_expires = Column(DateTime, nullable=True)  # 验证码过期时间
    is_verified = Column(Integer, default=0)  # 是否验证
    
    # 配额限制字段
    last_usage_date = Column(String(20), nullable=True)  # 格式: YYYY-MM-DD
    daily_usage_count = Column(Integer, default=0)   # 当日已使用次数
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# 创建表
Base.metadata.create_all(bind=engine)


def get_db():
    """
    获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

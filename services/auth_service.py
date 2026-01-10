"""
认证服务 - 用户注册、登录、验证等
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from services.database import User
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


# 密码加密上下文
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    default="argon2",
    deprecated="auto"
)


class AuthService:
    """
    认证服务类
    """
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        验证密码
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """
        获取密码哈希
        """
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """
        创建访问令牌
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_access_token(self, token: str) -> Optional[dict]:
        """
        解码访问令牌
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
    
    def generate_verification_code(self) -> str:
        """
        生成6位数字验证码
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    def register_user(
        self,
        db: Session,
        phone: str,
        password: str,
        nickname: str,
        avatar: Optional[str] = None,
        age: Optional[int] = None,
        profession: Optional[str] = None
    ) -> Optional[User]:
        """
        注册用户
        """
        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.phone == phone).first()
        if existing_user:
            return None  # 用户已存在
        
        # 创建新用户
        hashed_password = self.get_password_hash(password)
        db_user = User(
            phone=phone,
            nickname=nickname,
            avatar=avatar,
            age=age,
            profession=profession,
            hashed_password=hashed_password
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return db_user
    
    def authenticate_user(self, db: Session, phone: str, password: str) -> Optional[User]:
        """
        认证用户
        """
        user = db.query(User).filter(User.phone == phone).first()
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def update_verification_code(self, db: Session, phone: str, code: str, expires: datetime):
        """
        更新验证码
        """
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            return False
        
        user.verification_code = code
        user.verification_code_expires = expires
        db.commit()
        return True
    
    def verify_phone_with_code(self, db: Session, phone: str, code: str) -> bool:
        """
        验证手机验证码
        """
        user = db.query(User).filter(User.phone == phone).first()
        if not user or user.verification_code != code:
            return False
        
        # 检查验证码是否过期
        if user.verification_code_expires and user.verification_code_expires < datetime.utcnow():
            return False
        
        # 验证成功，更新验证状态
        user.is_verified = 1
        user.verification_code = None
        user.verification_code_expires = None
        db.commit()
        return True

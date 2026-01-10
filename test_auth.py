import sys
import os
# 添加当前目录到 sys.path
sys.path.append(os.getcwd())

from services.database import get_db, User, Base, engine
from services.auth_service import AuthService

# 重新创建表
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = next(get_db())
auth = AuthService()

print("--- 开始测试 ---")

# 1. 注册
phone = "13800138000"
password = "yang2025"
nickname = "TestUser"

print(f"尝试注册用户: {phone} / {password}")
try:
    user = auth.register_user(db, phone, password, nickname)
    if user:
        print(f"注册成功! ID: {user.id}, Hash: {user.hashed_password[:30]}...")
    else:
        print("注册失败!")
except Exception as e:
    print(f"注册异常: {e}")

# 2. 验证数据库
saved_user = db.query(User).filter(User.phone == phone).first()
if saved_user:
    print(f"数据库验证: 找到用户 {saved_user.nickname}")
else:
    print("数据库验证: 未找到用户!")

# 3. 登录
print(f"尝试登录: {phone} / {password}")
try:
    login_user = auth.authenticate_user(db, phone, password)
    if login_user:
        print("登录成功!")
    else:
        print("登录失败!")
except Exception as e:
    print(f"登录异常: {e}")

print("--- 测试结束 ---")

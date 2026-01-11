from datetime import datetime
from sqlalchemy.orm import Session
from services.database import User
from fastapi import HTTPException

MAX_DAILY_ANALYSIS = 3

class QuotaService:
    @staticmethod
    def check_and_increment_quota(db: Session, user_id: int):
        """
        检查并增加用户每日使用配额
        如果超过限制，抛出 403 异常
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 检查是否是新的一天
        if user.last_usage_date != today_str:
            # 重置计数器
            user.last_usage_date = today_str
            user.daily_usage_count = 0
            
        # 检查是否超额
        if user.daily_usage_count >= MAX_DAILY_ANALYSIS:
            raise HTTPException(
                status_code=403, 
                detail=f"今日免费额度已用完（每日限 {MAX_DAILY_ANALYSIS} 篇）。请明天再来！"
            )
            
        # 增加计数
        user.daily_usage_count += 1
        db.commit()
        db.refresh(user)
        
        return user.daily_usage_count
import os
import json
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import time

try:
    import redis
except ImportError:
    redis = None

from config import CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)

class SessionStore(ABC):
    """Session 存储抽象基类"""
    
    @abstractmethod
    def load(self, session_id: str) -> Dict[str, Any]:
        """加载 Session 数据"""
        pass
    
    @abstractmethod
    def save(self, session_id: str, data: Dict[str, Any]) -> None:
        """保存 Session 数据"""
        pass
    
    @abstractmethod
    def delete(self, session_id: str) -> None:
        """删除 Session"""
        pass

class FileSessionStore(SessionStore):
    """基于文件的 Session 存储 (开发/无 Redis 环境使用)"""
    
    def __init__(self, session_dir: str = "sessions"):
        self.session_dir = session_dir
        os.makedirs(self.session_dir, exist_ok=True)
        
    def _get_path(self, session_id: str) -> str:
        # 简单的安全过滤
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.session_dir, f"{safe_id}.json")
        
    def load(self, session_id: str) -> Dict[str, Any]:
        path = self._get_path(session_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载 Session 文件失败: {e}")
        return {}
        
    def save(self, session_id: str, data: Dict[str, Any]) -> None:
        path = self._get_path(session_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 Session 文件失败: {e}")
            
    def delete(self, session_id: str) -> None:
        path = self._get_path(session_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"删除 Session 文件失败: {e}")

class RedisSessionStore(SessionStore):
    """基于 Redis 的 Session 存储 (生产环境使用)"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        if redis is None:
            raise ImportError("请先安装 redis 库: pip install redis")
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.expire_seconds = 86400 * 7 # 7天过期
        
    def load(self, session_id: str) -> Dict[str, Any]:
        try:
            data = self.client.get(f"session:{session_id}")
            return json.loads(data) if data else {}
        except Exception as e:
            logger.error(f"Redis 加载失败: {e}")
            return {}
            
    def save(self, session_id: str, data: Dict[str, Any]) -> None:
        try:
            self.client.setex(
                f"session:{session_id}",
                self.expire_seconds,
                json.dumps(data)
            )
        except Exception as e:
            logger.error(f"Redis 保存失败: {e}")
            
    def delete(self, session_id: str) -> None:
        try:
            self.client.delete(f"session:{session_id}")
        except Exception as e:
            logger.error(f"Redis 删除失败: {e}")

# 工厂方法
def get_session_store() -> SessionStore:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        logger.info(f"使用 Redis Session 存储: {redis_url}")
        return RedisSessionStore(redis_url)
    else:
        logger.info("使用本地文件 Session 存储")
        return FileSessionStore()

session_store = get_session_store()
"""
论文阅读多智能体系统 - FastAPI 后端入口（单用户版）。

本文件是薄入口，核心逻辑已拆分到 app/ 包中：
- app/main.py          应用工厂与生命周期
- app/state.py         应用状态（持久化 + 线程安全）
- app/schemas.py       Pydantic 请求/响应模型
- app/dependencies.py  单例与共享辅助函数
- app/routers/          REST 路由（documents / chat / history / features）
- app/websocket.py     WebSocket 多路复用端点

保留 `from api import app` 的兼容写法，start.bat / Dockerfile 无需改动。
"""
from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
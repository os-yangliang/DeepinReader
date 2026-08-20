"""FastAPI 应用工厂 - 组装路由与生命周期。"""
import os
import time as _time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import CORS_ALLOW_ORIGINS
from app.dependencies import UPLOAD_DIR
from app.websocket import websocket_endpoint
from app.routers import documents, chat, history, features

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时：清理超过 7 天的上传文件
    max_age_seconds = 7 * 24 * 3600
    now = _time.time()
    cleaned = 0
    for filename in os.listdir(UPLOAD_DIR):
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.isfile(filepath):
            if now - os.path.getmtime(filepath) > max_age_seconds:
                try:
                    os.remove(filepath)
                    cleaned += 1
                except OSError:
                    pass
    if cleaned > 0:
        logger.info(f"已清理 {cleaned} 个过期上传文件")

    yield  # 应用运行中

    # 关闭时
    logger.info("应用关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DeepinReader API",
        description="基于 LangChain + LangGraph 构建的智能论文分析与问答系统",
        version="2.0.0",
        lifespan=lifespan,
    )

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载静态文件目录，用于访问上传的 PDF
    app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    # 注册路由
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(history.router)
    app.include_router(features.router)

    # WebSocket 端点
    @app.websocket("/ws")
    async def ws_endpoint(ws):
        await websocket_endpoint(ws)

    # 根端点
    @app.get("/")
    async def root():
        return {"message": "论文阅读助手 API", "version": "2.0.0"}

    return app


app = create_app()
"""全局单例与共享辅助函数。"""
import os
import logging
from typing import Optional, Dict, Any

from agents.coordinator import PaperReaderCoordinator
from services.history_store import HistoryStoreService
from services.object_indexer import ObjectIndexer
from services.paper_schema import PaperProfile

logger = logging.getLogger(__name__)

# 上传文件存储目录
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Coordinator 单例缓存（避免每次请求都重新初始化 LLM + Embedding 模型）
_coordinator_instance: Optional[PaperReaderCoordinator] = None


def get_coordinator(require_llm: bool = True) -> PaperReaderCoordinator:
    """获取全局 Coordinator 单例。"""
    global _coordinator_instance
    if _coordinator_instance is None:
        init_mode = "加载 LLM + Embedding 模型" if require_llm else "仅加载解析/索引能力"
        logger.info(f"首次初始化 Coordinator（{init_mode}）...")
        _coordinator_instance = PaperReaderCoordinator(require_llm=require_llm)
        logger.info("Coordinator 初始化完成")
    elif require_llm and _coordinator_instance.llm_service is None:
        logger.info("升级 Coordinator 到完整 LLM 模式...")
        _coordinator_instance = PaperReaderCoordinator(
            require_llm=True, vector_store=_coordinator_instance.vector_store
        )
        logger.info("Coordinator 已升级到完整模式")
    return _coordinator_instance


# HistoryStoreService 单例缓存
_history_store_instance: Optional[HistoryStoreService] = None


def get_history_store() -> HistoryStoreService:
    """获取全局 HistoryStoreService 单例。"""
    global _history_store_instance
    if _history_store_instance is None:
        _history_store_instance = HistoryStoreService()
    return _history_store_instance


# 最近一次课题组讨论会话缓存（跨 WebSocket 与 REST 端点共享）
_lab_session_cache = None


def get_lab_session_cache():
    """获取最近的课题组讨论会话缓存。"""
    return _lab_session_cache


def set_lab_session_cache(session) -> None:
    """更新最近的课题组讨论会话缓存。"""
    global _lab_session_cache
    _lab_session_cache = session


def load_profile_for_document(document_id: str) -> Optional[PaperProfile]:
    """加载指定文档的结构化 profile。"""
    if not document_id:
        return None
    coordinator = get_coordinator()
    return ObjectIndexer(coordinator.vector_store).load_profile(document_id)


def build_profile_summary(profile: PaperProfile) -> Dict[str, Any]:
    """构建结构化 profile 摘要字典。"""
    return {
        "success": True,
        "document_id": profile.document_id,
        "title": profile.title,
        "abstract": profile.abstract[:1200],
        "counts": {
            "sections": len(profile.sections),
            "claims": len(profile.claims),
            "evidences": len(profile.evidences),
            "experiments": len(profile.experiments),
            "results": len(profile.results),
        },
        "contributions": profile.contributions[:8],
        "limitations": profile.limitations[:8],
        "keywords": profile.keywords[:12],
    }


def build_profile_detail(profile: PaperProfile) -> Dict[str, Any]:
    """构建结构化 profile 完整字典。"""
    payload = build_profile_summary(profile)
    payload.update({
        "sections": [section.model_dump() for section in profile.sections],
        "claims": [claim.model_dump() for claim in profile.claims],
        "evidences": [evidence.model_dump() for evidence in profile.evidences],
        "experiments": [experiment.model_dump() for experiment in profile.experiments],
        "results": [result.model_dump() for result in profile.results],
        "graph": profile.graph,
    })
    return payload
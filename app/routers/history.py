"""分析历史与对话历史路由。"""
import logging

from fastapi import APIRouter, HTTPException

from app.state import app_state
from app.dependencies import (
    get_coordinator,
    get_history_store,
    load_profile_for_document,
    build_profile_summary,
    build_profile_detail,
)
from app.schemas import (
    HistoryItem,
    HistoryListResponse,
    ProfileSummaryResponse,
    ProfileDetailResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/history", response_model=HistoryListResponse)
async def get_analysis_history():
    """获取分析历史记录列表。"""
    try:
        history_list = get_history_store().get_analysis_history_list()
        history_items = [
            HistoryItem(
                id=h["id"],
                filename=h["filename"],
                title=h.get("title", ""),
                file_type=h.get("file_type", ""),
                page_count=h.get("page_count", 0),
                word_count=h.get("word_count", 0),
                processing_time=h.get("processing_time", 0),
                analyzed_at=h.get("analyzed_at", ""),
            )
            for h in history_list
        ]
        return HistoryListResponse(
            history=history_items, current_id=app_state.current_history_id
        )
    except Exception as e:
        logger.error("获取历史记录失败: %s", e)
        return HistoryListResponse(history=[], current_id=None)


@router.get("/api/history/{history_id}")
async def get_history_detail(history_id: str):
    """获取指定历史记录详情。"""
    try:
        item = get_history_store().get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取详情失败: {e}")
        raise HTTPException(status_code=500, detail="服务错误")


@router.post("/api/history/{history_id}/load")
def load_history_item(history_id: str):
    """加载历史记录到当前状态。"""
    coordinator = get_coordinator()

    try:
        history_store = get_history_store()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        app_state.current_summary = item.get("summary", "")
        app_state.current_structure = item.get("structure", "")
        app_state.is_document_loaded = True
        app_state.current_history_id = history_id
        app_state.current_document_id = item.get("document_id", "")
        app_state.document_info = {
            "filename": item["filename"],
            "title": item.get("title", ""),
            "file_type": item.get("file_type", ""),
            "page_count": item.get("page_count", 0),
            "word_count": item.get("word_count", 0),
            "processing_time": item.get("processing_time", 0),
            "document_id": item.get("document_id", ""),
        }

        if app_state.current_document_id:
            coordinator.qa_agent.set_document_context(
                doc_id=app_state.current_document_id,
                paper_title=item.get("title", ""),
                paper_summary=app_state.current_summary[:500],
            )

        chat_history = history_store.get_chat_history(app_state.current_document_id)

        return {
            "success": True,
            "document_info": app_state.document_info,
            "structure": app_state.current_structure,
            "summary": app_state.current_summary,
            "chat_history": chat_history,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加载历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history/chat")
async def get_current_history_chat():
    """获取当前活跃文档的对话历史。"""
    if not app_state.current_document_id:
        return {"chat_history": []}
    try:
        chat_history = get_history_store().get_chat_history(app_state.current_document_id)
        return {"chat_history": chat_history}
    except Exception as e:
        logger.error(f"获取当前对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history/{history_id}/profile-summary", response_model=ProfileSummaryResponse)
def get_history_profile_summary(history_id: str):
    """获取指定历史记录对应论文的结构化 profile 摘要。"""
    history_store = get_history_store()
    item = history_store.get_analysis_history_detail(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    profile = load_profile_for_document(item.get("document_id", ""))
    if not profile:
        raise HTTPException(status_code=404, detail="该历史记录暂无结构化 profile")
    return ProfileSummaryResponse(**build_profile_summary(profile))


@router.get("/api/history/{history_id}/profile/detail", response_model=ProfileDetailResponse)
def get_history_profile_detail(history_id: str):
    """获取指定历史记录对应论文的完整结构化 profile。"""
    history_store = get_history_store()
    item = history_store.get_analysis_history_detail(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    profile = load_profile_for_document(item.get("document_id", ""))
    if not profile:
        raise HTTPException(status_code=404, detail="该历史记录暂无结构化 profile")
    return ProfileDetailResponse(**build_profile_detail(profile))


@router.delete("/api/history/{history_id}")
def delete_history_item(history_id: str):
    """删除指定历史记录。"""
    coordinator = get_coordinator()

    try:
        history_store = get_history_store()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        success = history_store.delete_analysis_history(history_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        if item.get("document_id"):
            try:
                coordinator.vector_store.delete_collection(item["document_id"])
            except Exception as e:
                logger.warning(f"删除向量集合失败: {e}")

        if app_state.current_history_id == history_id:
            app_state.clear()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history/{history_id}/chat")
async def get_history_chat(history_id: str):
    """获取指定历史记录的对话历史。"""
    try:
        history_store = get_history_store()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        document_id = item.get("document_id", "")
        chat_history = history_store.get_chat_history(document_id)

        return {"chat_history": chat_history}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
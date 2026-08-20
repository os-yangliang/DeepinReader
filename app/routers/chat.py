"""智能问答相关路由。"""
import json
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.state import app_state
from app.dependencies import get_coordinator, get_history_store
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """聊天问答。"""
    coordinator = get_coordinator()

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    if not app_state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传并解析论文文档")

    try:
        if app_state.current_document_id:
            get_history_store().add_chat_message(
                document_id=app_state.current_document_id,
                role="user",
                content=request.message,
                route_type="general",
                confidence=0.0,
                warnings=[],
                evidence_summary=[],
                reasoning_trace=[],
            )
    except Exception as e:
        logger.error(f"保存消息失败: {e}")

    result = coordinator.ask_question(request.message)

    if result.success:
        try:
            if app_state.current_document_id:
                get_history_store().add_chat_message(
                    document_id=app_state.current_document_id,
                    role="assistant",
                    content=result.answer,
                    source_chunks=result.source_chunks[:3] if result.source_chunks else [],
                    route_type=result.route_type,
                    confidence=result.confidence,
                    warnings=result.warnings,
                    evidence_summary=result.evidence_summary,
                    reasoning_trace=result.reasoning_trace,
                )
        except Exception as e:
            logger.error(f"保存回复失败: {e}")

        return ChatResponse(
            success=True,
            answer=result.answer,
            source_chunks=result.source_chunks[:3] if result.source_chunks else [],
            route_type=result.route_type,
            confidence=result.confidence,
            warnings=result.warnings,
            evidence_summary=result.evidence_summary,
            reasoning_trace=result.reasoning_trace,
            reasoning_paths=result.reasoning_paths,
            reasoning_chains=result.reasoning_chains,
            claim_nodes=result.claim_nodes,
            evidence_nodes=result.evidence_nodes,
            result_nodes=result.result_nodes,
            sufficiency_score=result.sufficiency_score,
            sufficiency_label=result.sufficiency_label,
            sufficiency_factors=result.sufficiency_factors,
            consistency_score=result.consistency_score,
            evidence_coverage=result.evidence_coverage,
        )
    else:
        return ChatResponse(
            success=False,
            answer=f"回答失败: {result.error_message}",
        )


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天问答。"""
    coordinator = get_coordinator()

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    if not app_state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传并解析论文文档")

    try:
        if app_state.current_document_id:
            get_history_store().add_chat_message(
                document_id=app_state.current_document_id,
                role="user",
                content=request.message,
                route_type="general",
                confidence=0.0,
                warnings=[],
                evidence_summary=[],
                reasoning_trace=[],
            )
    except Exception as e:
        logger.error(f"保存消息失败: {e}")

    async def generate():
        full_response = ""
        try:
            result = coordinator.ask_question(request.message)
            if not result.success:
                yield f"data: {json.dumps({'error': result.error_message or '问答失败'}, ensure_ascii=False)}\n\n"
                return

            for chunk in coordinator.ask_question_stream(request.message):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)

            try:
                if app_state.current_document_id:
                    get_history_store().add_chat_message(
                        document_id=app_state.current_document_id,
                        role="assistant",
                        content=result.answer,
                        source_chunks=result.source_chunks[:3] if result.source_chunks else [],
                        route_type=result.route_type,
                        confidence=result.confidence,
                        warnings=result.warnings,
                        evidence_summary=result.evidence_summary,
                        reasoning_trace=result.reasoning_trace,
                    )
            except Exception as e:
                logger.error(f"保存回复失败: {e}")

            yield f"data: {json.dumps({'done': True, 'route_type': result.route_type, 'confidence': result.confidence, 'warnings': result.warnings, 'evidence_summary': result.evidence_summary, 'reasoning_trace': result.reasoning_trace, 'reasoning_paths': result.reasoning_paths, 'reasoning_chains': result.reasoning_chains, 'claim_nodes': result.claim_nodes, 'evidence_nodes': result.evidence_nodes, 'result_nodes': result.result_nodes, 'sufficiency_score': result.sufficiency_score, 'sufficiency_label': result.sufficiency_label, 'sufficiency_factors': result.sufficiency_factors, 'consistency_score': result.consistency_score, 'evidence_coverage': result.evidence_coverage, 'source_chunks': result.source_chunks[:3] if result.source_chunks else []}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/api/suggestions")
def get_suggestions():
    """获取建议问题。"""
    if not app_state.is_document_loaded:
        return {"questions": []}

    coordinator = get_coordinator()
    questions = coordinator.get_suggested_questions()
    return {"questions": questions}


@router.post("/api/clear")
def clear_chat():
    """清除聊天历史。"""
    coordinator = get_coordinator()
    coordinator.clear_chat_history()

    if app_state.current_document_id:
        try:
            get_history_store().clear_chat_history(app_state.current_document_id)
        except Exception as e:
            logger.error(f"清除历史记录失败: {e}")

    return {"success": True}


@router.delete("/api/document")
def clear_document():
    """清除当前文档。"""
    coordinator = get_coordinator()
    coordinator.clear_chat_history()
    if app_state.current_document_id:
        app_state.remove_document(app_state.current_document_id)
    else:
        app_state.clear()
    return {"success": True}
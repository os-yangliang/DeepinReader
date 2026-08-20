"""WebSocket 统一流式端点 - 多路复用所有流式操作。"""
import asyncio
import logging
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect

from agents.lab.lab_session import LabSession
from app.state import app_state
from app.dependencies import (
    get_coordinator,
    get_history_store,
    set_lab_session_cache,
)

logger = logging.getLogger(__name__)

# 活跃的 WS 任务（用于取消）
_active_ws_tasks: Dict[str, asyncio.Task] = {}
_cancel_flags: Dict[str, bool] = {}


async def websocket_endpoint(ws: WebSocket):
    """统一 WebSocket 端点 - 多路复用所有流式操作。"""
    await ws.accept()

    async def send(msg_type: str, request_id: str, data: dict):
        """统一发送格式。"""
        try:
            await ws.send_json({"type": msg_type, "request_id": request_id, "data": data})
        except Exception:
            pass

    async def handle_analyze(request_id: str, data: dict):
        """流式分析。"""
        if not app_state.is_document_loaded:
            await send("error", request_id, {"message": "请先上传文档"})
            return
        coordinator = get_coordinator()
        try:
            full_analysis = ""
            for event in coordinator.stream_analysis():
                if _cancel_flags.get(request_id):
                    await send("cancelled", request_id, {})
                    return
                stage = event.get("stage", "")
                if stage == "analyzing" and event.get("chunk"):
                    full_analysis += event["chunk"]
                if stage == "done":
                    analysis_text = event.get("analysis", "")
                    app_state.current_summary = analysis_text
                    if app_state.current_document_id:
                        app_state.save_summary(app_state.current_document_id, analysis_text)
                    try:
                        doc_info = app_state.document_info or {}
                        history_id = get_history_store().add_analysis_history(
                            document_id=app_state.current_document_id or "",
                            filename=doc_info.get("filename", ""),
                            title=doc_info.get("title", ""),
                            file_type=doc_info.get("file_type", ""),
                            page_count=doc_info.get("page_count", 0),
                            word_count=doc_info.get("word_count", 0),
                            processing_time=0, structure="",
                            summary=analysis_text,
                        )
                        app_state.current_history_id = history_id
                    except Exception as e:
                        logger.error(f"保存历史失败: {e}")
                await send("stream", request_id, event)
                await asyncio.sleep(0.01)
            await send("done", request_id, {})
        except Exception as e:
            await send("error", request_id, {"message": str(e)})

    async def handle_chat(request_id: str, data: dict):
        """流式问答。"""
        message = data.get("message", "").strip()
        if not message:
            await send("error", request_id, {"message": "消息不能为空"})
            return
        if not app_state.is_document_loaded:
            await send("error", request_id, {"message": "请先上传文档"})
            return
        coordinator = get_coordinator()
        try:
            if app_state.current_document_id:
                get_history_store().add_chat_message(
                    document_id=app_state.current_document_id,
                    role="user",
                    content=message,
                    route_type="general",
                    confidence=0.0,
                    warnings=[],
                    evidence_summary=[],
                    reasoning_trace=[],
                )
        except Exception:
            pass
        full_response = ""
        result = None
        try:
            result = coordinator.ask_question(message)
            if not result.success:
                await send("error", request_id, {"message": result.error_message or "问答失败"})
                return
            full_response = result.answer
            for chunk in coordinator.ask_question_stream(message):
                if _cancel_flags.get(request_id):
                    await send("cancelled", request_id, {"partial": full_response})
                    return
                await send("stream", request_id, {"chunk": chunk})
                await asyncio.sleep(0.01)
            try:
                if app_state.current_document_id:
                    get_history_store().add_chat_message(
                        document_id=app_state.current_document_id,
                        role="assistant",
                        content=full_response,
                        source_chunks=result.source_chunks[:3] if result and result.source_chunks else [],
                        route_type=result.route_type if result else "general",
                        confidence=result.confidence if result else 0.0,
                        warnings=result.warnings if result else [],
                        evidence_summary=result.evidence_summary if result else [],
                        reasoning_trace=result.reasoning_trace if result else [],
                    )
            except Exception:
                pass
            await send("done", request_id, {
                "full_response": full_response,
                "route_type": result.route_type if result else "general",
                "confidence": result.confidence if result else 0.0,
                "warnings": result.warnings if result else [],
                "evidence_summary": result.evidence_summary if result else [],
                "reasoning_paths": result.reasoning_paths if result else [],
                "reasoning_chains": result.reasoning_chains if result else [],
                "sufficiency_score": result.sufficiency_score if result else 0.0,
                "sufficiency_label": result.sufficiency_label if result else "unknown",
                "sufficiency_factors": result.sufficiency_factors if result else [],
                "consistency_score": result.consistency_score if result else 0.0,
                "evidence_coverage": result.evidence_coverage if result else 0.0,
                "source_chunks": result.source_chunks[:3] if result and result.source_chunks else [],
            })
        except Exception as e:
            await send("error", request_id, {"message": str(e)})

    async def handle_translate(request_id: str, data: dict):
        """流式翻译 - 翻译使用 pdf2zh 子进程，不走 WS，强制 SSE 降级。"""
        await send("error", request_id, {"message": "translate_use_sse"})

    async def handle_compare(request_id: str, data: dict):
        """流式对比分析。"""
        doc_ids = data.get("doc_ids", [])
        if len(doc_ids) < 2 or len(doc_ids) > 3:
            await send("error", request_id, {"message": "请选择 2-3 篇论文"})
            return
        papers = []
        for did in doc_ids:
            if did not in app_state.documents:
                await send("error", request_id, {"message": f"文档 {did} 不存在"})
                return
            doc_data = app_state.documents[did]
            summary = doc_data.get("summary", "")
            if not summary:
                info = doc_data.get("document_info", {})
                await send("error", request_id, {"message": f"文档「{info.get('filename', did)}」尚未分析"})
                return
            info = doc_data.get("document_info", {})
            papers.append({
                "title": info.get("title") or info.get("filename", f"论文{len(papers)+1}"),
                "summary": summary[:6000],
            })
        papers_text = ""
        for i, p in enumerate(papers):
            papers_text += f"\n{'='*50}\n论文 {i+1}: {p['title']}\n{'='*50}\n{p['summary']}\n"
        col3 = " 论文3 |" if len(papers) > 2 else ""
        sep3 = "-------|" if len(papers) > 2 else ""
        prompt = f"""你是资深学术研究员，请对以下 {len(papers)} 篇论文进行深度对比分析。
{papers_text}
请按以下结构输出（Markdown 格式）：
## 📊 对比概览表
| 维度 | 论文1 | 论文2 |{col3}
|------|-------|-------|{sep3}
| 研究目标 | | |
| 核心方法 | | |
| 数据集 | | |
| 主要结果 | | |
| 创新点 | | |
## 🔬 方法对比
## 📈 实验与结果对比
## 💡 创新点与贡献对比
## ⚠️ 局限性对比
## 🎯 总结与建议
请使用中文，对专业术语附英文原文。"""
        coordinator = get_coordinator()
        try:
            full_text = ""
            for chunk in coordinator.llm_service.stream_chat(prompt):
                if _cancel_flags.get(request_id):
                    await send("cancelled", request_id, {})
                    return
                full_text += chunk
                await send("stream", request_id, {"stage": "analyzing", "chunk": chunk})
                await asyncio.sleep(0.01)
            await send("done", request_id, {"stage": "done", "analysis": full_text})
        except Exception as e:
            await send("error", request_id, {"message": str(e)})

    async def handle_lab_discuss(request_id: str, data: dict):
        """流式课题组讨论。"""
        if not app_state.is_document_loaded:
            await send("error", request_id, {"message": "请先上传文档"})
            return
        coordinator = get_coordinator()
        paper_summary = app_state.current_summary or ""
        paper_title = (app_state.document_info or {}).get("title", "")
        if not paper_summary:
            await send("error", request_id, {"message": "请先分析文档（需要分析结果作为讨论基础）"})
            return
        mode = data.get("mode", "quick")
        user_focus = data.get("user_focus", "")
        session = LabSession(
            llm_service=coordinator.llm_service,
            vector_store=coordinator.vector_store,
            paper_summary=paper_summary,
            paper_title=paper_title,
            mode=mode,
            user_focus=user_focus,
        )
        set_lab_session_cache(session)
        try:
            for event in session.run_discussion_stream():
                if _cancel_flags.get(request_id):
                    await send("cancelled", request_id, {})
                    return
                await send("stream", request_id, event)
                await asyncio.sleep(0.01)
            await send("done", request_id, {
                "proposal": session.proposal,
            })
        except Exception as e:
            logger.exception("课题组讨论失败")
            await send("error", request_id, {"message": str(e)})

    handlers = {
        "analyze": handle_analyze,
        "chat": handle_chat,
        "translate": handle_translate,
        "compare": handle_compare,
        "lab_discuss": handle_lab_discuss,
    }

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type", "")
            request_id = msg.get("request_id", "")

            if msg_type == "cancel":
                _cancel_flags[request_id] = True
                task = _active_ws_tasks.get(request_id)
                if task and not task.done():
                    task.cancel()
                await send("cancelled", request_id, {})
                continue

            if msg_type == "ping":
                await send("pong", request_id, {})
                continue

            handler = handlers.get(msg_type)
            if not handler:
                await send("error", request_id, {"message": f"未知消息类型: {msg_type}"})
                continue

            _cancel_flags[request_id] = False
            task = asyncio.create_task(handler(request_id, msg.get("data", {})))
            _active_ws_tasks[request_id] = task

            async def cleanup(rid, t):
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                finally:
                    _active_ws_tasks.pop(rid, None)
                    _cancel_flags.pop(rid, None)

            asyncio.create_task(cleanup(request_id, task))

    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
    finally:
        for rid, task in list(_active_ws_tasks.items()):
            _cancel_flags[rid] = True
            task.cancel()
        _active_ws_tasks.clear()
        _cancel_flags.clear()
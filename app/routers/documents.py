"""文档上传、解析、分析与多文档管理路由。"""
import os
import re
import json
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

import fitz  # PyMuPDF

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from config import SUPPORTED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.state import app_state
from app.dependencies import (
    UPLOAD_DIR,
    get_coordinator,
    get_history_store,
    load_profile_for_document,
    build_profile_summary,
    build_profile_detail,
)
from app.schemas import (
    DocumentInfoResponse,
    ProfileSummaryResponse,
    ProfileDetailResponse,
    SwitchDocumentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/status")
async def get_status():
    """获取系统状态。"""
    return {
        "is_document_loaded": app_state.is_document_loaded,
        "has_coordinator": True,
    }


@router.get("/api/document", response_model=DocumentInfoResponse)
async def get_document_info():
    """获取当前文档信息。"""
    return DocumentInfoResponse(
        is_loaded=app_state.is_document_loaded,
        info=app_state.document_info,
        structure=app_state.current_structure,
        summary=app_state.current_summary,
    )


async def _validate_upload(file: UploadFile, ext: str):
    if ext.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，请上传 PDF 或 Word 文档",
        )
    file_bytes = await file.read()
    max_bytes = int(MAX_FILE_SIZE_MB * 1024 * 1024)
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大：{len(file_bytes) / (1024 * 1024):.2f}MB，最大支持 {MAX_FILE_SIZE_MB}MB",
        )
    return file_bytes


@router.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档：保存 + 解析 + 建立向量索引（无 LLM，~5秒）。"""
    coordinator = get_coordinator(require_llm=False)

    try:
        filename = file.filename
        _, ext = os.path.splitext(filename)
        file_bytes = await _validate_upload(file, ext)

        file_id = str(uuid.uuid4())
        save_filename = f"{file_id}{ext}"
        save_path = os.path.join(UPLOAD_DIR, save_filename)

        def _save_and_index():
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            return coordinator.parse_and_index(file_bytes, filename)

        doc_info = await asyncio.to_thread(_save_and_index)
        doc_info["file_url"] = f"/api/uploads/{save_filename}"

        doc_id = doc_info.get("document_id", file_id)
        app_state.add_document(doc_id, doc_info)

        if coordinator.current_state is not None:
            coordinator.current_state["document_id"] = doc_id
            coordinator.current_state["summary"] = ""
            coordinator.current_state["structure_info"] = doc_info.get("structure_info", "")
            coordinator.current_state["keywords"] = ""
            coordinator.current_state["current_stage"] = "indexed"
        if coordinator.qa_agent:
            coordinator.qa_agent.set_document_context(
                doc_id=doc_id,
                paper_title=doc_info.get("title", ""),
                paper_summary="",
            )

        return {
            "success": True,
            "message": f"文档就绪：{doc_info.get('page_count', 0)} 页，{doc_info.get('word_count', 0)} 字",
            "document_info": doc_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文档上传解析失败")
        return {"success": False, "error": str(e)}


@router.post("/api/analyze/stream")
async def analyze_stream():
    """流式 AI 分析（独立于上传，需要先上传文档）。"""
    if not app_state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传文档")

    coordinator = get_coordinator()

    async def generate():
        try:
            full_analysis = ""
            for event in coordinator.stream_analysis():
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
                            processing_time=0,
                            structure="",
                            summary=event.get("analysis", ""),
                        )
                        app_state.current_history_id = history_id
                    except Exception as e:
                        logger.error(f"保存历史记录失败: {e}")

                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.exception("流式分析失败")
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/api/upload/stream")
async def upload_and_analyze_stream(file: UploadFile = File(...)):
    """流式上传并分析论文（SSE）。"""
    coordinator = get_coordinator()

    filename = file.filename
    _, ext = os.path.splitext(filename)
    file_bytes = await _validate_upload(file, ext)

    file_id = str(uuid.uuid4())
    save_filename = f"{file_id}{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_filename)
    await asyncio.to_thread(lambda: open(save_path, "wb").write(file_bytes))
    file_url = f"/api/uploads/{save_filename}"

    async def generate():
        try:
            for event in coordinator.process_document_stream(file_bytes, filename):
                stage = event.get("stage", "")

                if stage == "done":
                    doc_info = event.get("document_info", {})
                    doc_info["file_url"] = file_url

                    app_state.is_document_loaded = True
                    app_state.current_document_id = doc_info.get("document_id")
                    app_state.current_summary = event.get("analysis", "")
                    app_state.current_structure = ""
                    app_state.document_info = doc_info

                    try:
                        history_id = get_history_store().add_analysis_history(
                            document_id=app_state.current_document_id,
                            filename=doc_info.get("filename", ""),
                            title=doc_info.get("title", ""),
                            file_type=doc_info.get("file_type", ""),
                            page_count=doc_info.get("page_count", 0),
                            word_count=doc_info.get("word_count", 0),
                            processing_time=doc_info.get("processing_time", 0),
                            structure="",
                            summary=event.get("analysis", ""),
                        )
                        app_state.current_history_id = history_id
                    except Exception as e:
                        logger.error(f"保存历史记录失败: {e}")

                    event["document_info"] = doc_info

                if stage == "parsed":
                    event["file_url"] = file_url

                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.exception("流式分析失败")
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/api/documents")
async def list_documents():
    """获取所有已加载的文档列表。"""
    docs = []
    for doc_id, doc_data in app_state.documents.items():
        info = doc_data.get("document_info", {})
        docs.append({
            "document_id": doc_id,
            "filename": info.get("filename", ""),
            "title": info.get("title", ""),
            "file_url": info.get("file_url", ""),
            "page_count": info.get("page_count", 0),
            "is_active": doc_id == app_state.current_document_id,
            "has_summary": bool(doc_data.get("summary")),
        })
    return {"documents": docs, "active_id": app_state.current_document_id}


@router.post("/api/documents/switch")
def switch_document(request: SwitchDocumentRequest):
    """切换活跃文档。"""
    doc_id = request.document_id

    if doc_id not in app_state.documents:
        raise HTTPException(status_code=404, detail="文档不存在")

    if doc_id == app_state.current_document_id:
        return {
            "success": True,
            "message": "已经是当前文档",
            "document_info": app_state.document_info
        }

    success = app_state.switch_to(doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="切换失败")

    coordinator = get_coordinator()
    doc_info = app_state.document_info
    coordinator.qa_agent.set_document_context(
        doc_id=doc_id,
        paper_title=doc_info.get("title", ""),
        paper_summary=app_state.current_summary,
    )
    if coordinator.current_state:
        coordinator.current_state["summary"] = app_state.current_summary

    return {
        "success": True,
        "document_info": doc_info,
        "message": f"已切换到: {doc_info.get('filename', '')}"
    }


@router.delete("/api/documents/{doc_id}")
def remove_document(doc_id: str):
    """移除指定文档。"""
    if doc_id not in app_state.documents:
        raise HTTPException(status_code=404, detail="文档不存在")

    was_active = doc_id == app_state.current_document_id
    app_state.remove_document(doc_id)

    if was_active and app_state.is_document_loaded:
        coordinator = get_coordinator()
        new_id = app_state.current_document_id
        doc_info = app_state.document_info
        coordinator.qa_agent.set_document_context(
            doc_id=new_id,
            paper_title=doc_info.get("title", ""),
            paper_summary=app_state.current_summary,
        )

    return {"success": True}


@router.get("/api/document/profile", response_model=ProfileSummaryResponse)
def get_document_profile_summary():
    """获取当前文档的结构化 profile 摘要。"""
    profile = load_profile_for_document(app_state.current_document_id or "")
    if not profile:
        raise HTTPException(status_code=404, detail="当前文档暂无结构化 profile")
    return ProfileSummaryResponse(**build_profile_summary(profile))


@router.get("/api/document/profile/detail", response_model=ProfileDetailResponse)
def get_document_profile_detail():
    """获取当前文档的完整结构化 profile。"""
    profile = load_profile_for_document(app_state.current_document_id or "")
    if not profile:
        raise HTTPException(status_code=404, detail="当前文档暂无结构化 profile")
    return ProfileDetailResponse(**build_profile_detail(profile))


def _current_pdf_path() -> Optional[str]:
    """根据当前活跃文档的信息解析出 PDF 文件在本地的路径。"""
    doc_info = app_state.document_info or {}
    file_url = doc_info.get("file_url", "")
    if not file_url:
        return None
    filename = file_url.split("/")[-1]
    path = os.path.join(UPLOAD_DIR, filename)
    return path if os.path.exists(path) else None


@router.get("/api/document/toc")
def get_document_toc():
    """获取当前 PDF 的目录大纲（用于阅读器侧边导航）。"""
    path = _current_pdf_path()
    if not path:
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    try:
        with fitz.open(path) as doc:
            toc = []
            for level, title, page in doc.get_toc():
                toc.append({"level": level, "title": title, "page": max(1, page)})
            return {"toc": toc}
    except Exception as e:
        logger.exception("读取 PDF 目录失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/document/search")
def search_document(q: str = ""):
    """在当前 PDF 中全文搜索，返回匹配到的页码（用于引用跳转定位）。"""
    query = (q or "").strip()
    if not query:
        return {"matches": []}

    path = _current_pdf_path()
    if not path:
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    query = query[:100]
    try:
        with fitz.open(path) as doc:
            matches = []
            for pno in range(len(doc)):
                rects = doc[pno].search_for(query)
                if rects:
                    matches.append({"page": pno + 1, "count": len(rects)})
            return {"matches": matches}
    except Exception as e:
        logger.exception("PDF 全文搜索失败")
        raise HTTPException(status_code=500, detail=str(e))

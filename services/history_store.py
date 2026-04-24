"""
历史记录存储服务 - 使用 ChromaDB 持久化存储分析历史和对话记录
"""
import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from config import CHROMA_PERSIST_DIR
from services.chroma_client import get_chroma_client

logger = logging.getLogger(__name__)


class HistoryStoreService:
    """历史记录存储服务 - 基于 ChromaDB"""

    HISTORY_COLLECTION = "paper_analysis_history"
    CHAT_COLLECTION = "paper_chat_history"

    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or CHROMA_PERSIST_DIR
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = get_chroma_client(self.persist_directory)
        self.history_collection = self.client.get_or_create_collection(
            name=self.HISTORY_COLLECTION,
            metadata={"description": "论文分析历史记录"}
        )
        self.chat_collection = self.client.get_or_create_collection(
            name=self.CHAT_COLLECTION,
            metadata={"description": "论文问答对话记录"}
        )

    def add_analysis_history(
        self,
        document_id: str,
        filename: str,
        title: str = "",
        file_type: str = "",
        page_count: int = 0,
        word_count: int = 0,
        processing_time: float = 0,
        structure: str = "",
        summary: str = ""
    ) -> str:
        logger.debug("add_analysis_history called: document_id=%s, filename=%s", document_id, filename)
        history_id = f"h_{document_id}"
        analyzed_at = datetime.now().isoformat()
        metadata = {
            "document_id": document_id,
            "filename": filename,
            "title": title or "",
            "file_type": file_type or "",
            "page_count": page_count,
            "word_count": word_count,
            "processing_time": processing_time,
            "analyzed_at": analyzed_at,
            "structure": structure[:10000] if structure else "",
            "summary": summary[:10000] if summary else ""
        }
        content = f"{filename} {title} {file_type}"
        existing = self.history_collection.get(ids=[history_id])
        if existing and existing['ids']:
            self.history_collection.update(ids=[history_id], documents=[content], metadatas=[metadata])
        else:
            self.history_collection.add(ids=[history_id], documents=[content], metadatas=[metadata])
        return history_id

    def get_analysis_history_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            results = self.history_collection.get(include=["metadatas"])
            if not results or not results['ids']:
                return []
            history_list = []
            for i, history_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                history_list.append({
                    "id": history_id,
                    "document_id": metadata.get("document_id", ""),
                    "filename": metadata.get("filename", "未知文件"),
                    "title": metadata.get("title", ""),
                    "file_type": metadata.get("file_type", ""),
                    "page_count": metadata.get("page_count", 0),
                    "word_count": metadata.get("word_count", 0),
                    "processing_time": metadata.get("processing_time", 0),
                    "analyzed_at": metadata.get("analyzed_at", "")
                })
            history_list.sort(key=lambda x: x.get("analyzed_at", ""), reverse=True)
            return history_list[:limit]
        except Exception as e:
            logger.exception("获取历史记录失败: %s", e)
            return []

    def get_analysis_history_detail(self, history_id: str) -> Optional[Dict[str, Any]]:
        try:
            results = self.history_collection.get(ids=[history_id], include=["metadatas"])
            if not results or not results['ids']:
                return None
            metadata = results['metadatas'][0] if results['metadatas'] else {}
            return {
                "id": history_id,
                "document_id": metadata.get("document_id", ""),
                "filename": metadata.get("filename", "未知文件"),
                "title": metadata.get("title", ""),
                "file_type": metadata.get("file_type", ""),
                "page_count": metadata.get("page_count", 0),
                "word_count": metadata.get("word_count", 0),
                "processing_time": metadata.get("processing_time", 0),
                "analyzed_at": metadata.get("analyzed_at", ""),
                "structure": metadata.get("structure", ""),
                "summary": metadata.get("summary", "")
            }
        except Exception as e:
            logger.exception("获取历史记录详情失败: %s", e)
            return None

    def delete_analysis_history(self, history_id: str) -> bool:
        try:
            self.history_collection.delete(ids=[history_id])
            self._delete_chat_history_by_document(history_id)
            return True
        except Exception as e:
            logger.exception("删除历史记录失败: %s", e)
            return False

    def add_chat_message(
        self,
        document_id: str,
        role: str,
        content: str,
        source_chunks: Optional[List[str]] = None,
        route_type: str = "general",
        confidence: float = 0.0,
        warnings: Optional[List[str]] = None,
        evidence_summary: Optional[List[str]] = None,
        reasoning_trace: Optional[List[str]] = None,
    ) -> str:
        message_id = f"m_{document_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        timestamp = datetime.now().isoformat()
        metadata = {
            "document_id": document_id,
            "role": role,
            "content": content[:10000],
            "timestamp": timestamp,
            "source_chunks": json.dumps(source_chunks[:3] if source_chunks else [], ensure_ascii=False),
            "route_type": route_type or "general",
            "confidence": float(confidence or 0.0),
            "warnings": json.dumps((warnings or [])[:5], ensure_ascii=False),
            "evidence_summary": json.dumps((evidence_summary or [])[:5], ensure_ascii=False),
            "reasoning_trace": json.dumps((reasoning_trace or [])[:8], ensure_ascii=False),
        }
        self.chat_collection.add(
            ids=[message_id],
            documents=[content[:1000]],
            metadatas=[metadata]
        )
        return message_id

    def get_chat_history(self, document_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            results = self.chat_collection.get(where={"document_id": document_id}, include=["metadatas"])
            if not results or not results['ids']:
                return []
            chat_list = []
            for i, msg_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                chat_list.append({
                    "id": msg_id,
                    "role": metadata.get("role", "user"),
                    "content": metadata.get("content", ""),
                    "timestamp": metadata.get("timestamp", ""),
                    "source_chunks": self._loads_json_list(metadata.get("source_chunks", "[]")),
                    "route_type": metadata.get("route_type", "general"),
                    "confidence": float(metadata.get("confidence", 0.0) or 0.0),
                    "warnings": self._loads_json_list(metadata.get("warnings", "[]")),
                    "evidence_summary": self._loads_json_list(metadata.get("evidence_summary", "[]")),
                    "reasoning_trace": self._loads_json_list(metadata.get("reasoning_trace", "[]")),
                })
            chat_list.sort(key=lambda x: x.get("timestamp", ""))
            return chat_list[-limit:]
        except Exception as e:
            logger.exception("获取对话历史失败: %s", e)
            return []

    def clear_chat_history(self, document_id: str) -> bool:
        return self._delete_chat_history_by_document(document_id)

    def _delete_chat_history_by_document(self, history_id: str) -> bool:
        try:
            document_id = history_id.replace("h_", "") if history_id.startswith("h_") else history_id
            results = self.chat_collection.get(where={"document_id": document_id})
            if results and results['ids']:
                self.chat_collection.delete(ids=results['ids'])
            return True
        except Exception as e:
            logger.exception("删除对话历史失败: %s", e)
            return False

    def _loads_json_list(self, raw: str) -> List[str]:
        try:
            value = json.loads(raw)
            return value if isinstance(value, list) else []
        except Exception:
            return []

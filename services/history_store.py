"""
历史记录存储服务 - 使用 SQLite 持久化存储分析历史和对话记录
"""
import os
import json
import sqlite3
import threading
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from config import CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)

# 历史记录存放于 ChromaDB 同级目录下的独立 SQLite 文件，
# 避免将结构化元数据错误地存进向量数据库。
DEFAULT_DB_PATH = os.path.join(CHROMA_PERSIST_DIR, "paper_history.db")


class HistoryStoreService:
    """历史记录存储服务 - 基于 SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # FastAPI 可能在多线程中访问；SQLite 默认限制跨线程使用，
        # 这里关闭该限制并配合线程锁保证串行写入。
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_history (
                    history_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    filename TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    file_type TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL DEFAULT 0,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    processing_time REAL NOT NULL DEFAULT 0,
                    analyzed_at TEXT NOT NULL DEFAULT '',
                    structure TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    message_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    content TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL DEFAULT '',
                    source_chunks TEXT NOT NULL DEFAULT '[]',
                    route_type TEXT NOT NULL DEFAULT 'general',
                    confidence REAL NOT NULL DEFAULT 0,
                    warnings TEXT NOT NULL DEFAULT '[]',
                    evidence_summary TEXT NOT NULL DEFAULT '[]',
                    reasoning_trace TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_chat_document ON chat_history(document_id, timestamp);
                """
            )
            self._conn.commit()

    # ==================== 分析历史 ====================

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
        history_id = f"h_{document_id}"
        analyzed_at = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO analysis_history (
                    history_id, document_id, filename, title, file_type,
                    page_count, word_count, processing_time, analyzed_at,
                    structure, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(history_id) DO UPDATE SET
                    filename=excluded.filename,
                    title=excluded.title,
                    file_type=excluded.file_type,
                    page_count=excluded.page_count,
                    word_count=excluded.word_count,
                    processing_time=excluded.processing_time,
                    analyzed_at=excluded.analyzed_at,
                    structure=excluded.structure,
                    summary=excluded.summary
                """,
                (
                    history_id, document_id, filename, title, file_type,
                    int(page_count or 0), int(word_count or 0), float(processing_time or 0),
                    analyzed_at,
                    (structure or "")[:10000], (summary or "")[:10000],
                ),
            )
            self._conn.commit()
        return history_id

    def get_analysis_history_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    """
                    SELECT history_id, document_id, filename, title, file_type,
                           page_count, word_count, processing_time, analyzed_at
                    FROM analysis_history
                    ORDER BY analyzed_at DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()
            return [self._analysis_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.exception("获取历史记录失败: %s", e)
            return []

    def get_analysis_history_detail(self, history_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._lock:
                row = self._conn.execute(
                    """
                    SELECT history_id, document_id, filename, title, file_type,
                           page_count, word_count, processing_time, analyzed_at,
                           structure, summary
                    FROM analysis_history
                    WHERE history_id = ?
                    """,
                    (history_id,),
                ).fetchone()
            if row is None:
                return None
            return self._analysis_row_to_dict(row, include_detail=True)
        except Exception as e:
            logger.exception("获取历史记录详情失败: %s", e)
            return None

    def delete_analysis_history(self, history_id: str) -> bool:
        try:
            with self._lock:
                self._conn.execute(
                    "DELETE FROM analysis_history WHERE history_id = ?", (history_id,)
                )
                self._conn.commit()
            self._delete_chat_history_by_id(history_id)
            return True
        except Exception as e:
            logger.exception("删除历史记录失败: %s", e)
            return False

    # ==================== 对话历史 ====================

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
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO chat_history (
                    message_id, document_id, role, content, timestamp,
                    source_chunks, route_type, confidence,
                    warnings, evidence_summary, reasoning_trace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    document_id,
                    role,
                    (content or "")[:10000],
                    timestamp,
                    json.dumps(source_chunks[:3] if source_chunks else [], ensure_ascii=False),
                    route_type or "general",
                    float(confidence or 0.0),
                    json.dumps((warnings or [])[:5], ensure_ascii=False),
                    json.dumps((evidence_summary or [])[:5], ensure_ascii=False),
                    json.dumps((reasoning_trace or [])[:8], ensure_ascii=False),
                ),
            )
            self._conn.commit()
        return message_id

    def get_chat_history(self, document_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    """
                    SELECT message_id, role, content, timestamp, source_chunks,
                           route_type, confidence, warnings, evidence_summary, reasoning_trace
                    FROM chat_history
                    WHERE document_id = ?
                    ORDER BY timestamp ASC
                    """,
                    (document_id,),
                ).fetchall()
            chat_list = [self._chat_row_to_dict(r) for r in rows]
            return chat_list[-limit:]
        except Exception as e:
            logger.exception("获取对话历史失败: %s", e)
            return []

    def clear_chat_history(self, document_id: str) -> bool:
        return self._delete_chat_history_by_id(document_id)

    def _delete_chat_history_by_id(self, history_id_or_document_id: str) -> bool:
        try:
            document_id = (
                history_id_or_document_id.replace("h_", "")
                if history_id_or_document_id.startswith("h_")
                else history_id_or_document_id
            )
            with self._lock:
                self._conn.execute(
                    "DELETE FROM chat_history WHERE document_id = ?", (document_id,)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.exception("删除对话历史失败: %s", e)
            return False

    # ==================== 辅助方法 ====================

    def _analysis_row_to_dict(self, row: sqlite3.Row, include_detail: bool = False) -> Dict[str, Any]:
        data = {
            "id": row["history_id"],
            "document_id": row["document_id"],
            "filename": row["filename"] or "未知文件",
            "title": row["title"] or "",
            "file_type": row["file_type"] or "",
            "page_count": row["page_count"],
            "word_count": row["word_count"],
            "processing_time": row["processing_time"],
            "analyzed_at": row["analyzed_at"] or "",
        }
        if include_detail:
            data["structure"] = row["structure"] or ""
            data["summary"] = row["summary"] or ""
        return data

    def _chat_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["message_id"],
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["timestamp"],
            "source_chunks": self._loads_json_list(row["source_chunks"]),
            "route_type": row["route_type"],
            "confidence": float(row["confidence"] or 0.0),
            "warnings": self._loads_json_list(row["warnings"]),
            "evidence_summary": self._loads_json_list(row["evidence_summary"]),
            "reasoning_trace": self._loads_json_list(row["reasoning_trace"]),
        }

    def _loads_json_list(self, raw: str) -> List[str]:
        try:
            value = json.loads(raw)
            return value if isinstance(value, list) else []
        except Exception:
            return []
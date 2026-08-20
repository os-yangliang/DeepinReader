"""
应用状态管理 - 单用户、多文档，带磁盘持久化与线程安全。

状态以 JSON 形式持久化到磁盘，服务重启后可恢复；
对可变字段的读写通过 RLock 保护，并通过 __setattr__ 在字段变更时自动持久化，
从而兼容 api.py 中对 app_state.xxx 的直接赋值写法。
"""
import os
import json
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 状态文件存放于 ChromaDB 同级目录，便于与向量库数据统一管理。
_DEFAULT_STATE_PATH = os.path.join(
    os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"), "app_state.json"
)


class AppState:
    """单用户应用状态（支持多文档），可变状态通过锁保护并持久化。"""

    _PERSISTED_FIELDS = (
        "_documents",
        "current_document_id",
        "is_document_loaded",
        "current_summary",
        "current_structure",
        "document_info",
        "current_history_id",
    )

    def __init__(self, state_path: Optional[str] = None):
        object.__setattr__(self, "_state_path", state_path or _DEFAULT_STATE_PATH)
        object.__setattr__(self, "_lock", threading.RLock())
        object.__setattr__(self, "_loaded", False)
        self._load()

    # ---------- 持久化 ----------

    def _load(self) -> None:
        """从磁盘恢复状态（首次访问时调用，幂等）。"""
        with self._lock:
            if self._loaded:
                return
            data: dict = {}
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}
            except Exception as e:
                logger.warning("恢复应用状态失败，使用全新状态: %s", e)
                data = {}
            object.__setattr__(self, "_documents", data.get("documents", {}))
            object.__setattr__(self, "current_document_id", data.get("current_document_id"))
            object.__setattr__(self, "is_document_loaded", bool(data.get("is_document_loaded", False)))
            object.__setattr__(self, "current_summary", data.get("current_summary", ""))
            object.__setattr__(self, "current_structure", data.get("current_structure", ""))
            object.__setattr__(self, "document_info", data.get("document_info", {}))
            object.__setattr__(self, "current_history_id", data.get("current_history_id"))
            object.__setattr__(self, "_loaded", True)
            if data:
                logger.info("已从 %s 恢复应用状态", self._state_path)

    def _persist(self) -> None:
        """将当前状态写入磁盘（原子写入）。"""
        payload = {
            "documents": object.__getattribute__(self, "_documents"),
            "current_document_id": object.__getattribute__(self, "current_document_id"),
            "is_document_loaded": object.__getattribute__(self, "is_document_loaded"),
            "current_summary": object.__getattribute__(self, "current_summary"),
            "current_structure": object.__getattribute__(self, "current_structure"),
            "document_info": object.__getattribute__(self, "document_info"),
            "current_history_id": object.__getattribute__(self, "current_history_id"),
        }
        try:
            with self._lock:
                os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
                tmp_path = self._state_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, default=str)
                os.replace(tmp_path, self._state_path)
        except Exception as e:
            logger.warning("持久化应用状态失败: %s", e)

    # ---------- 透明属性访问（兼容 app_state.xxx 直接读写）----------

    def __getattr__(self, name):
        # 仅当普通查找失败时调用；确保字段在首次访问前完成加载。
        if name in self._PERSISTED_FIELDS:
            self._load()
            return object.__getattribute__(self, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        self._load()
        object.__setattr__(self, name, value)
        if name in self._PERSISTED_FIELDS:
            self._persist()

    @property
    def documents(self) -> Dict[str, dict]:
        """返回文档注册表（内部字典引用，调用方应只读使用）。"""
        self._load()
        return object.__getattribute__(self, "_documents")

    # ---------- 文档管理 ----------

    def add_document(self, doc_id: str, doc_info: dict, summary: str = ""):
        """添加文档并设为活跃。"""
        with self._lock:
            self._load()
            docs = object.__getattribute__(self, "_documents")
            docs[doc_id] = {"document_info": doc_info, "summary": summary}
            object.__setattr__(self, "current_document_id", doc_id)
            object.__setattr__(self, "is_document_loaded", True)
            object.__setattr__(self, "document_info", doc_info)
            object.__setattr__(self, "current_summary", summary)
            object.__setattr__(self, "current_structure", "")
            object.__setattr__(self, "current_history_id", None)
            self._persist()

    def switch_to(self, doc_id: str) -> bool:
        """切换活跃文档。"""
        with self._lock:
            self._load()
            docs = object.__getattribute__(self, "_documents")
            if doc_id not in docs:
                return False
            doc = docs[doc_id]
            object.__setattr__(self, "current_document_id", doc_id)
            object.__setattr__(self, "is_document_loaded", True)
            object.__setattr__(self, "document_info", doc["document_info"])
            object.__setattr__(self, "current_summary", doc.get("summary", ""))
            object.__setattr__(self, "current_structure", "")
            object.__setattr__(self, "current_history_id", None)
            self._persist()
            return True

    def remove_document(self, doc_id: str):
        """移除文档。"""
        with self._lock:
            self._load()
            docs = object.__getattribute__(self, "_documents")
            if doc_id in docs:
                del docs[doc_id]
            if object.__getattribute__(self, "current_document_id") == doc_id:
                if docs:
                    next_id = next(iter(docs))
                    doc = docs[next_id]
                    object.__setattr__(self, "current_document_id", next_id)
                    object.__setattr__(self, "is_document_loaded", True)
                    object.__setattr__(self, "document_info", doc["document_info"])
                    object.__setattr__(self, "current_summary", doc.get("summary", ""))
                    object.__setattr__(self, "current_structure", "")
                    object.__setattr__(self, "current_history_id", None)
                else:
                    self._reset_fields()
            self._persist()

    def save_summary(self, doc_id: str, summary: str):
        """保存分析结果到文档。"""
        with self._lock:
            self._load()
            docs = object.__getattribute__(self, "_documents")
            if doc_id in docs:
                docs[doc_id]["summary"] = summary
            if object.__getattribute__(self, "current_document_id") == doc_id:
                object.__setattr__(self, "current_summary", summary)
            self._persist()

    def clear(self):
        """重置所有状态。"""
        with self._lock:
            self._load()
            self._reset_fields()
            self._persist()

    def _reset_fields(self):
        object.__setattr__(self, "_documents", {})
        object.__setattr__(self, "current_document_id", None)
        object.__setattr__(self, "is_document_loaded", False)
        object.__setattr__(self, "current_summary", "")
        object.__setattr__(self, "current_structure", "")
        object.__setattr__(self, "document_info", {})
        object.__setattr__(self, "current_history_id", None)


# 全局单例
app_state = AppState()
"""共享的论文索引加载工具：优先复用已预索引的 ChromaDB collection。"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.coordinator import PaperReaderCoordinator
from config import COLLECTION_NAME
from services.chroma_client import get_chroma_client
from services.document_parser import DocumentParser


def compute_doc_id(filename: str, content: str) -> str:
    hash_input = f"{filename}_{len(content)}_{content[:1000]}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


def collection_exists(doc_id: str) -> bool:
    client = get_chroma_client()
    collection_name = f"{COLLECTION_NAME}_{doc_id}"
    return any(c.name == collection_name for c in client.list_collections())


def load_paper_reuse(coordinator: PaperReaderCoordinator, paper_path: str) -> Dict:
    """加载论文：若 ChromaDB 中已存在索引则直接复用，否则执行完整 parse_and_index。"""
    path = PROJECT_ROOT / paper_path if not os.path.isabs(paper_path) else Path(paper_path)
    with path.open("rb") as f:
        file_bytes = f.read()

    parsed = DocumentParser().parse_from_bytes(file_bytes, path.name)
    doc_id = compute_doc_id(parsed.filename, parsed.content)
    if collection_exists(doc_id):
        coordinator.vector_store.load_collection(doc_id)
        coordinator.qa_agent.set_document_context(doc_id=doc_id, paper_title=parsed.title or "", paper_summary="")
        return {
            "filename": parsed.filename,
            "title": parsed.title,
            "file_type": parsed.file_type,
            "page_count": parsed.page_count,
            "word_count": parsed.word_count,
            "document_id": doc_id,
            "structure_info": "",
            "reused": True,
        }

    return {**coordinator.parse_and_index(file_bytes, path.name), "reused": False}

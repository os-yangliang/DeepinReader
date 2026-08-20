"""API 请求/响应 Pydantic 模型。"""
from typing import List, Dict, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    success: bool
    answer: str
    source_chunks: List[str] = []
    route_type: str = "general"
    confidence: float = 0.0
    warnings: List[str] = []
    evidence_summary: List[str] = []
    reasoning_trace: List[str] = []
    reasoning_paths: List[List[str]] = []
    reasoning_chains: List[dict] = []
    claim_nodes: List[str] = []
    evidence_nodes: List[str] = []
    result_nodes: List[str] = []
    sufficiency_score: float = 0.0
    sufficiency_label: str = "unknown"
    sufficiency_factors: List[str] = []
    consistency_score: float = 0.0
    evidence_coverage: float = 0.0


class AnalysisResponse(BaseModel):
    success: bool
    status: str
    document_info: dict = {}
    structure: str = ""
    summary: str = ""
    error: str = ""


class DocumentInfoResponse(BaseModel):
    is_loaded: bool
    info: dict = {}
    structure: str = ""
    summary: str = ""


class HistoryItem(BaseModel):
    id: str
    filename: str
    title: str = ""
    file_type: str = ""
    page_count: int = 0
    word_count: int = 0
    processing_time: float = 0
    analyzed_at: str = ""


class HistoryListResponse(BaseModel):
    history: List[HistoryItem] = []
    current_id: Optional[str] = None


class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str = ""
    source_chunks: List[str] = []
    route_type: str = "general"
    confidence: float = 0.0
    warnings: List[str] = []
    evidence_summary: List[str] = []
    reasoning_trace: List[str] = []


class ProfileSummaryResponse(BaseModel):
    success: bool
    document_id: str = ""
    title: str = ""
    abstract: str = ""
    counts: Dict[str, int] = {}
    contributions: List[str] = []
    limitations: List[str] = []
    keywords: List[str] = []


class ProfileDetailResponse(ProfileSummaryResponse):
    sections: List[dict] = []
    claims: List[dict] = []
    evidences: List[dict] = []
    experiments: List[dict] = []
    results: List[dict] = []
    graph: Dict[str, List[str]] = {}


class TranslateTextRequest(BaseModel):
    text: str


class ExportRequest(BaseModel):
    annotations: List[dict] = []


class SearchRequest(BaseModel):
    query: str = ""
    limit: int = 10


class CompareRequest(BaseModel):
    doc_ids: List[str]


class SwitchDocumentRequest(BaseModel):
    document_id: str


class LabDiscussRequest(BaseModel):
    mode: str = "quick"
    user_focus: str = ""

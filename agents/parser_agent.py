"""
文档解析 Agent - 负责解析和预处理论文文档
"""
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import hashlib
import time

from services.document_parser import DocumentParser, ParsedDocument
from services.vector_store import VectorStoreService
from services.llm_service import LLMService
from services.section_parser import SectionParser
from services.scholarly_object_extractor import ScholarlyObjectExtractor
from services.paper_graph_builder import PaperGraphBuilder
from services.object_indexer import ObjectIndexer
from services.paper_schema import PaperProfile
from prompts.templates import STRUCTURE_ANALYSIS_PROMPT


@dataclass
class ParserResult:
    """解析结果"""
    success: bool
    document_id: str
    parsed_doc: Optional[ParsedDocument] = None
    paper_profile: Optional[PaperProfile] = None
    structure_info: str = ""
    error_message: str = ""
    processing_time: float = 0.0


class ParserAgent:
    """文档解析 Agent"""

    def __init__(
        self,
        document_parser: Optional[DocumentParser] = None,
        vector_store: Optional[VectorStoreService] = None,
        llm_service: Optional[LLMService] = None,
        llm_factory: Optional[Callable[[], LLMService]] = None
    ):
        self.document_parser = document_parser or DocumentParser()
        self.vector_store = vector_store or VectorStoreService()
        self.llm_service = llm_service
        self.llm_factory = llm_factory or LLMService
        self.section_parser = SectionParser()
        self.object_extractor = None
        self.graph_builder = PaperGraphBuilder()
        self.object_indexer = ObjectIndexer(self.vector_store)


    def _get_llm_service(self) -> LLMService:
        if self.llm_service is None:
            self.llm_service = self.llm_factory()
        return self.llm_service

    def _generate_document_id(self, filename: str, content: str) -> str:
        """生成文档唯一ID"""
        hash_input = f"{filename}_{len(content)}_{content[:1000]}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def parse_document(self, file_path: str) -> ParserResult:
        start_time = time.time()
        try:
            parsed_doc = self.document_parser.parse(file_path)
            doc_id = self._generate_document_id(parsed_doc.filename, parsed_doc.content)
            paper_profile = self._build_paper_profile(doc_id, parsed_doc)
            structure_info = self._analyze_structure(parsed_doc, paper_profile)
            self._store_document(doc_id, parsed_doc, paper_profile)
            return ParserResult(
                success=True,
                document_id=doc_id,
                parsed_doc=parsed_doc,
                paper_profile=paper_profile,
                structure_info=structure_info,
                processing_time=time.time() - start_time,
            )
        except Exception as e:
            return ParserResult(
                success=False,
                document_id="",
                error_message=str(e),
                processing_time=time.time() - start_time,
            )

    def parse_document_from_bytes(self, file_bytes: bytes, filename: str) -> ParserResult:
        start_time = time.time()
        try:
            parsed_doc = self.document_parser.parse_from_bytes(file_bytes, filename)
            doc_id = self._generate_document_id(parsed_doc.filename, parsed_doc.content)
            paper_profile = self._build_paper_profile(doc_id, parsed_doc)
            structure_info = self._analyze_structure(parsed_doc, paper_profile)
            self._store_document(doc_id, parsed_doc, paper_profile)
            return ParserResult(
                success=True,
                document_id=doc_id,
                parsed_doc=parsed_doc,
                paper_profile=paper_profile,
                structure_info=structure_info,
                processing_time=time.time() - start_time,
            )
        except Exception as e:
            return ParserResult(
                success=False,
                document_id="",
                error_message=str(e),
                processing_time=time.time() - start_time,
            )

    def _build_paper_profile(self, doc_id: str, parsed_doc: ParsedDocument) -> PaperProfile:
        sections = self.section_parser.parse(parsed_doc.content)
        try:
            extractor = self.object_extractor or ScholarlyObjectExtractor(self._get_llm_service())
            self.object_extractor = extractor
            extracted = extractor.extract(sections)
        except Exception:
            extracted = {
                "claims": [],
                "evidences": [],
                "experiments": [],
                "results": [],
                "contributions": [],
                "limitations": [],
            }
        profile = self.graph_builder.build(doc_id, parsed_doc.title, sections, extracted)
        return profile

    def _analyze_structure(self, parsed_doc: ParsedDocument, paper_profile: Optional[PaperProfile] = None) -> str:
        if paper_profile and paper_profile.sections:
            lines = ["## 结构化章节"]
            for section in paper_profile.sections[:12]:
                lines.append(f"- [{section.section_type.value}] {section.title}")
            if paper_profile.claims:
                lines.append("\n## 主张数量")
                lines.append(f"- 识别到 {len(paper_profile.claims)} 条主张")
            if paper_profile.evidences:
                lines.append(f"- 识别到 {len(paper_profile.evidences)} 条证据")
            return "\n".join(lines)

        try:
            content_preview = parsed_doc.content[:8000] if len(parsed_doc.content) > 8000 else parsed_doc.content
            return self._get_llm_service().generate_with_prompt(
                STRUCTURE_ANALYSIS_PROMPT,
                {"paper_content": content_preview}
            )
        except Exception as e:
            return f"结构分析失败: {str(e)}"

    def _store_document(self, doc_id: str, parsed_doc: ParsedDocument, paper_profile: Optional[PaperProfile] = None) -> None:
        self.vector_store.create_collection(doc_id)
        base_metadata = {
            "filename": parsed_doc.filename,
            "file_type": parsed_doc.file_type,
            "title": parsed_doc.title,
            "page_count": parsed_doc.page_count,
            "object_type": "chunk",
        }
        if parsed_doc.chunks:
            metadatas = [base_metadata.copy() for _ in parsed_doc.chunks]
            self.vector_store.add_documents(parsed_doc.chunks, metadatas)
        else:
            self.vector_store.add_document_with_splitting(parsed_doc.content, base_metadata)

        if paper_profile:
            self.object_indexer.persist_profile(paper_profile)
            self.object_indexer.index_profile(paper_profile)

    def get_document_info(self, parsed_doc: ParsedDocument) -> Dict[str, Any]:
        return {
            "filename": parsed_doc.filename,
            "file_type": parsed_doc.file_type,
            "title": parsed_doc.title,
            "page_count": parsed_doc.page_count,
            "word_count": parsed_doc.word_count,
            "chunk_count": len(parsed_doc.chunks),
            "metadata": parsed_doc.metadata,
        }

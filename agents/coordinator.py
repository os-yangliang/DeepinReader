"""
论文阅读协调 Agent - 基于 LangGraph 的工作流编排
"""
from typing import TypedDict, Optional, List, Dict, Literal
from dataclasses import dataclass, field
import time
import logging

from langgraph.graph import StateGraph, END

from services.document_parser import ParsedDocument
from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from services.object_indexer import ObjectIndexer
from agents.parser_agent import ParserAgent
from agents.summarizer_agent import SummarizerAgent
from agents.qa_agent import QAAgent, QAResult
from prompts.templates import PAPER_ANALYSIS_PROMPT, TRANSLATE_PROMPT

logger = logging.getLogger(__name__)


class PaperReaderState(TypedDict):
    file_path: Optional[str]
    file_bytes: Optional[bytes]
    filename: Optional[str]
    user_question: Optional[str]
    current_stage: str
    error_message: Optional[str]
    document_id: Optional[str]
    parsed_doc: Optional[ParsedDocument]
    structure_info: Optional[str]
    summary: Optional[str]
    keywords: Optional[str]
    qa_answer: Optional[str]
    source_chunks: List[str]
    processing_times: Dict[str, float]


@dataclass
class ProcessingResult:
    success: bool
    stage: str
    document_id: str = ""
    paper_title: str = ""
    structure_info: str = ""
    summary: str = ""
    keywords: str = ""
    qa_answer: str = ""
    source_chunks: List[str] = field(default_factory=list)
    error_message: str = ""
    total_time: float = 0.0
    stage_times: Dict[str, float] = field(default_factory=dict)


class PaperReaderCoordinator:
    def __init__(self, llm_service: Optional[LLMService] = None, vector_store: Optional[VectorStoreService] = None, require_llm: bool = True):
        self.llm_service = llm_service
        self._llm_required = require_llm
        if require_llm and self.llm_service is None:
            try:
                self.llm_service = LLMService()
            except ValueError as e:
                raise ValueError(f"LLM 初始化失败: {str(e)}")

        try:
            self.vector_store = vector_store or VectorStoreService()
        except Exception as e:
            raise ValueError(f"向量数据库初始化失败: {str(e)}")

        self.parser_agent = ParserAgent(vector_store=self.vector_store, llm_service=self.llm_service)
        self.summarizer_agent = SummarizerAgent(llm_service=self.llm_service) if self.llm_service else None
        self.qa_agent = QAAgent(llm_service=self.llm_service, vector_store=self.vector_store) if self.llm_service else None
        self.object_indexer = ObjectIndexer(self.vector_store)
        self.current_state: Optional[PaperReaderState] = None
        self.workflow = self._build_workflow() if self.llm_service else None

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(PaperReaderState)
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("qa", self._qa_node)
        workflow.add_node("error", self._error_node)
        workflow.set_entry_point("parse")
        workflow.add_conditional_edges("parse", self._route_after_parse, {"summarize": "summarize", "error": "error"})
        workflow.add_conditional_edges("summarize", self._route_after_summarize, {"end": END, "error": "error"})
        workflow.add_edge("qa", END)
        workflow.add_edge("error", END)
        return workflow.compile()

    def _parse_node(self, state: PaperReaderState) -> PaperReaderState:
        start_time = time.time()
        try:
            if state.get("file_bytes") and state.get("filename"):
                result = self.parser_agent.parse_document_from_bytes(state["file_bytes"], state["filename"])
            elif state.get("file_path"):
                result = self.parser_agent.parse_document(state["file_path"])
            else:
                return {**state, "current_stage": "error", "error_message": "缺少文件路径或文件内容"}
            if result.success:
                processing_times = state.get("processing_times", {})
                processing_times["parse"] = time.time() - start_time
                return {
                    **state,
                    "current_stage": "parsed",
                    "document_id": result.document_id,
                    "parsed_doc": result.parsed_doc,
                    "structure_info": result.structure_info,
                    "processing_times": processing_times,
                }
            return {**state, "current_stage": "error", "error_message": result.error_message}
        except Exception as e:
            return {**state, "current_stage": "error", "error_message": str(e)}

    def _summarize_node(self, state: PaperReaderState) -> PaperReaderState:
        start_time = time.time()
        try:
            parsed_doc = state.get("parsed_doc")
            if not parsed_doc:
                return {**state, "current_stage": "error", "error_message": "文档未解析，无法生成摘要"}
            result = self.summarizer_agent.generate_summary(parsed_doc)
            processing_times = state.get("processing_times", {})
            processing_times["summarize"] = time.time() - start_time
            if result.success:
                return {
                    **state,
                    "current_stage": "summarized",
                    "summary": result.summary,
                    "keywords": result.keywords,
                    "processing_times": processing_times,
                }
            return {
                **state,
                "current_stage": "error",
                "error_message": result.error_message,
                "processing_times": processing_times,
            }
        except Exception as e:
            return {**state, "current_stage": "error", "error_message": str(e)}

    def _qa_node(self, state: PaperReaderState) -> PaperReaderState:
        start_time = time.time()
        try:
            question = state.get("user_question")
            if not question:
                return {**state, "current_stage": "error", "error_message": "未提供问题"}
            result = self.qa_agent.ask(question)
            processing_times = state.get("processing_times", {})
            processing_times["qa"] = time.time() - start_time
            if result.success:
                return {
                    **state,
                    "current_stage": "answered",
                    "qa_answer": result.answer,
                    "source_chunks": result.source_chunks,
                    "processing_times": processing_times,
                }
            return {
                **state,
                "current_stage": "error",
                "error_message": result.error_message,
                "processing_times": processing_times,
            }
        except Exception as e:
            return {**state, "current_stage": "error", "error_message": str(e)}

    def _error_node(self, state: PaperReaderState) -> PaperReaderState:
        return {**state, "current_stage": "failed"}

    def _route_after_parse(self, state: PaperReaderState) -> Literal["summarize", "error"]:
        return "summarize" if state.get("current_stage") == "parsed" else "error"

    def _route_after_summarize(self, state: PaperReaderState) -> Literal["end", "error"]:
        return "end" if state.get("current_stage") == "summarized" else "error"

    def process_document(self, file_path: Optional[str] = None, file_bytes: Optional[bytes] = None, filename: Optional[str] = None) -> ProcessingResult:
        start_time = time.time()
        initial_state: PaperReaderState = {
            "file_path": file_path,
            "file_bytes": file_bytes,
            "filename": filename,
            "user_question": None,
            "current_stage": "start",
            "error_message": None,
            "document_id": None,
            "parsed_doc": None,
            "structure_info": None,
            "summary": None,
            "keywords": None,
            "qa_answer": None,
            "source_chunks": [],
            "processing_times": {},
        }
        try:
            if not self.workflow:
                raise ValueError("LLM 未初始化，无法执行完整分析流程")
            final_state = self.workflow.invoke(initial_state)
            self.current_state = final_state
            if final_state.get("document_id"):
                parsed_doc = final_state.get("parsed_doc")
                self.qa_agent.set_document_context(
                    doc_id=final_state["document_id"],
                    paper_title=parsed_doc.title if parsed_doc else "",
                    paper_summary=(final_state.get("summary") or "")[:500],
                )
            total_time = time.time() - start_time
            if final_state.get("current_stage") in ["summarized", "answered"]:
                parsed_doc = final_state.get("parsed_doc")
                return ProcessingResult(
                    success=True,
                    stage=final_state["current_stage"],
                    document_id=final_state.get("document_id", ""),
                    paper_title=parsed_doc.title if parsed_doc else "",
                    structure_info=final_state.get("structure_info") or "",
                    summary=final_state.get("summary") or "",
                    keywords=final_state.get("keywords") or "",
                    total_time=total_time,
                    stage_times=final_state.get("processing_times", {}),
                )
            return ProcessingResult(
                success=False,
                stage=final_state.get("current_stage", "unknown"),
                error_message=final_state.get("error_message") or "未知错误",
                total_time=total_time,
            )
        except Exception as e:
            logger.exception("process_document 执行失败")
            return ProcessingResult(success=False, stage="exception", error_message=str(e), total_time=time.time() - start_time)

    def ask_question(self, question: str) -> QAResult:
        return self.qa_agent.ask(question)

    def ask_question_stream(self, question: str):
        yield from self.qa_agent.ask_stream(question)

    def get_suggested_questions(self) -> List[str]:
        return self.qa_agent.get_suggested_questions()

    def clear_chat_history(self) -> None:
        self.qa_agent.clear_history()

    def parse_and_index(self, file_bytes: bytes, filename: str) -> dict:
        result = self.parser_agent.parse_document_from_bytes(file_bytes, filename)
        if not result.success or not result.parsed_doc:
            raise ValueError(result.error_message or "文档解析失败")
        parsed_doc = result.parsed_doc
        doc_id = result.document_id
        self.current_state = {"document_id": doc_id, "parsed_doc": parsed_doc, "summary": "", "structure_info": result.structure_info, "keywords": "", "current_stage": "indexed"}
        if self.qa_agent:
            self.qa_agent.set_document_context(doc_id=doc_id, paper_title=parsed_doc.title or "", paper_summary="")
        return {"filename": parsed_doc.filename, "title": parsed_doc.title, "file_type": parsed_doc.file_type, "page_count": parsed_doc.page_count, "word_count": parsed_doc.word_count, "document_id": doc_id, "structure_info": result.structure_info}

    def stream_analysis(self):
        if not self.current_state or not self.current_state.get("parsed_doc"):
            yield {"stage": "error", "message": "请先上传文档"}
            return
        parsed_doc = self.current_state["parsed_doc"]
        content = parsed_doc.content
        max_len = 15000
        if len(content) > max_len:
            head = int(max_len * 0.6)
            tail = max_len - head
            content = content[:head] + "\n\n...(中间部分省略)...\n\n" + content[-tail:]
        yield {"stage": "progress", "percent": 10, "step": "preparing", "message": "正在准备分析..."}
        if not self.llm_service or not self.qa_agent:
            yield {"stage": "error", "message": "LLM 未初始化，无法执行分析"}
            return
        prompt = PAPER_ANALYSIS_PROMPT.format(paper_content=content)
        yield {"stage": "progress", "percent": 30, "step": "llm_start", "message": "AI 模型开始分析..."}
        full_response = ""
        chunk_count = 0
        try:
            for chunk in self.llm_service.stream_chat(prompt):
                full_response += chunk
                chunk_count += 1
                yield {"stage": "analyzing", "chunk": chunk}
                if chunk_count % 10 == 0:
                    progress = min(35 + len(full_response) // 80, 90)
                    yield {"stage": "progress", "percent": progress, "step": "llm_running", "message": "正在深度分析论文内容..."}
            self.current_state["summary"] = full_response
            if self.current_state.get("document_id"):
                self.qa_agent.set_document_context(doc_id=self.current_state["document_id"], paper_title=parsed_doc.title or "", paper_summary=full_response[:500])
            yield {"stage": "done", "analysis": full_response, "document_info": {"filename": parsed_doc.filename, "title": parsed_doc.title, "file_type": parsed_doc.file_type, "page_count": parsed_doc.page_count, "word_count": parsed_doc.word_count, "document_id": self.current_state.get("document_id", "")}}
        except Exception as e:
            yield {"stage": "error", "message": str(e)}

    def process_document_stream(self, file_bytes: bytes, filename: str):
        try:
            result = self.parser_agent.parse_document_from_bytes(file_bytes, filename)
            if not result.success or not result.parsed_doc:
                yield {"stage": "error", "message": result.error_message or "文档解析失败"}
                return
            parsed_doc = result.parsed_doc
            self.current_state = {"document_id": result.document_id, "parsed_doc": parsed_doc, "summary": "", "structure_info": result.structure_info, "keywords": "", "current_stage": "indexed"}
            if self.qa_agent:
                self.qa_agent.set_document_context(result.document_id, parsed_doc.title or "", "")
            yield {"stage": "parsed", "document_info": {"filename": parsed_doc.filename, "title": parsed_doc.title, "file_type": parsed_doc.file_type, "page_count": parsed_doc.page_count, "word_count": parsed_doc.word_count, "document_id": result.document_id}}
            for event in self.stream_analysis():
                yield event
        except Exception as e:
            yield {"stage": "error", "message": str(e)}

    def translate_stream(self, text: str):
        prompt = TRANSLATE_PROMPT.format(text=text)
        for chunk in self.llm_service.stream_chat(prompt):
            yield chunk
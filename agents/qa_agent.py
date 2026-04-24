"""
问答 Agent - 基于结构化解析和 Claim-Evidence 的论文问答
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import time
import logging
import json

from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from services.tools import tool_service
from services.paper_schema import (
    PaperProfile,
    EvidenceBundle,
    QuestionRoute,
)
from services.subgraph_retriever import SubgraphRetriever
from services.object_indexer import ObjectIndexer
from prompts.templates import CLAIM_EVIDENCE_ANSWER_PROMPT
from agents.question_router_agent import QuestionRouterAgent
from agents.verifier_agent import VerifierAgent

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    success: bool
    answer: str = ""
    source_chunks: List[str] = None
    route_type: str = "general"
    evidence_summary: List[str] = None
    warnings: List[str] = None
    reasoning_trace: List[str] = None
    reasoning_paths: List[List[str]] = None
    claim_nodes: List[str] = None
    evidence_nodes: List[str] = None
    result_nodes: List[str] = None
    confidence: float = 0.0
    error_message: str = ""
    processing_time: float = 0.0

    def __post_init__(self):
        if self.source_chunks is None:
            self.source_chunks = []
        if self.evidence_summary is None:
            self.evidence_summary = []
        if self.warnings is None:
            self.warnings = []
        if self.reasoning_trace is None:
            self.reasoning_trace = []
        if self.reasoning_paths is None:
            self.reasoning_paths = []
        if self.claim_nodes is None:
            self.claim_nodes = []
        if self.evidence_nodes is None:
            self.evidence_nodes = []
        if self.result_nodes is None:
            self.result_nodes = []


class QAAgent:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        vector_store: Optional[VectorStoreService] = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.vector_store = vector_store or VectorStoreService()
        self.chat_history: List[Dict[str, str]] = []
        self.current_doc_id: Optional[str] = None
        self.current_paper_title: str = ""
        self.current_paper_summary: str = ""
        self.current_profile: Optional[PaperProfile] = None
        self._cached_suggestions: Optional[List[str]] = None
        self.object_indexer = ObjectIndexer(self.vector_store)
        self.subgraph_retriever = SubgraphRetriever()
        self.router = QuestionRouterAgent(self.llm_service)
        self.verifier = VerifierAgent(self.llm_service)

    def set_document_context(
        self,
        doc_id: str,
        paper_title: str = "",
        paper_summary: str = "",
    ) -> bool:
        try:
            success = self.vector_store.load_collection(doc_id)
            if success:
                self.current_doc_id = doc_id
                self.current_paper_title = paper_title
                self.current_paper_summary = paper_summary
                self.current_profile = self.object_indexer.load_profile(doc_id)
                self.chat_history = []
                self._cached_suggestions = None
                return True
            return False
        except Exception:
            return False

    def _build_system_prompt(self) -> str:
        return (
            "你是一位专业的学术论文研究助手。"
            f"当前论文标题：{self.current_paper_title or '未知标题'}\n"
            f"论文摘要概述：{self.current_paper_summary[:500]}"
        )

    def _build_plan(self, route_type: QuestionRoute, question: str) -> List[str]:
        if route_type == QuestionRoute.STRUCTURE:
            return ["定位章节结构", "整理章节摘要"]
        if route_type == QuestionRoute.METHOD:
            return ["检索方法章节", "定位关键主张", "生成方法解释"]
        if route_type == QuestionRoute.EVIDENCE:
            return ["定位主张", "检索证据与结果", "验证回答是否有支撑"]
        if route_type == QuestionRoute.RESULT:
            return ["检索实验结果", "聚合指标和数据集信息"]
        if route_type == QuestionRoute.CRITICAL:
            return ["定位主张", "查找证据与局限", "给出批判性结论"]
        return ["检索相关章节", "提取证据", "生成回答"]

    def _retrieve_bundle(self, question: str, route_type: QuestionRoute) -> EvidenceBundle:
        bundle = EvidenceBundle(route=route_type)
        profile = self.current_profile

        if profile:
            if route_type == QuestionRoute.STRUCTURE:
                bundle.sections = profile.sections[:6]
            elif route_type == QuestionRoute.METHOD:
                bundle.sections = [s for s in profile.sections if s.section_type.value in {"method", "introduction"}][:4]
                bundle.target_claims = [c for c in profile.claims if c.claim_type.value in {"causal", "general"}][:4]
            elif route_type == QuestionRoute.EVIDENCE:
                bundle.target_claims = profile.claims[:4]
                bundle.evidences = profile.evidences[:6]
                bundle.results = profile.results[:4]
            elif route_type == QuestionRoute.RESULT:
                bundle.results = profile.results[:6]
                bundle.sections = [s for s in profile.sections if s.section_type.value in {"experiment", "result", "ablation"}][:3]
            elif route_type == QuestionRoute.CRITICAL:
                bundle.target_claims = profile.claims[:3]
                bundle.evidences = profile.evidences[:4]
                bundle.missing_information.extend(profile.limitations[:3])
                bundle.sections = [s for s in profile.sections if s.section_type.value in {"conclusion", "limitation"}][:2]
            else:
                bundle.sections = profile.sections[:3]
                bundle.target_claims = profile.claims[:3]
                bundle.evidences = profile.evidences[:3]

        docs = self.vector_store.search(question, top_k=6)
        for doc in docs:
            meta = doc.metadata or {}
            object_type = meta.get("object_type", "chunk")
            if object_type == "claim" and profile:
                matched = next((c for c in profile.claims if c.claim_id == meta.get("claim_id")), None)
                if matched and all(c.claim_id != matched.claim_id for c in bundle.target_claims):
                    bundle.target_claims.append(matched)
            elif object_type == "evidence" and profile:
                matched = next((e for e in profile.evidences if e.evidence_id == meta.get("evidence_id")), None)
                if matched and all(e.evidence_id != matched.evidence_id for e in bundle.evidences):
                    bundle.evidences.append(matched)
            elif object_type == "result" and profile:
                matched = next((r for r in profile.results if r.result_id == meta.get("result_id")), None)
                if matched and all(r.result_id != matched.result_id for r in bundle.results):
                    bundle.results.append(matched)
            elif object_type == "section" and profile:
                matched = next((s for s in profile.sections if s.section_id == meta.get("section_id")), None)
                if matched and all(s.section_id != matched.section_id for s in bundle.sections):
                    bundle.sections.append(matched)
            bundle.source_chunks.append(doc.page_content[:500])

        if not bundle.source_chunks:
            bundle.missing_information.append("未检索到足够相关的论文片段")
        return bundle

    def _bundle_to_text(self, bundle: EvidenceBundle) -> str:
        data = {
            "route": bundle.route.value,
            "claims": [c.text for c in bundle.target_claims[:5]],
            "evidences": [e.text for e in bundle.evidences[:5]],
            "results": [r.text for r in bundle.results[:5]],
            "sections": [f"{s.title}: {s.content[:300]}" for s in bundle.sections[:4]],
            "missing_information": bundle.missing_information[:3],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _solve(self, question: str, bundle: EvidenceBundle, use_history: bool = True) -> str:
        prompt = CLAIM_EVIDENCE_ANSWER_PROMPT.format(
            question=question,
            route_type=bundle.route.value,
            evidence_bundle=self._bundle_to_text(bundle),
        )
        history = self.chat_history if use_history else None
        return self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt=self._build_system_prompt(),
            chat_history=history,
        )

    def ask(self, question: str, top_k: int = 5, use_history: bool = True) -> QAResult:
        start_time = time.time()
        if self.current_doc_id is None:
            return QAResult(success=False, error_message="请先上传并解析论文文档")

        try:
            decision = self.router.route(question)
            trace = [f"route={decision.route.value}", f"targets={','.join(decision.retrieval_targets)}"]
            trace.extend(self._build_plan(decision.route, question))
            bundle = self._retrieve_bundle(question, decision.route)
            subgraph = self.subgraph_retriever.retrieve(self.current_profile, decision.route) if self.current_profile else {"paths": [], "visited_ids": []}
            if self.current_profile:
                bundle = self.subgraph_retriever.enrich_bundle(bundle, self.current_profile, subgraph)
            answer = self._solve(question, bundle, use_history)
            verification = self.verifier.verify(question, answer, bundle, subgraph.get("paths", []))

            if use_history:
                self.chat_history.append({"role": "user", "content": question})
                self.chat_history.append({"role": "assistant", "content": answer})
                if len(self.chat_history) > 20:
                    self.chat_history = self.chat_history[-20:]

            evidence_summary = [e.text for e in bundle.evidences[:3]] or [r.text for r in bundle.results[:3]]
            if not evidence_summary:
                evidence_summary = [s.title for s in bundle.sections[:3]]
            path_strings = ["path=" + " ".join(path) for path in subgraph.get("paths", [])[:3]]
            claim_nodes = [claim.claim_id for claim in bundle.target_claims[:4]]
            evidence_nodes = [evidence.evidence_id for evidence in bundle.evidences[:4]]
            result_nodes = [result.result_id for result in bundle.results[:4]]

            return QAResult(
                success=True,
                answer=answer,
                source_chunks=bundle.source_chunks[:5],
                route_type=decision.route.value,
                evidence_summary=evidence_summary,
                warnings=verification.warnings,
                reasoning_trace=trace + path_strings,
                reasoning_paths=subgraph.get("paths", [])[:5],
                claim_nodes=claim_nodes,
                evidence_nodes=evidence_nodes,
                result_nodes=result_nodes,
                confidence=verification.confidence,
                processing_time=time.time() - start_time,
            )
        except Exception as e:
            logger.exception("Claim-Evidence QA failed")
            return QAResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time,
            )

    def ask_stream(self, question: str, top_k: int = 5):
        if self.current_doc_id is None:
            yield "请先上传并解析论文文档"
            return
        try:
            yield "正在识别问题类型...\n"
            decision = self.router.route(question)
            yield f"> 问题类型: {decision.route.value}\n"
            yield "> 正在检索关键主张与证据...\n"
            bundle = self._retrieve_bundle(question, decision.route)
            subgraph = self.subgraph_retriever.retrieve(self.current_profile, decision.route) if self.current_profile else {"paths": [], "visited_ids": []}
            if self.current_profile:
                bundle = self.subgraph_retriever.enrich_bundle(bundle, self.current_profile, subgraph)
            if subgraph.get("paths"):
                yield "> 已定位论证路径...\n"
                for path in subgraph.get("paths", [])[:2]:
                    yield f"> path: {' '.join(path)}\n"
            yield "> 正在综合证据生成回答...\n"
            answer = self._solve(question, bundle, use_history=True)
            for chunk in self._stream_text(answer):
                yield chunk
            yield "\n> 正在验证答案可靠性...\n"
            verification = self.verifier.verify(question, answer, bundle, subgraph.get("paths", []))
            if verification.warnings:
                yield "\n风险提示：\n"
                for warning in verification.warnings:
                    yield f"- {warning}\n"
            self.chat_history.append({"role": "user", "content": question})
            self.chat_history.append({"role": "assistant", "content": answer})
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]
        except Exception as e:
            yield f"问答失败: {str(e)}"

    def _stream_text(self, text: str, chunk_size: int = 80):
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    def clear_history(self):
        self.chat_history = []

    def get_suggested_questions(self) -> List[str]:
        return [
            "这篇论文的核心方法是什么？",
            "作者是如何证明方法有效的？",
            "有哪些关键实验结果支持论文结论？",
            "这篇论文的局限性是什么？",
        ]

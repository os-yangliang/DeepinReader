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
    VerificationReport,
)
from services.subgraph_retriever import SubgraphRetriever
from services.evidence_sufficiency import EvidenceSufficiencyEstimator
from services.object_indexer import ObjectIndexer
from prompts.templates import (
    CLAIM_EVIDENCE_ANSWER_PROMPT,
    RETRIEVAL_PLANNER_PROMPT,
    ANSWER_REFINEMENT_PROMPT,
)
from agents.question_router_agent import QuestionRouterAgent, RouteDecision
from agents.verifier_agent import VerifierAgent
from agents.critic_agent import CriticAgent
from agents.reviser_agent import ReviserAgent
from agents.arbiter_agent import ArbiterAgent
from services.paper_schema import CriticReport, ArbiterDecision

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
    reasoning_chains: List[Dict[str, Any]] = None
    sufficiency_score: float = 0.0
    sufficiency_label: str = "unknown"
    sufficiency_factors: List[str] = None
    consistency_score: float = 0.0
    evidence_coverage: float = 0.0
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
        if self.reasoning_chains is None:
            self.reasoning_chains = []
        if self.sufficiency_factors is None:
            self.sufficiency_factors = []


class QAAgent:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        vector_store: Optional[VectorStoreService] = None,
        ablation_config: Optional[Dict[str, bool]] = None,
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
        self.sufficiency_estimator = EvidenceSufficiencyEstimator(self.llm_service)
        self.router = QuestionRouterAgent(self.llm_service)
        self.verifier = VerifierAgent(self.llm_service)
        self.critic = CriticAgent(self.llm_service)
        self.reviser = ReviserAgent(self.llm_service)
        self.arbiter = ArbiterAgent(self.llm_service)

        # 消融实验配置：默认全部开启
        self.ablation = {
            "use_routing": True,
            "use_graph": True,
            "use_chain": True,
            "use_sufficiency": True,
            "use_verification": True,
            "use_iterative": True,
            "use_debate": True,
        }
        if ablation_config:
            self.ablation.update(ablation_config)

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
                bundle.target_claims = profile.claims[:5]
                bundle.evidences = profile.evidences[:5]
                bundle.results = profile.results[:5]
                bundle.missing_information.extend(profile.limitations[:4])
                bundle.sections = [s for s in profile.sections if s.section_type.value in {"conclusion", "limitation", "experiment", "result", "ablation"}][:4]
                if self.sufficiency_estimator.is_overgeneralized_question(question):
                    bundle.missing_information.append("问题要求全称范围证明，需要覆盖所有任务、所有数据集或所有方法的直接证据")
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
            "reasoning_chains": [
                {
                    "chain_id": chain.chain_id,
                    "nodes": chain.nodes,
                    "edge_types": chain.edge_types,
                    "chain_type": chain.chain_type,
                    "score": chain.score,
                    "text": chain.text[:600],
                }
                for chain in bundle.reasoning_chains[:5]
            ],
            "sufficiency": bundle.sufficiency.model_dump() if bundle.sufficiency else None,
            "missing_information": bundle.missing_information[:3],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _iterative_expand(self, question: str, route_type: str, bundle: EvidenceBundle, max_rounds: int = 2) -> EvidenceBundle:
        """当证据不足时，由 LLM 生成补充检索 query，迭代扩展证据包。"""
        for round_idx in range(max_rounds):
            if not bundle.sufficiency or bundle.sufficiency.label == "sufficient":
                break
            if bundle.sufficiency.should_abstain and self._is_clearly_unanswerable(bundle):
                # 对明显不可答问题不再浪费检索
                break

            try:
                evidence_summary = (
                    [e.text for e in bundle.evidences[:3]]
                    or [r.text for r in bundle.results[:3]]
                    or [s.title for s in bundle.sections[:3]]
                )
                missing_factors = bundle.sufficiency.missing_factors or bundle.missing_information
                planner_prompt = RETRIEVAL_PLANNER_PROMPT.format(
                    question=question,
                    route_type=route_type,
                    evidence_summary="\n".join(evidence_summary[:5]),
                    missing_factors="\n".join(missing_factors[:5]),
                )
                raw = self.llm_service.chat_sync(
                    user_message=planner_prompt,
                    system_prompt="你是一位严谨的检索规划专家，只输出合法 JSON。",
                    chat_history=[],
                )
                parsed = self._extract_json(raw)
                if not parsed.get("needs_more_search", False):
                    break
                queries = [q for q in parsed.get("queries", []) if q and isinstance(q, str)]
                if not queries:
                    break

                added = 0
                for query in queries[:3]:
                    docs = self.vector_store.search(query, top_k=3)
                    for doc in docs:
                        content = doc.page_content[:500]
                        if content and content not in bundle.source_chunks:
                            bundle.source_chunks.append(content)
                            added += 1
                if added == 0:
                    break
                # 重新评估充分性
                bundle.sufficiency = self.sufficiency_estimator.estimate(question, bundle)
            except Exception:
                break
        return bundle

    def _is_clearly_unanswerable(self, bundle: EvidenceBundle) -> bool:
        """启发式判断：是否已明确没有检索到任何相关内容。"""
        return not bundle.source_chunks and not bundle.target_claims and not bundle.evidences and not bundle.results

    def _extract_json(self, text: str) -> dict:
        import json
        import re
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        return {}

    def _solve(self, question: str, bundle: EvidenceBundle, use_history: bool = True) -> str:
        prompt = CLAIM_EVIDENCE_ANSWER_PROMPT.format(
            question=question,
            route_type=bundle.route.value,
            evidence_bundle=self._bundle_to_text(bundle),
        )
        history = self.chat_history if use_history else None
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt=self._build_system_prompt(),
            chat_history=history,
        )
        return self._extract_answer(raw)

    def _refine_answer(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        unsupported_points: List[str],
    ) -> str:
        """根据 verifier 发现的 unsupported claims 重写答案，移除无证据支持的内容。"""
        prompt = ANSWER_REFINEMENT_PROMPT.format(
            question=question,
            answer=answer,
            evidence_bundle=self._bundle_to_text(bundle),
            unsupported_points="\n".join(f"- {p}" for p in unsupported_points[:8]),
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严格的答案精炼专家，只输出精简后的最终回答。",
            chat_history=[],
        )
        return self._extract_answer(raw)

    def _build_abstention_answer(self, bundle: EvidenceBundle) -> str:
        """根据证据不足信息构建保守拒答。"""
        factors = []
        if bundle.sufficiency and bundle.sufficiency.missing_factors:
            factors.extend(bundle.sufficiency.missing_factors[:2])
        if bundle.missing_information:
            factors.extend(bundle.missing_information[:2])
        if not factors:
            return "根据当前证据不足以回答该问题。"
        return "根据当前证据不足以回答该问题，缺少以下关键证据：" + "；".join(dict.fromkeys(factors)) + "。"

    def _debate_refine(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        route_type: str,
    ) -> str:
        """Verifier-first + Critic-for-misalignment 的两阶段精炼。

        阶段 1：复用 v3 的 Verifier + Refinement，先消除 unsupported claims（这是 v3 最成功的部分）。
        阶段 2：用 Critic 检查 misalignment / omissions_with_evidence，由 Reviser 对齐问题焦点或补充证据中确实遗漏的内容。
        阶段 3：Arbiter 在“精炼版”与“对齐版”之间做最终选择，规则 guardrail 保证不引入新幻觉。
        """
        current_answer = answer

        # ---------- 阶段 1：Verifier-first 精炼 ----------
        try:
            verification = self.verifier.verify(question, current_answer, bundle, [])
            invalid_citations = self._validate_citations(current_answer, bundle)
            if invalid_citations:
                verification.unsupported_points.extend(
                    [f"答案引用了不存在的证据 ID: {cid}" for cid in invalid_citations]
                )
                verification.unsupported_points = list(dict.fromkeys(verification.unsupported_points))[:10]

            for _ in range(3):
                if not verification.unsupported_points:
                    break
                refined = self._refine_answer(
                    question=question,
                    answer=current_answer,
                    bundle=bundle,
                    unsupported_points=verification.unsupported_points,
                )
                verification2 = self.verifier.verify(question, refined, bundle, [])
                invalid2 = self._validate_citations(refined, bundle)
                if invalid2:
                    verification2.unsupported_points.extend(
                        [f"答案引用了不存在的证据 ID: {cid}" for cid in invalid2]
                    )
                    verification2.unsupported_points = list(dict.fromkeys(verification2.unsupported_points))[:10]

                if len(verification2.unsupported_points) < len(verification.unsupported_points):
                    current_answer = refined
                    verification = verification2
                else:
                    break
        except Exception:
            pass

        # ---------- 阶段 2：Critic 检查对齐与遗漏 ----------
        try:
            critic_report = self.critic.criticize(
                question=question,
                answer=current_answer,
                bundle=bundle,
                route_type=route_type,
            )
        except Exception:
            return current_answer

        # 若证据严重不足，直接输出保守拒答
        if critic_report.overall_verdict == "should_abstain":
            if bundle.sufficiency and bundle.sufficiency.should_abstain:
                return self._build_abstention_answer(bundle)

        # 只有 misalignment / omissions_with_evidence / citation_issues 才需要 reviser
        needs_alignment_fix = bool(
            critic_report.omissions_with_evidence
            or critic_report.misalignment
            or critic_report.citation_issues
        )
        if not needs_alignment_fix:
            return current_answer

        # 过滤 Critic 报告：unsupported_claims 已在阶段 1 处理，evidence_gaps 不能硬编
        filtered_report = CriticReport(
            unsupported_claims=[],
            omissions_with_evidence=critic_report.omissions_with_evidence,
            evidence_gaps=[],
            misalignment=critic_report.misalignment,
            citation_issues=critic_report.citation_issues,
            suggestions=critic_report.suggestions,
            overall_verdict=critic_report.overall_verdict,
            reasoning=critic_report.reasoning,
        )

        try:
            revised = self.reviser.revise(
                question=question,
                answer=current_answer,
                bundle=bundle,
                critic_report=filtered_report,
            )
        except Exception:
            return current_answer

        # ---------- 阶段 3：Guardrail + Arbiter ----------
        # 规则 guardrail：修订版若引入不存在的引用，则直接丢弃
        if self._validate_citations(revised, bundle):
            return current_answer

        # 规则 guardrail：修订版若被 verifier 发现更多 unsupported claims，则直接丢弃
        try:
            revised_verification = self.verifier.verify(question, revised, bundle, [])
            if len(revised_verification.unsupported_points) > len(verification.unsupported_points):
                return current_answer
        except Exception:
            pass

        try:
            arbiter_decision = self.arbiter.choose(
                question=question,
                answer_a=current_answer,
                answer_b=revised,
                bundle=bundle,
                critic_report=filtered_report,
            )
        except Exception:
            return current_answer

        if arbiter_decision.chosen_label == "B" and arbiter_decision.confidence >= 0.6:
            return arbiter_decision.chosen_answer
        return current_answer

    def _fix_citations(self, answer: str, bundle: EvidenceBundle) -> str:
        """简单规则：删除答案中不存在的引用 ID（保留文本）。"""
        valid_ids = self._valid_citation_ids(bundle)
        pattern = re.compile(r"\[\^([\w_\-]+)\]")

        def replace_citation(match):
            cid = match.group(1)
            if cid in valid_ids:
                return match.group(0)
            return ""

        return pattern.sub(replace_citation, answer)

    def _extract_citation_ids(self, text: str) -> List[str]:
        """提取答案中的引用 ID，如 [^claim_1] -> claim_1。"""
        import re
        return re.findall(r"\[\^([\w_\-]+)\]", text)

    def _valid_citation_ids(self, bundle: EvidenceBundle) -> set:
        """返回证据包中真实存在的引用 ID 集合。"""
        ids = set()
        for c in bundle.target_claims:
            if c.claim_id:
                ids.add(c.claim_id)
        for e in bundle.evidences:
            if e.evidence_id:
                ids.add(e.evidence_id)
        for r in bundle.results:
            if r.result_id:
                ids.add(r.result_id)
        for s in bundle.sections:
            if s.section_id:
                ids.add(s.section_id)
        for chain in bundle.reasoning_chains:
            if getattr(chain, "chain_id", None):
                ids.add(chain.chain_id)
        return ids

    def _validate_citations(self, answer: str, bundle: EvidenceBundle) -> List[str]:
        """检查答案中的引用是否真实存在，返回无效引用列表。"""
        cited = self._extract_citation_ids(answer)
        valid = self._valid_citation_ids(bundle)
        invalid = [cid for cid in cited if cid not in valid]
        return invalid

    def _extract_answer(self, raw: str) -> str:
        """从 LLM 输出中提取最终回答。

        优先提取 <answer> 与 </answer> 之间的内容；若不存在，则移除 <reasoning> 块后返回剩余文本。
        """
        import re
        match = re.search(r"<answer>\s*([\s\S]*?)\s*</answer>", raw, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # 移除 reasoning 块，保留其余内容作为答案
        cleaned = re.sub(r"<reasoning>\s*[\s\S]*?\s*</reasoning>", "", raw, flags=re.IGNORECASE).strip()
        if cleaned:
            return cleaned
        return raw.strip()

    def ask(self, question: str, top_k: int = 5, use_history: bool = True) -> QAResult:
        start_time = time.time()
        if self.current_doc_id is None:
            return QAResult(success=False, error_message="请先上传并解析论文文档")

        try:
            # 消融：问题路由
            if self.ablation["use_routing"]:
                decision = self.router.route(question)
            else:
                from services.paper_schema import QuestionRoute
                decision = RouteDecision(route=QuestionRoute.GENERAL, reason="ablation: routing disabled")
            trace = [f"route={decision.route.value}", f"targets={','.join(decision.retrieval_targets)}"]
            trace.extend(self._build_plan(decision.route, question))

            # 消融：图与 chain
            if self.ablation["use_graph"]:
                bundle = self._retrieve_bundle(question, decision.route)
                if self.ablation["use_chain"] and self.current_profile:
                    subgraph = self.subgraph_retriever.retrieve(self.current_profile, decision.route, question=question)
                    bundle = self.subgraph_retriever.enrich_bundle(bundle, self.current_profile, subgraph)
                else:
                    subgraph = {"paths": [], "visited_ids": [], "chains": []}
            else:
                # 仅使用向量检索的 chunk
                bundle = EvidenceBundle(route=decision.route)
                docs = self.vector_store.search(question, top_k=top_k)
                bundle.source_chunks = [doc.page_content[:500] for doc in docs]
                subgraph = {"paths": [], "visited_ids": [], "chains": []}

            # 消融：证据充分性估计
            if self.ablation["use_sufficiency"]:
                bundle.sufficiency = self.sufficiency_estimator.estimate(question, bundle)
            else:
                bundle.sufficiency = None

            # 消融：迭代检索
            if self.ablation["use_iterative"] and self.ablation["use_sufficiency"]:
                bundle = self._iterative_expand(question, decision.route.value, bundle)

            if bundle.sufficiency and bundle.sufficiency.should_abstain:
                bundle.missing_information.append("证据充分性低于回答阈值，应输出保守结论")

            answer = self._solve(question, bundle, use_history)

            # 消融：答案验证 + 多轮忠实性精炼
            if self.ablation["use_verification"]:
                if self.ablation["use_debate"]:
                    answer = self._debate_refine(
                        question=question,
                        answer=answer,
                        bundle=bundle,
                        route_type=decision.route.value,
                    )
                    verification = self.verifier.verify(question, answer, bundle, subgraph.get("paths", []))
                    invalid_citations = self._validate_citations(answer, bundle)
                    if invalid_citations:
                        verification.unsupported_points.extend(
                            [f"答案引用了不存在的证据 ID: {cid}" for cid in invalid_citations]
                        )
                        verification.unsupported_points = list(dict.fromkeys(verification.unsupported_points))[:10]
                else:
                    verification = self.verifier.verify(question, answer, bundle, subgraph.get("paths", []))
                    # 同时检查答案中的引用 ID 是否真实存在
                    invalid_citations = self._validate_citations(answer, bundle)
                    if invalid_citations:
                        verification.unsupported_points.extend(
                            [f"答案引用了不存在的证据 ID: {cid}" for cid in invalid_citations]
                        )
                        verification.unsupported_points = list(dict.fromkeys(verification.unsupported_points))[:10]

                    # 多轮 refine：直到无 unsupported claims 或不再改善
                    max_refine_rounds = 3
                    for _ in range(max_refine_rounds):
                        if not verification.unsupported_points:
                            break
                        try:
                            refined = self._refine_answer(
                                question=question,
                                answer=answer,
                                bundle=bundle,
                                unsupported_points=verification.unsupported_points,
                            )
                            verification2 = self.verifier.verify(question, refined, bundle, subgraph.get("paths", []))
                            invalid2 = self._validate_citations(refined, bundle)
                            if invalid2:
                                verification2.unsupported_points.extend(
                                    [f"答案引用了不存在的证据 ID: {cid}" for cid in invalid2]
                                )
                                verification2.unsupported_points = list(dict.fromkeys(verification2.unsupported_points))[:10]

                            # 当精炼后的 unsupported 更少（或相等且答案变短）时采用
                            if len(verification2.unsupported_points) < len(verification.unsupported_points):
                                answer = refined
                                verification = verification2
                            elif len(verification2.unsupported_points) == len(verification.unsupported_points):
                                # 避免循环：如果不再改善，直接跳出
                                break
                            else:
                                # 精炼后反而更差，放弃
                                break
                        except Exception:
                            break
            else:
                verification = VerificationReport(confidence=0.5)

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
            warnings = list(verification.warnings)
            if bundle.sufficiency and bundle.sufficiency.should_abstain:
                warnings.extend(bundle.sufficiency.missing_factors)
            warnings = list(dict.fromkeys(warnings))

            return QAResult(
                success=True,
                answer=answer,
                source_chunks=bundle.source_chunks[:5],
                route_type=decision.route.value,
                evidence_summary=evidence_summary,
                warnings=warnings,
                reasoning_trace=trace + path_strings,
                reasoning_paths=subgraph.get("paths", [])[:5],
                claim_nodes=claim_nodes,
                evidence_nodes=evidence_nodes,
                result_nodes=result_nodes,
                reasoning_chains=[chain.model_dump() for chain in bundle.reasoning_chains[:5]],
                sufficiency_score=bundle.sufficiency.score if bundle.sufficiency else 0.0,
                sufficiency_label=bundle.sufficiency.label if bundle.sufficiency else "unknown",
                sufficiency_factors=bundle.sufficiency.missing_factors if bundle.sufficiency else [],
                consistency_score=verification.consistency_score,
                evidence_coverage=verification.evidence_coverage,
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
            subgraph = self.subgraph_retriever.retrieve(self.current_profile, decision.route, question=question) if self.current_profile else {"paths": [], "visited_ids": [], "chains": []}
            if self.current_profile:
                bundle = self.subgraph_retriever.enrich_bundle(bundle, self.current_profile, subgraph)
            bundle.sufficiency = self.sufficiency_estimator.estimate(question, bundle)
            yield f"> 证据充分性: {bundle.sufficiency.label} ({bundle.sufficiency.score:.2f})\n"
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

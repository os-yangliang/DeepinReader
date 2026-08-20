import json
import re
from typing import Dict, List, Optional

from prompts.templates import SUFFICIENCY_ASSESSMENT_PROMPT
from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, QuestionRoute, SufficiencyReport


class EvidenceSufficiencyEstimator:
    """证据充分性估计：规则快速预筛选 + LLM 语义精细判断的混合策略。"""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service

    def estimate(self, question: str, bundle: EvidenceBundle) -> SufficiencyReport:
        # 规则层：对空证据或明显全称问题做快速 guardrail
        rule_report = self._rule_estimate(question, bundle)

        # 如果规则层已判定为 insufficient 且理由充分，直接返回
        if rule_report.should_abstain and rule_report.score < 0.25:
            return rule_report

        # LLM 层：做语义精细判断
        if self.llm_service is not None:
            try:
                llm_report = self._llm_estimate(question, bundle)
                # 融合：取 LLM 与规则的保守结果
                return self._fuse_reports(rule_report, llm_report)
            except Exception:
                # LLM 失败时回退到规则结果
                return rule_report

        return rule_report

    def is_overgeneralized_question(self, question: str) -> bool:
        return self._has_universal_claim(question)

    # ------------------------------------------------------------------
    # LLM-based 充分性评估
    # ------------------------------------------------------------------

    def _llm_estimate(self, question: str, bundle: EvidenceBundle) -> SufficiencyReport:
        evidence_text = self._bundle_to_text(bundle)
        prompt = SUFFICIENCY_ASSESSMENT_PROMPT.format(
            question=question,
            route_type=bundle.route.value,
            evidence_bundle=evidence_text,
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严谨的证据充分性评估专家，只输出合法 JSON。",
            chat_history=[],
        )
        parsed = self._extract_json(raw)

        score = float(parsed.get("score", 0.0))
        label = parsed.get("label", "insufficient")
        should_abstain = bool(parsed.get("should_abstain", False))
        missing_factors = parsed.get("missing_factors", [])
        needed_evidence = parsed.get("needed_evidence", [])
        reasoning = parsed.get("reasoning", "")

        # Guardrail：LLM 输出异常时修正
        score = max(0.0, min(1.0, score))
        if label not in {"sufficient", "partial", "insufficient"}:
            label = self._score_to_label(score)

        # 对全称问题再复核
        if self._has_universal_claim(question) and not self._universal_scope_covered(question, bundle):
            score = min(score, 0.36)
            label = "insufficient"
            should_abstain = True
            missing_factors.append("问题包含全称或过度泛化结论，当前证据不足以支持所有任务/数据集/方法范围内的断言")

        return SufficiencyReport(
            score=round(score, 4),
            label=label,
            coverage=rule_component(self._coverage(bundle)[0]),
            support=rule_component(self._support(bundle)),
            consistency=rule_component(self._consistency(bundle)),
            missing_penalty=rule_component(min(1.0, 0.18 * len(bundle.missing_information) + 0.14 * len(missing_factors))),
            route_match=rule_component(self._route_match(bundle)[0]),
            missing_factors=list(dict.fromkeys(missing_factors + bundle.missing_information))[:8],
            should_abstain=should_abstain,
        )

    # ------------------------------------------------------------------
    # 规则层（快速预筛选 + fallback）
    # ------------------------------------------------------------------

    def _rule_estimate(self, question: str, bundle: EvidenceBundle) -> SufficiencyReport:
        coverage, missing = self._coverage(bundle)
        support = self._support(bundle)
        consistency = self._consistency(bundle)
        route_match, route_missing = self._route_match(bundle)
        overgeneralized, overgeneralized_missing = self._overgeneralized_claim_risk(question, bundle)
        missing.extend(route_missing)
        missing.extend(overgeneralized_missing)
        missing_penalty = min(1.0, 0.18 * len(bundle.missing_information) + 0.14 * len(missing))
        score = 0.30 * coverage + 0.30 * support + 0.20 * consistency + 0.20 * route_match - missing_penalty
        if overgeneralized:
            score = min(score, 0.36)
        score = max(0.0, min(1.0, score))
        # Tuned thresholds based on subset50 analysis: reduce conservatism
        label = "sufficient" if score >= 0.55 else "partial" if score >= 0.30 else "insufficient"
        return SufficiencyReport(
            score=round(score, 4),
            label=label,
            coverage=round(coverage, 4),
            support=round(support, 4),
            consistency=round(consistency, 4),
            missing_penalty=round(missing_penalty, 4),
            route_match=round(route_match, 4),
            missing_factors=list(dict.fromkeys(missing + bundle.missing_information))[:8],
            should_abstain=score < 0.30 or overgeneralized,
        )

    # ------------------------------------------------------------------
    # 融合策略
    # ------------------------------------------------------------------

    def _fuse_reports(self, rule_report: SufficiencyReport, llm_report: SufficiencyReport) -> SufficiencyReport:
        """融合规则层与 LLM 层的评估结果。

        为避免过度保守，不再对 should_abstain 取“或”，而是采用较低的统一阈值。
        分数仍取较低值以保持一定保守性，但 label 优先使用 LLM 判断。
        """
        score = min(rule_report.score, llm_report.score)
        should_abstain = score < 0.30
        label = self._score_to_label(score) if should_abstain else llm_report.label
        if should_abstain and label == "sufficient":
            label = "partial"
        # missing_factors 合并去重
        missing_factors = list(dict.fromkeys(rule_report.missing_factors + llm_report.missing_factors))[:8]
        return SufficiencyReport(
            score=round(score, 4),
            label=label,
            coverage=round(min(rule_report.coverage, llm_report.coverage), 4),
            support=round(min(rule_report.support, llm_report.support), 4),
            consistency=round(min(rule_report.consistency, llm_report.consistency), 4),
            missing_penalty=round(max(rule_report.missing_penalty, llm_report.missing_penalty), 4),
            route_match=round(min(rule_report.route_match, llm_report.route_match), 4),
            missing_factors=missing_factors,
            should_abstain=should_abstain,
        )

    # ------------------------------------------------------------------
    # 原有规则评分函数
    # ------------------------------------------------------------------

    def _overgeneralized_claim_risk(self, question: str, bundle: EvidenceBundle):
        has_universal_claim = self._has_universal_claim(question)
        if not has_universal_claim:
            return False, []

        evidence_text = "\n".join(
            [item.text for item in bundle.evidences]
            + [item.text for item in bundle.results]
            + [item.text for item in bundle.target_claims]
            + bundle.source_chunks
        ).lower()
        broad_scope_markers = [
            "all tasks", "all datasets", "all existing methods", "all methods", "any task", "any dataset",
            "所有任务", "所有数据集", "所有方法", "全部任务", "全部数据集", "全部方法",
        ]
        scope_supported = any(marker in evidence_text for marker in broad_scope_markers)
        comparative_supported = any(
            marker in evidence_text
            for marker in ["outperform", "superior", "state-of-the-art", "better than", "优于", "超过", "最先进", "sota"]
        )

        if scope_supported and comparative_supported:
            return False, []

        return True, ["问题包含全称或过度泛化结论，当前证据不足以支持所有任务/所有数据集/所有方法范围内的断言"]

    def _has_universal_claim(self, question: str) -> bool:
        normalized_question = question.lower()
        universal_patterns = [
            r"所有任务", r"所有数据集", r"所有方法", r"全部任务", r"全部数据集", r"全部方法",
            r"任何任务", r"任何数据集", r"任何方法", r"任意任务", r"任意数据集", r"任意方法",
            r"总是", r"一定", r"完全", r"证明了.*都", r"优于所有",
            r"all\s+tasks", r"all\s+datasets", r"all\s+methods", r"all\s+existing\s+methods",
            r"any\s+task", r"any\s+dataset", r"always", r"never", r"guarantee", r"prove[sd]?\s+that",
            r"outperform[s]?\s+all", r"state-of-the-art\s+on\s+all",
        ]
        return any(re.search(pattern, normalized_question) for pattern in universal_patterns)

    def _universal_scope_covered(self, question: str, bundle: EvidenceBundle) -> bool:
        """判断全称问题的范围是否被证据明确覆盖（用于 LLM 结果复核）。"""
        evidence_text = "\n".join(
            [item.text for item in bundle.evidences]
            + [item.text for item in bundle.results]
            + [item.text for item in bundle.target_claims]
            + bundle.source_chunks
        ).lower()
        broad_scope_markers = [
            "all tasks", "all datasets", "all existing methods", "all methods",
            "所有任务", "所有数据集", "所有方法", "全部任务", "全部数据集", "全部方法",
        ]
        return any(marker in evidence_text for marker in broad_scope_markers)

    def _coverage(self, bundle: EvidenceBundle):
        score = 0.0
        missing = []
        if bundle.source_chunks:
            score += min(0.35, 0.08 * len(bundle.source_chunks))
        else:
            missing.append("缺少相关原文片段")
        if bundle.sections:
            score += 0.15
        else:
            missing.append("缺少章节上下文")
        if bundle.target_claims:
            score += 0.15
        if bundle.evidences:
            score += 0.2
        if bundle.results:
            score += 0.15
        return min(1.0, score), missing

    def _support(self, bundle: EvidenceBundle) -> float:
        score = 0.0
        if bundle.target_claims:
            score += 0.25
        if bundle.evidences:
            score += 0.3
        if bundle.results:
            score += 0.25
        if bundle.reasoning_chains:
            score += min(0.2, 0.05 * len(bundle.reasoning_chains))
        return min(1.0, score)

    def _consistency(self, bundle: EvidenceBundle) -> float:
        if not bundle.reasoning_chains:
            return 0.45 if (bundle.evidences or bundle.results) else 0.25
        top_scores = [chain.score for chain in bundle.reasoning_chains[:5]]
        avg_chain_score = sum(top_scores) / len(top_scores)
        completeness = sum(chain.completeness for chain in bundle.reasoning_chains[:5]) / len(top_scores)
        return min(1.0, 0.55 * avg_chain_score + 0.45 * completeness)

    def _route_match(self, bundle: EvidenceBundle):
        route = bundle.route
        missing = []
        if route == QuestionRoute.STRUCTURE:
            score = 1.0 if bundle.sections else 0.2
            if not bundle.sections:
                missing.append("结构类问题缺少章节结构")
            return score, missing
        if route == QuestionRoute.METHOD:
            score = 0.5 * bool(bundle.sections) + 0.5 * bool(bundle.target_claims)
            if not bundle.target_claims:
                missing.append("方法类问题缺少方法主张")
            return float(score), missing
        if route == QuestionRoute.EVIDENCE:
            score = 0.35 * bool(bundle.target_claims) + 0.4 * bool(bundle.evidences) + 0.25 * bool(bundle.results or bundle.reasoning_chains)
            if not bundle.evidences:
                missing.append("证据类问题缺少直接证据节点")
            return float(score), missing
        if route == QuestionRoute.RESULT:
            score = 0.55 * bool(bundle.results) + 0.25 * bool(bundle.sections) + 0.2 * bool(bundle.reasoning_chains)
            if not bundle.results:
                missing.append("结果类问题缺少实验结果节点")
            return float(score), missing
        if route == QuestionRoute.CRITICAL:
            score = 0.2 * bool(bundle.target_claims) + 0.2 * bool(bundle.evidences) + 0.2 * bool(bundle.results) + 0.2 * bool(bundle.sections) + 0.2 * bool(bundle.missing_information)
            if not bundle.missing_information and not bundle.sections:
                missing.append("批判类问题缺少局限性或讨论信息")
            if not bundle.results:
                missing.append("批判类问题缺少实验结果范围信息")
            return float(score), missing
        score = 0.25 * bool(bundle.sections) + 0.25 * bool(bundle.target_claims) + 0.25 * bool(bundle.evidences) + 0.25 * bool(bundle.source_chunks)
        return float(score), missing

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------

    def _bundle_to_text(self, bundle: EvidenceBundle) -> str:
        data = {
            "route": bundle.route.value,
            "claims": [c.text for c in bundle.target_claims[:5]],
            "evidences": [e.text for e in bundle.evidences[:5]],
            "results": [r.text for r in bundle.results[:5]],
            "sections": [f"{s.title}: {s.content[:300]}" for s in bundle.sections[:4]],
            "reasoning_chains": [
                {
                    "nodes": chain.nodes,
                    "chain_type": chain.chain_type,
                    "score": chain.score,
                    "text": chain.text[:400],
                }
                for chain in bundle.reasoning_chains[:5]
            ],
            "missing_information": bundle.missing_information[:5],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _extract_json(self, text: str) -> Dict:
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
        raise ValueError("无法从 LLM 输出中提取 JSON")

    def _score_to_label(self, score: float) -> str:
        # Tuned thresholds to reduce conservatism observed on subset50
        if score >= 0.55:
            return "sufficient"
        if score >= 0.30:
            return "partial"
        return "insufficient"


def rule_component(value: float) -> float:
    """用于 LLM 报告中的规则分量占位（保持 schema 一致）。"""
    return round(max(0.0, min(1.0, value)), 4)

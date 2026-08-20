import json
import re
from typing import Dict, List, Optional

from prompts.templates import ANSWER_VERIFICATION_PROMPT
from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, VerificationReport


class VerifierAgent:
    """答案验证 Agent：LLM 细粒度验证 + 规则 guardrail 的混合策略。"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def verify(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        reasoning_paths: Optional[List[List[str]]] = None,
    ) -> VerificationReport:
        # 规则层：快速计算基础指标
        rule_report = self._rule_verify(question, answer, bundle, reasoning_paths)

        # LLM 层：细粒度验证
        if self.llm_service is not None:
            try:
                llm_report = self._llm_verify(question, answer, bundle)
                return self._fuse_reports(rule_report, llm_report)
            except Exception:
                return rule_report

        return rule_report

    # ------------------------------------------------------------------
    # LLM-based 细粒度验证
    # ------------------------------------------------------------------

    def _llm_verify(self, question: str, answer: str, bundle: EvidenceBundle) -> VerificationReport:
        evidence_text = self._evidence_text(bundle)
        sufficiency_label = bundle.sufficiency.label if bundle.sufficiency else "unknown"
        prompt = ANSWER_VERIFICATION_PROMPT.format(
            question=question,
            answer=answer,
            evidence=evidence_text[:4500],
            sufficiency_label=sufficiency_label,
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严格的答案验证专家，只输出合法 JSON。",
            chat_history=[],
        )
        parsed = self._extract_json(raw)

        supported_points = parsed.get("supported_points", [])
        unsupported_points = parsed.get("unsupported_points", [])
        warnings = parsed.get("warnings", [])
        confidence = float(parsed.get("confidence", 0.5))
        consistency_score = float(parsed.get("consistency_score", 0.0))
        evidence_coverage = float(parsed.get("evidence_coverage", 0.0))
        atomic_claims = parsed.get("atomic_claims", [])

        # Guardrail：数值范围修正
        confidence = max(0.0, min(1.0, confidence))
        consistency_score = max(0.0, min(1.0, consistency_score))
        evidence_coverage = max(0.0, min(1.0, evidence_coverage))

        # 若证据不充分但答案未拒答，追加警告
        if bundle.sufficiency and bundle.sufficiency.should_abstain and not self._is_abstention_answer(answer):
            warnings.append("证据充分性不足，但答案未给出保守结论")

        unsupported_claims = [
            c.get("claim", "") for c in atomic_claims
            if c.get("verdict") in {"NOT_ENOUGH_INFO", "CONTRADICTED"}
        ]

        return VerificationReport(
            confidence=round(confidence, 2),
            supported_points=supported_points[:6],
            unsupported_points=unsupported_points[:6],
            warnings=list(dict.fromkeys(warnings))[:7],
            consistency_score=round(consistency_score, 4),
            unsupported_claims=unsupported_claims[:5],
            evidence_coverage=round(evidence_coverage, 4),
        )

    # ------------------------------------------------------------------
    # 规则层（fast-path + fallback）
    # ------------------------------------------------------------------

    def _rule_verify(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        reasoning_paths: Optional[List[List[str]]] = None,
    ) -> VerificationReport:
        evidence_text = self._evidence_text(bundle)
        path_count = len(reasoning_paths or [])
        claim_count = len(bundle.target_claims)
        evidence_count = len(bundle.evidences)
        result_count = len(bundle.results)
        sufficiency = bundle.sufficiency

        answer_units = self._answer_units(answer)
        abstains = self._is_abstention_answer(answer)
        if abstains and sufficiency and sufficiency.should_abstain:
            unsupported_units = []
            evidence_coverage = 1.0
        else:
            unsupported_units = self._unsupported_units(answer_units, evidence_text)
            evidence_coverage = 1.0 - (len(unsupported_units) / max(1, len(answer_units)))
        chain_quality = self._chain_quality(bundle)
        consistency_score = max(0.0, min(1.0, 0.55 * evidence_coverage + 0.30 * chain_quality + 0.15 * (sufficiency.score if sufficiency else 0.4)))

        supported = []
        unsupported = []
        warnings = []

        if evidence_text.strip():
            supported.append("已检索到可核验的论文原文证据")
        else:
            unsupported.append("未找到足够证据片段")
            warnings.append("缺少直接原文证据，回答可靠性较低")

        if claim_count:
            supported.append(f"命中 {claim_count} 个主张节点")
        else:
            unsupported.append("未识别到明确主张节点")

        if evidence_count:
            supported.append(f"命中 {evidence_count} 个证据节点")
        else:
            warnings.append("缺少直接证据节点")

        if result_count:
            supported.append(f"命中 {result_count} 个结果节点")

        if path_count:
            supported.append(f"形成 {path_count} 条可解释推理路径")
        else:
            unsupported.append("未形成显式 reasoning chain")
            warnings.append("回答缺少显式主张-证据推理链")

        if sufficiency:
            supported.append(f"证据充分性={sufficiency.label}({sufficiency.score:.2f})")
            if sufficiency.should_abstain:
                warnings.append("证据充分性低，建议拒答或仅给出保守结论")
            warnings.extend(sufficiency.missing_factors[:3])

        if unsupported_units:
            unsupported.extend(unsupported_units[:4])
            warnings.append("答案中存在未被当前证据充分覆盖的表述")

        if abstains and sufficiency and sufficiency.should_abstain:
            supported.append("回答已根据证据不足信号给出保守拒答")

        if len(answer) > 1200:
            warnings.append("回答较长，可能包含部分推断性表述")

        confidence = 0.18 + 0.42 * consistency_score
        confidence += min(len(bundle.source_chunks), 5) * 0.035
        confidence += min(claim_count, 3) * 0.035
        confidence += min(evidence_count, 3) * 0.04
        confidence += min(result_count, 2) * 0.03
        confidence += min(path_count, 3) * 0.04
        if sufficiency:
            confidence = 0.65 * confidence + 0.35 * sufficiency.score
        if unsupported_units:
            confidence -= min(0.18, 0.045 * len(unsupported_units))
        if bundle.missing_information:
            confidence -= 0.06
        confidence = max(0.12, min(confidence, 0.96))

        if not supported:
            supported = [c.text for c in bundle.target_claims[:2]] or [s.title for s in bundle.sections[:2]]

        return VerificationReport(
            confidence=round(confidence, 2),
            supported_points=supported[:6],
            unsupported_points=list(dict.fromkeys(unsupported))[:6],
            warnings=list(dict.fromkeys(warnings))[:7],
            consistency_score=round(consistency_score, 4),
            unsupported_claims=unsupported_units[:5],
            evidence_coverage=round(evidence_coverage, 4),
        )

    # ------------------------------------------------------------------
    # 融合策略
    # ------------------------------------------------------------------

    def _fuse_reports(self, rule_report: VerificationReport, llm_report: VerificationReport) -> VerificationReport:
        """保守融合：取 LLM 与规则中更严格的结果。"""
        confidence = min(rule_report.confidence, llm_report.confidence)
        consistency_score = min(rule_report.consistency_score, llm_report.consistency_score)
        evidence_coverage = min(rule_report.evidence_coverage, llm_report.evidence_coverage)
        supported_points = list(dict.fromkeys(rule_report.supported_points + llm_report.supported_points))[:6]
        unsupported_points = list(dict.fromkeys(rule_report.unsupported_points + llm_report.unsupported_points))[:6]
        warnings = list(dict.fromkeys(rule_report.warnings + llm_report.warnings))[:7]
        unsupported_claims = list(dict.fromkeys(rule_report.unsupported_claims + llm_report.unsupported_claims))[:5]

        return VerificationReport(
            confidence=round(confidence, 2),
            supported_points=supported_points,
            unsupported_points=unsupported_points,
            warnings=warnings,
            consistency_score=round(consistency_score, 4),
            unsupported_claims=unsupported_claims,
            evidence_coverage=round(evidence_coverage, 4),
        )

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------

    def _evidence_text(self, bundle: EvidenceBundle) -> str:
        parts = []
        parts.extend(bundle.source_chunks[:6])
        parts.extend(claim.text for claim in bundle.target_claims[:6])
        parts.extend(evidence.text for evidence in bundle.evidences[:6])
        parts.extend(result.text for result in bundle.results[:6])
        parts.extend(chain.text for chain in bundle.reasoning_chains[:4])
        missing = bundle.missing_information[:3]
        if missing:
            parts.append("缺失信息：" + "; ".join(missing))
        return "\n".join(parts)

    def _answer_units(self, answer: str):
        units = re.split(r"[。！？；;\n]+", answer or "")
        return [unit.strip() for unit in units if len(unit.strip()) >= 8]

    def _is_abstention_answer(self, answer: str) -> bool:
        text = (answer or "").lower()
        markers = ["证据不足", "不足以回答", "无法回答", "不能证明", "无法证明", "insufficient evidence", "not enough evidence", "cannot answer"]
        return any(marker in text for marker in markers)

    def _unsupported_units(self, units, evidence_text: str):
        unsupported = []
        evidence_terms = self._terms(evidence_text)
        for unit in units:
            terms = self._terms(unit)
            if not terms:
                continue
            overlap = len(terms & evidence_terms) / max(1, len(terms))
            has_number = bool(re.search(r"\d", unit))
            threshold = 0.18 if has_number else 0.12
            if overlap < threshold:
                unsupported.append(unit[:160])
        return unsupported

    def _terms(self, text: str):
        return {term.lower() for term in re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}", text or "") if len(term.strip()) >= 2}

    def _chain_quality(self, bundle: EvidenceBundle) -> float:
        if not bundle.reasoning_chains:
            return 0.25
        chains = bundle.reasoning_chains[:5]
        return min(1.0, sum(chain.score for chain in chains) / len(chains))

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

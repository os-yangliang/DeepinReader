"""
Reviser Agent - 多 Agent 辩论架构中的修订者
"""
import json
import re

from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, CriticReport
from prompts.templates import REVISER_PROMPT


class ReviserAgent:
    """根据 Critic 的审查报告修订候选答案，消除编造、遗漏、答非所问和引用问题。"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def revise(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        critic_report: CriticReport,
    ) -> str:
        prompt = REVISER_PROMPT.format(
            question=question,
            route_type=bundle.route.value,
            answer=answer,
            evidence_bundle=self._bundle_to_text(bundle),
            critic_report=self._report_to_text(critic_report),
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严格的答案修订专家，只输出精简后的最终回答。",
            chat_history=[],
        )
        return self._extract_answer(raw)

    def _bundle_to_text(self, bundle: EvidenceBundle) -> str:
        data = {
            "route": bundle.route.value,
            "claims": [c.text for c in bundle.target_claims[:5]],
            "evidences": [e.text for e in bundle.evidences[:5]],
            "results": [r.text for r in bundle.results[:5]],
            "sections": [f"{s.title}: {s.content[:300]}" for s in bundle.sections[:4]],
            "source_chunks": bundle.source_chunks[:6],
            "reasoning_chains": [
                {
                    "chain_id": chain.chain_id,
                    "text": chain.text[:400],
                }
                for chain in bundle.reasoning_chains[:3]
            ],
            "missing_information": bundle.missing_information[:3],
            "sufficiency": bundle.sufficiency.model_dump() if bundle.sufficiency else None,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _report_to_text(self, report: CriticReport) -> str:
        data = {
            "unsupported_claims": report.unsupported_claims,
            "omissions_with_evidence": report.omissions_with_evidence,
            "evidence_gaps": report.evidence_gaps,
            "misalignment": report.misalignment,
            "citation_issues": report.citation_issues,
            "suggestions": report.suggestions,
            "overall_verdict": report.overall_verdict,
            "reasoning": report.reasoning,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _extract_answer(self, raw: str) -> str:
        match = re.search(r"<answer>\s*([\s\S]*?)\s*</answer>", raw, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        cleaned = re.sub(r"<reasoning>\s*[\s\S]*?\s*</reasoning>", "", raw, flags=re.IGNORECASE).strip()
        if cleaned:
            return cleaned
        return raw.strip()

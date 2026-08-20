"""
Critic Agent - 多 Agent 辩论架构中的质疑者
"""
import json
import re
from typing import List

from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, CriticReport
from prompts.templates import CRITIC_PROMPT


class CriticAgent:
    """独立审查候选答案，从编造、遗漏、答非所问、引用问题四个维度挑错。"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def criticize(
        self,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
        route_type: str,
    ) -> CriticReport:
        prompt = CRITIC_PROMPT.format(
            question=question,
            route_type=route_type,
            answer=answer,
            evidence_bundle=self._bundle_to_text(bundle),
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严苛的答案审查专家，只输出合法 JSON。",
            chat_history=[],
        )
        parsed = self._extract_json(raw)

        return CriticReport(
            unsupported_claims=parsed.get("unsupported_claims", []),
            omissions_with_evidence=parsed.get("omissions_with_evidence", parsed.get("missing_aspects", [])),
            evidence_gaps=parsed.get("evidence_gaps", []),
            misalignment=parsed.get("misalignment", []),
            citation_issues=parsed.get("citation_issues", []),
            suggestions=parsed.get("suggestions", []),
            overall_verdict=parsed.get("overall_verdict", "acceptable"),
            reasoning=parsed.get("reasoning", ""),
        )

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

    def _extract_json(self, text: str) -> dict:
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
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

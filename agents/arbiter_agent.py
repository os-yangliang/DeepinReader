"""
Arbiter Agent - 多 Agent 辩论架构中的仲裁者
"""
import json
import re

from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, CriticReport, ArbiterDecision
from prompts.templates import ARBITER_PROMPT


class ArbiterAgent:
    """比较原始答案与修订答案，选择更忠实、完整、切题的版本。"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def choose(
        self,
        question: str,
        answer_a: str,
        answer_b: str,
        bundle: EvidenceBundle,
        critic_report: CriticReport,
    ) -> ArbiterDecision:
        prompt = ARBITER_PROMPT.format(
            question=question,
            route_type=bundle.route.value,
            evidence_bundle=self._bundle_to_text(bundle),
            critic_report=self._report_to_text(critic_report),
            answer_a=answer_a,
            answer_b=answer_b,
        )
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位中立的答案仲裁专家，只输出合法 JSON。",
            chat_history=[],
        )
        parsed = self._extract_json(raw)

        chosen_label = parsed.get("chosen_label", "A")
        if chosen_label not in {"A", "B"}:
            chosen_label = "A"

        chosen_answer = answer_a if chosen_label == "A" else answer_b
        # 允许 arbiter 返回一个更保守的拒答
        if "chosen_answer" in parsed and parsed["chosen_answer"]:
            chosen_answer = parsed["chosen_answer"]

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ArbiterDecision(
            chosen_answer=chosen_answer,
            chosen_label=chosen_label,
            reasoning=parsed.get("reasoning", ""),
            confidence=confidence,
        )

    def _bundle_to_text(self, bundle: EvidenceBundle) -> str:
        data = {
            "route": bundle.route.value,
            "claims": [c.text for c in bundle.target_claims[:5]],
            "evidences": [e.text for e in bundle.evidences[:5]],
            "results": [r.text for r in bundle.results[:5]],
            "sections": [f"{s.title}: {s.content[:300]}" for s in bundle.sections[:4]],
            "source_chunks": bundle.source_chunks[:6],
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

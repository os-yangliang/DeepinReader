import json
import logging
from typing import List

from services.llm_service import LLMService
from services.paper_schema import (
    Claim,
    ClaimType,
    Evidence,
    Experiment,
    PaperSection,
    ProvenanceSpan,
    ResultItem,
)
from prompts.templates import SCHOLARLY_OBJECT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class ScholarlyObjectExtractor:
    MAX_ITEMS_PER_SECTION = 4

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def extract(self, sections: List[PaperSection]):
        claims: List[Claim] = []
        evidences: List[Evidence] = []
        experiments: List[Experiment] = []
        results: List[ResultItem] = []
        contributions: List[str] = []
        limitations: List[str] = []

        for section in sections:
            if len(section.content.strip()) < 80:
                continue
            try:
                payload = self._extract_section(section)
            except Exception as e:
                logger.warning("结构化对象抽取失败: %s", e)
                continue

            provenance = self._build_provenance(section)

            for i, text in enumerate(self._limit_items(payload.get("claims", [])), start=1):
                claims.append(Claim(
                    claim_id=f"{section.section_id}_claim_{i}",
                    text=text,
                    claim_type=self._infer_claim_type(section.section_type.value),
                    section_id=section.section_id,
                    provenance=provenance,
                ))
            for i, text in enumerate(self._limit_items(payload.get("evidences", [])), start=1):
                evidences.append(Evidence(
                    evidence_id=f"{section.section_id}_evidence_{i}",
                    text=text,
                    section_id=section.section_id,
                    provenance=provenance,
                ))
            for i, item in enumerate(payload.get("experiments", []), start=1):
                experiments.append(Experiment(
                    experiment_id=f"{section.section_id}_exp_{i}",
                    name=item.get("name", ""),
                    dataset=item.get("dataset", ""),
                    metrics=item.get("metrics", []),
                    section_id=section.section_id,
                    provenance=provenance,
                ))
            for i, item in enumerate(self._limit_items(payload.get("results", [])), start=1):
                results.append(ResultItem(
                    result_id=f"{section.section_id}_result_{i}",
                    text=item.get("text", ""),
                    dataset=item.get("dataset", ""),
                    metric=item.get("metric", ""),
                    value=item.get("value", ""),
                    section_id=section.section_id,
                    provenance=provenance,
                ))
            contributions.extend(payload.get("contributions", []))
            limitations.extend(payload.get("limitations", []))

        return {
            "claims": claims,
            "evidences": evidences,
            "experiments": experiments,
            "results": results,
            "contributions": contributions,
            "limitations": limitations,
        }

    def _extract_section(self, section: PaperSection) -> dict:
        preview = section.content[:5000]
        raw = self.llm_service.generate_with_prompt(
            SCHOLARLY_OBJECT_EXTRACTION_PROMPT,
            {
                "section_title": section.title,
                "section_type": section.section_type.value,
                "section_content": preview,
            },
        )
        return self._parse_payload(raw)

    def _parse_payload(self, raw: str) -> dict:
        text = (raw or "").strip()
        if not text:
            raise ValueError("empty response")

        fenced = text
        if fenced.startswith("```"):
            lines = fenced.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            fenced = "\n".join(lines).strip()
            if fenced.lower().startswith("json"):
                fenced = fenced[4:].lstrip()

        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            start = fenced.find("{")
            end = fenced.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(fenced[start:end + 1])
            raise

    def _infer_claim_type(self, section_type: str) -> ClaimType:
        if section_type == "conclusion":
            return ClaimType.CONTRIBUTION
        if section_type in {"result", "experiment", "ablation"}:
            return ClaimType.PERFORMANCE
        if section_type == "limitation":
            return ClaimType.LIMITATION
        if section_type == "method":
            return ClaimType.CAUSAL
        return ClaimType.GENERAL

    def _build_provenance(self, section: PaperSection) -> ProvenanceSpan:
        return ProvenanceSpan(
            section_id=section.section_id,
            start_line=section.start_line,
            end_line=section.end_line,
            snippet=section.content[:280],
        )

    def _limit_items(self, items):
        return [item for item in items if item][:self.MAX_ITEMS_PER_SECTION]

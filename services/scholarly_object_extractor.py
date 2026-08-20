import json
import logging
import re
from typing import Any, Dict, List

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
    """学术论文对象抽取器：LLM 结构化抽取 + 规则后处理增强。"""

    MAX_ITEMS_PER_SECTION = 6  # 从 4 放宽到 6，避免截断关键对象

    # 信号词，用于规则后处理增强 evidence strength 与 claim 类型
    CLAIM_SIGNALS = {
        "contribution": ["propose", "introduce", "present", "contribution", "贡献", "提出"],
        "performance": ["achieve", "outperform", "surpass", "obtain", "达到", "取得", "优于"],
        "comparison": ["compared with", "versus", "against", "better than", "superior to", "优于", "超过"],
        "causal": ["because", "due to", "since", "as a result", "因此", "由于", "导致"],
        "limitation": ["limitation", "shortcoming", " drawback", "不足", "局限", "缺点"],
    }

    STRONG_EVIDENCE_SIGNALS = [
        r"\d+(\.\d+)?\s*%", r"accuracy|f1|bleu|rouge|auc|map|ndcg|mrr",
        r"p\s*<\s*0\.05", r"significant", r"state-of-the-art", r"sota",
        r"outperform", r"improve",
    ]

    FIGURE_TABLE_PATTERN = re.compile(r"(Fig\.?\s*\d+|Figure\s*\d+|Table\s*\d+|表\s*\d+|图\s*\d+)", re.IGNORECASE)

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

            claim_items = self._normalize_claims(payload.get("claims", []))
            for i, item in enumerate(self._limit_items(claim_items), start=1):
                claims.append(Claim(
                    claim_id=f"{section.section_id}_claim_{i}",
                    text=item["text"],
                    claim_type=self._refine_claim_type(item.get("claim_type", ""), item["text"], section.section_type.value),
                    section_id=section.section_id,
                    provenance=provenance,
                ))

            evidence_items = self._normalize_evidences(payload.get("evidences", []))
            for i, item in enumerate(self._limit_items(evidence_items), start=1):
                strength = self._refine_evidence_strength(item.get("strength", ""), item["text"])
                related_ft = item.get("related_figure_table", "") or self._extract_figure_table(item["text"])
                evidences.append(Evidence(
                    evidence_id=f"{section.section_id}_evidence_{i}",
                    text=item["text"],
                    section_id=section.section_id,
                    strength=strength,
                    provenance=provenance,
                ))
                # 将 figure/table 信息附加到 evidence 文本中，便于后续检索
                if related_ft and related_ft not in item["text"]:
                    evidences[-1].text = f"[{related_ft}] {item['text']}"

            for i, item in enumerate(payload.get("experiments", []), start=1):
                experiments.append(Experiment(
                    experiment_id=f"{section.section_id}_exp_{i}",
                    name=item.get("name", ""),
                    dataset=item.get("dataset", ""),
                    metrics=item.get("metrics", []),
                    section_id=section.section_id,
                    provenance=provenance,
                ))

            result_items = self._normalize_results(payload.get("results", []))
            for i, item in enumerate(self._limit_items(result_items), start=1):
                results.append(ResultItem(
                    result_id=f"{section.section_id}_result_{i}",
                    text=item.get("text", ""),
                    dataset=item.get("dataset", ""),
                    metric=item.get("metric", ""),
                    value=item.get("value", ""),
                    section_id=section.section_id,
                    provenance=provenance,
                ))

            contributions.extend([c for c in payload.get("contributions", []) if isinstance(c, str)])
            limitations.extend([l for l in payload.get("limitations", []) if isinstance(l, str)])

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

    # ------------------------------------------------------------------
    # 格式兼容与规则后处理
    # ------------------------------------------------------------------

    def _normalize_claims(self, items: List[Any]) -> List[Dict[str, str]]:
        normalized = []
        for item in items:
            if isinstance(item, str):
                normalized.append({"text": item, "claim_type": ""})
            elif isinstance(item, dict):
                normalized.append({"text": item.get("text", ""), "claim_type": item.get("claim_type", "")})
        return [n for n in normalized if n["text"]]

    def _normalize_evidences(self, items: List[Any]) -> List[Dict[str, str]]:
        normalized = []
        for item in items:
            if isinstance(item, str):
                normalized.append({"text": item, "strength": "", "related_figure_table": ""})
            elif isinstance(item, dict):
                normalized.append({
                    "text": item.get("text", ""),
                    "strength": item.get("strength", ""),
                    "related_figure_table": item.get("related_figure_table", ""),
                })
        return [n for n in normalized if n["text"]]

    def _normalize_results(self, items: List[Any]) -> List[Dict[str, str]]:
        normalized = []
        for item in items:
            if isinstance(item, str):
                normalized.append({"text": item, "dataset": "", "metric": "", "value": ""})
            elif isinstance(item, dict):
                normalized.append({
                    "text": item.get("text", ""),
                    "dataset": item.get("dataset", ""),
                    "metric": item.get("metric", ""),
                    "value": item.get("value", ""),
                })
        return [n for n in normalized if n["text"]]

    def _refine_claim_type(self, llm_type: str, text: str, section_type: str) -> ClaimType:
        """结合 LLM 输出、文本信号词和章节类型推断 claim 类型。"""
        text_lower = text.lower()
        type_scores = {}
        for ctype, signals in self.CLAIM_SIGNALS.items():
            type_scores[ctype] = sum(1 for s in signals if s.lower() in text_lower)

        # LLM 输出优先
        llm_type_lower = (llm_type or "").lower()
        if llm_type_lower in type_scores:
            type_scores[llm_type_lower] += 2

        # 章节类型调整
        if section_type == "conclusion":
            type_scores["contribution"] += 1
        elif section_type in {"result", "experiment", "ablation"}:
            type_scores["performance"] += 1
        elif section_type == "limitation":
            type_scores["limitation"] += 2
        elif section_type == "method":
            type_scores["causal"] += 0.5

        if type_scores:
            best = max(type_scores, key=type_scores.get)
            if type_scores[best] > 0:
                mapping = {
                    "contribution": ClaimType.CONTRIBUTION,
                    "performance": ClaimType.PERFORMANCE,
                    "comparison": ClaimType.COMPARISON,
                    "causal": ClaimType.CAUSAL,
                    "limitation": ClaimType.LIMITATION,
                }
                return mapping.get(best, ClaimType.GENERAL)

        return self._infer_claim_type(section_type)

    def _refine_evidence_strength(self, llm_strength: str, text: str) -> str:
        """结合 LLM 输出和文本信号词判断证据强度。"""
        if llm_strength in {"strong", "medium", "weak"}:
            base = llm_strength
        else:
            base = "medium"

        text_lower = text.lower()
        strong_hits = sum(1 for p in self.STRONG_EVIDENCE_SIGNALS if re.search(p, text_lower))
        if strong_hits >= 2:
            return "strong"
        if strong_hits == 1:
            return base if base != "weak" else "medium"
        if "for example" in text_lower or "such as" in text_lower or "e.g." in text_lower:
            return "weak"
        return base

    def _extract_figure_table(self, text: str) -> str:
        match = self.FIGURE_TABLE_PATTERN.search(text)
        return match.group(0) if match else ""

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

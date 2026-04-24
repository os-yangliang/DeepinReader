from services.llm_service import LLMService
from services.paper_schema import EvidenceBundle, VerificationReport
from prompts.templates import ANSWER_VERIFICATION_PROMPT


class VerifierAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def verify(self, question: str, answer: str, bundle: EvidenceBundle, reasoning_paths=None) -> VerificationReport:
        evidence_text = "\n".join(bundle.source_chunks[:6])
        path_count = len(reasoning_paths or [])
        claim_count = len(bundle.target_claims)
        evidence_count = len(bundle.evidences)
        result_count = len(bundle.results)

        if not evidence_text.strip() and path_count == 0:
            return VerificationReport(
                confidence=0.28,
                unsupported_points=["未找到足够证据片段", "未形成可验证的论证路径"],
                warnings=["当前回答证据不足，建议进一步查看原文"],
            )

        unsupported = []
        warnings = []
        supported = []

        confidence = 0.32
        if evidence_text.strip():
            confidence += min(len(bundle.source_chunks), 4) * 0.08
            supported.append("已检索到相关原文片段")
        else:
            warnings.append("缺少直接原文片段，回答更依赖结构化图谱")

        if claim_count:
            confidence += min(claim_count, 3) * 0.05
            supported.append(f"命中 {claim_count} 个主张节点")
        else:
            unsupported.append("未识别到明确主张节点")

        if evidence_count:
            confidence += min(evidence_count, 3) * 0.05
            supported.append(f"命中 {evidence_count} 个证据节点")
        else:
            warnings.append("缺少直接证据节点")

        if result_count:
            confidence += min(result_count, 2) * 0.04
            supported.append(f"命中 {result_count} 个结果节点")

        if path_count:
            confidence += min(path_count, 3) * 0.07
            supported.append(f"形成 {path_count} 条推理路径")
            longest_path = max(len(path) for path in reasoning_paths)
            if longest_path >= 5:
                confidence += 0.05
                supported.append("存在多跳论证链路")
        else:
            unsupported.append("未形成 claim-evidence-result 推理路径")
            warnings.append("回答缺少显式支撑链路")

        if bundle.missing_information:
            warnings.extend(bundle.missing_information[:2])
            confidence -= 0.08

        if len(answer) > 1200:
            warnings.append("回答较长，可能包含部分推断性表述")
            confidence -= 0.05

        if claim_count and not evidence_count and not result_count:
            warnings.append("命中了主张，但缺少证据或结果支撑")
            confidence -= 0.08

        if path_count and evidence_count == 0:
            warnings.append("已形成路径，但路径中的证据节点较弱")
            confidence -= 0.04

        confidence = max(0.18, min(confidence, 0.96))

        if not supported:
            supported = [c.text for c in bundle.target_claims[:2]] or [s.title for s in bundle.sections[:2]]

        return VerificationReport(
            confidence=round(confidence, 2),
            supported_points=supported[:5],
            unsupported_points=unsupported[:4],
            warnings=list(dict.fromkeys(warnings))[:5],
        )

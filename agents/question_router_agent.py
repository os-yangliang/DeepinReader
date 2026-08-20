import json
import re
from dataclasses import dataclass, field
from typing import List

from prompts.templates import QUESTION_ROUTING_PROMPT
from services.llm_service import LLMService
from services.paper_schema import QuestionRoute


@dataclass
class RouteDecision:
    route: QuestionRoute
    reason: str = ""
    retrieval_targets: List[str] = field(default_factory=list)
    expected_evidence_types: List[str] = field(default_factory=list)
    complexity: str = "single-hop"
    is_overgeneralized: bool = False

    def __post_init__(self):
        if self.retrieval_targets is None:
            self.retrieval_targets = []
        if self.expected_evidence_types is None:
            self.expected_evidence_types = []


class QuestionRouterAgent:
    """问题路由 Agent：优先使用 LLM 做结构化路由决策，规则作为 guardrail 与 fallback。"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def route(self, question: str) -> RouteDecision:
        # Guardrail 1：检测到全称/过度泛化问题时，直接判为 critical
        if self._is_overgeneralized_question(question):
            return RouteDecision(
                route=QuestionRoute.CRITICAL,
                reason="检测到全称或过度泛化断言，需要批判性分析",
                retrieval_targets=["claim", "evidence", "result", "limitation"],
                expected_evidence_types=["comparison_claim", "quantitative_result", "limitation_statement"],
                complexity="multi-hop",
                is_overgeneralized=True,
            )

        # 优先使用 LLM 路由
        try:
            return self._llm_route(question)
        except Exception:
            # Fallback 到规则路由
            return self._rule_route(question)

    def _llm_route(self, question: str) -> RouteDecision:
        prompt = QUESTION_ROUTING_PROMPT.format(question=question)
        raw = self.llm_service.chat_sync(
            user_message=prompt,
            system_prompt="你是一位严谨的学术论文问答路由专家，只输出合法 JSON。",
            chat_history=[],
        )
        parsed = self._extract_json(raw)

        route_str = parsed.get("route", "general").lower().strip()
        route = self._normalize_route(route_str)

        # Guardrail 2：LLM 返回的 route 不在合法集合中时 fallback
        if route is None:
            return self._rule_route(question)

        # Guardrail 3：即使 LLM 没检测出过度泛化，我们再用规则复核一次
        is_overgeneralized = parsed.get("is_overgeneralized", False) or self._is_overgeneralized_question(question)
        if is_overgeneralized and route != QuestionRoute.CRITICAL:
            route = QuestionRoute.CRITICAL

        return RouteDecision(
            route=route,
            reason=parsed.get("reasoning", ""),
            retrieval_targets=parsed.get("retrieval_targets", self._default_targets(route)),
            expected_evidence_types=parsed.get("expected_evidence_types", []),
            complexity=parsed.get("complexity", "single-hop"),
            is_overgeneralized=is_overgeneralized,
        )

    def _rule_route(self, question: str) -> RouteDecision:
        """关键词规则路由，作为 LLM 失败时的 fallback。"""
        q = question.lower()
        if any(k in q for k in ["结构", "章节", "section", "outline"]):
            return RouteDecision(
                route=QuestionRoute.STRUCTURE,
                reason="关键词命中结构/章节",
                retrieval_targets=["section"],
                expected_evidence_types=[],
            )
        if any(k in q for k in ["为什么", "依据", "证明", "evidence", "support"]):
            return RouteDecision(
                route=QuestionRoute.EVIDENCE,
                reason="关键词命中证据/证明",
                retrieval_targets=["claim", "evidence", "result"],
                expected_evidence_types=["causal_claim", "quantitative_result"],
            )
        if any(k in q for k in ["结果", "指标", "数据集", "实验", "metric", "dataset"]):
            return RouteDecision(
                route=QuestionRoute.RESULT,
                reason="关键词命中结果/实验",
                retrieval_targets=["result", "experiment", "section"],
                expected_evidence_types=["quantitative_result", "ablation_result"],
            )
        if any(k in q for k in ["局限", "靠谱吗", "缺点", "limitations", "weakness"]):
            return RouteDecision(
                route=QuestionRoute.CRITICAL,
                reason="关键词命中局限/批判",
                retrieval_targets=["claim", "evidence", "section", "limitation"],
                expected_evidence_types=["limitation_statement"],
            )
        if any(k in q for k in ["方法", "模块", "模型", "how", "approach"]):
            return RouteDecision(
                route=QuestionRoute.METHOD,
                reason="关键词命中方法",
                retrieval_targets=["section", "claim"],
                expected_evidence_types=["causal_claim"],
            )
        return RouteDecision(
            route=QuestionRoute.GENERAL,
            reason="未命中特定关键词，按通用问题处理",
            retrieval_targets=["section", "claim", "evidence"],
            expected_evidence_types=["causal_claim", "quantitative_result"],
        )

    def _is_overgeneralized_question(self, question: str) -> bool:
        normalized_question = question.lower()
        universal_patterns = [
            r"所有任务", r"所有数据集", r"所有方法", r"全部任务", r"全部数据集", r"全部方法",
            r"任何任务", r"任何数据集", r"任何方法", r"任意任务", r"任意数据集", r"任意方法",
            r"总是", r"一定", r"完全", r"证明了.*都", r"优于已有方法", r"优于所有",
            r"all\s+tasks", r"all\s+datasets", r"all\s+methods", r"all\s+existing\s+methods",
            r"any\s+task", r"any\s+dataset", r"always", r"never", r"guarantee", r"prove[sd]?\s+that",
            r"outperform[s]?\s+all", r"state-of-the-art\s+on\s+all",
        ]
        return any(re.search(pattern, normalized_question) for pattern in universal_patterns)

    def _normalize_route(self, route_str: str) -> QuestionRoute | None:
        mapping = {
            "structure": QuestionRoute.STRUCTURE,
            "method": QuestionRoute.METHOD,
            "evidence": QuestionRoute.EVIDENCE,
            "result": QuestionRoute.RESULT,
            "critical": QuestionRoute.CRITICAL,
            "general": QuestionRoute.GENERAL,
        }
        return mapping.get(route_str)

    def _default_targets(self, route: QuestionRoute) -> List[str]:
        targets_map = {
            QuestionRoute.STRUCTURE: ["section"],
            QuestionRoute.METHOD: ["section", "claim"],
            QuestionRoute.EVIDENCE: ["claim", "evidence", "result"],
            QuestionRoute.RESULT: ["result", "experiment", "section"],
            QuestionRoute.CRITICAL: ["claim", "evidence", "result", "limitation"],
            QuestionRoute.GENERAL: ["section", "claim", "evidence"],
        }
        return targets_map.get(route, ["section", "claim", "evidence"])

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试从 ```json ... ``` 中提取
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取第一个 { ... }
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("无法从 LLM 输出中提取 JSON")

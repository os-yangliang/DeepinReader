from dataclasses import dataclass
from typing import List

from prompts.templates import QUESTION_ROUTING_PROMPT
from services.llm_service import LLMService
from services.paper_schema import QuestionRoute


@dataclass
class RouteDecision:
    route: QuestionRoute
    reason: str = ""
    retrieval_targets: List[str] = None

    def __post_init__(self):
        if self.retrieval_targets is None:
            self.retrieval_targets = []


class QuestionRouterAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def route(self, question: str) -> RouteDecision:
        q = question.lower()
        if any(k in q for k in ["结构", "章节", "section", "outline"]):
            return RouteDecision(route=QuestionRoute.STRUCTURE, reason="关注论文结构", retrieval_targets=["section"])
        if any(k in q for k in ["为什么", "依据", "证明", "evidence", "support"]):
            return RouteDecision(route=QuestionRoute.EVIDENCE, reason="需要主张与证据", retrieval_targets=["claim", "evidence", "result"])
        if any(k in q for k in ["结果", "指标", "数据集", "实验", "metric", "dataset"]):
            return RouteDecision(route=QuestionRoute.RESULT, reason="关注实验结果", retrieval_targets=["result", "section"])
        if any(k in q for k in ["局限", "靠谱吗", "缺点", "limitations", "weakness"]):
            return RouteDecision(route=QuestionRoute.CRITICAL, reason="需要批判性分析", retrieval_targets=["claim", "evidence", "section"])
        if any(k in q for k in ["方法", "模块", "模型", "how", "approach"]):
            return RouteDecision(route=QuestionRoute.METHOD, reason="关注方法设计", retrieval_targets=["section", "claim"])
        return RouteDecision(route=QuestionRoute.GENERAL, reason="通用问题", retrieval_targets=["section", "claim", "evidence"])

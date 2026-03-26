"""
课题组 Agent 工具集 — 11 个工具，按角色分组
"""
import logging
from typing import List

from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from services.tools import ToolService
from prompts.lab_templates import (
    METHOD_COMPARE_PROMPT,
    EXPERIMENT_DESIGN_PROMPT,
    ANALOGY_PROMPT,
    CHALLENGE_PROMPT,
    LITERATURE_SURVEY_PROMPT,
    SUMMARIZE_DISCUSSION_PROMPT,
    IDEA_EVALUATE_PROMPT,
    DIRECTION_DECIDE_PROMPT,
)

logger = logging.getLogger(__name__)


class LabTools:
    """课题组 Agent 工具集"""

    def __init__(self, llm_service: LLMService, vector_store: VectorStoreService):
        self.llm = llm_service
        self.vs = vector_store
        self.web = ToolService()

    # ==================== 博三工具 ====================

    def deep_paper_search(self, queries: List[str], top_k: int = 3) -> str:
        """
        论文深度检索：多轮检索不同主题，去重合并。
        用于深入理解论文的方法、实验和局限性。
        """
        all_results = []
        seen = set()
        for query in queries:
            try:
                docs = self.vs.search(query, top_k=top_k)
                for doc in docs:
                    key = doc.page_content[:100]
                    if key not in seen:
                        seen.add(key)
                        all_results.append(doc.page_content)
            except Exception as e:
                logger.warning(f"论文检索失败 [{query}]: {e}")
        if not all_results:
            return "（未检索到相关论文内容）"
        return "\n\n---\n\n".join(all_results[:10])

    def method_comparator(self, paper_method: str, baselines: str) -> str:
        """
        方法对比器：结构化对比论文方法与 baseline。
        """
        context = self.deep_paper_search([
            paper_method, baselines, "comparison experiment result baseline"
        ])
        prompt = METHOD_COMPARE_PROMPT.format(
            method=paper_method, baselines=baselines, context=context
        )
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"方法对比失败: {e}")
            return f"（方法对比工具出错：{e}）"

    def experiment_designer(self, idea: str, paper_experiment_info: str) -> str:
        """
        实验方案设计器：基于 Idea 和论文已有实验框架设计实验。
        """
        prompt = EXPERIMENT_DESIGN_PROMPT.format(
            idea=idea, existing_experiments=paper_experiment_info
        )
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"实验设计失败: {e}")
            return f"（实验设计工具出错：{e}）"

    # ==================== 博一工具 ====================

    def cross_domain_search(self, method_keywords: str, target_domain: str = "") -> str:
        """
        跨领域网络搜索：查找方法在其他领域的应用。
        """
        if target_domain:
            query = f"{method_keywords} applied in {target_domain} research"
        else:
            query = f"{method_keywords} novel application different domain"
        try:
            return self.web.web_search(query, max_results=5)
        except Exception as e:
            logger.error(f"跨领域搜索失败: {e}")
            return f"（跨领域搜索出错：{e}）"

    def analogy_finder(self, core_method: str) -> str:
        """
        类比查找器：找其他领域的相似方法。
        """
        try:
            web_results = self.web.web_search(
                f"{core_method} similar approach different field application",
                max_results=3,
            )
            prompt = ANALOGY_PROMPT.format(method=core_method, web_results=web_results)
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"类比查找失败: {e}")
            return f"（类比查找工具出错：{e}）"

    def innovation_challenger(self, idea: str) -> str:
        """
        创新性挑战器：扮演魔鬼代言人，质疑和改进 Idea。
        """
        prompt = CHALLENGE_PROMPT.format(idea=idea)
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"创新性挑战失败: {e}")
            return f"（挑战分析出错：{e}）"

    # ==================== 硕士工具 ====================

    def literature_survey(self, keywords: List[str]) -> str:
        """
        文献调研：搜索并整理相关文献。
        """
        all_web = []
        for kw in keywords[:3]:
            try:
                result = self.web.web_search(
                    f"{kw} survey paper research 2024", max_results=3
                )
                all_web.append(result)
            except Exception as e:
                logger.warning(f"文献搜索失败 [{kw}]: {e}")
        if not all_web:
            return "（文献检索暂不可用）"
        combined = "\n\n".join(all_web)
        prompt = LITERATURE_SURVEY_PROMPT.format(
            keywords=", ".join(keywords), results=combined
        )
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"文献调研整理失败: {e}")
            return combined[:500]

    def citation_finder(self, technique: str) -> str:
        """
        引文查找：查找关键技术的代表性论文。
        """
        try:
            return self.web.web_search(
                f'"{technique}" paper citation survey', max_results=5
            )
        except Exception as e:
            logger.error(f"引文查找失败: {e}")
            return f"（引文查找出错：{e}）"

    def discussion_summarizer(self, discussion_text: str) -> str:
        """
        讨论纪要整理：将发散讨论提炼为清晰条目。
        """
        prompt = SUMMARIZE_DISCUSSION_PROMPT.format(discussion=discussion_text)
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"讨论整理失败: {e}")
            return "（讨论纪要整理出错）"

    # ==================== 导师工具 ====================

    def idea_evaluator(self, ideas: List[str], paper_context: str) -> str:
        """
        Idea 评估器：多维度打分。
        """
        ideas_text = "\n".join(
            [f"Idea {i + 1}: {idea}" for i, idea in enumerate(ideas)]
        )
        prompt = IDEA_EVALUATE_PROMPT.format(ideas=ideas_text, context=paper_context)
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"Idea 评估失败: {e}")
            return f"（Idea 评估出错：{e}）"

    def direction_decider(self, evaluation: str, paper_summary: str) -> str:
        """
        方向决策器：选择最终方向。
        """
        prompt = DIRECTION_DECIDE_PROMPT.format(
            evaluation=evaluation, summary=paper_summary
        )
        try:
            return self.llm.chat_sync(prompt)
        except Exception as e:
            logger.error(f"方向决策失败: {e}")
            return f"（方向决策出错：{e}）"

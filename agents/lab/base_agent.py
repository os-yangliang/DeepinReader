"""
课题组 Agent 基类 — 含工具集成和记忆管理
"""
import logging
from typing import Dict, List, Optional

from services.llm_service import LLMService
from agents.lab.personas import AgentPersona
from agents.lab.memory import AgentMemory, LabContext
from agents.lab.tools import LabTools
from prompts.lab_templates import (
    LAB_SYSTEM_PROMPT,
    PAPER_REVIEW_PROMPT,
    BRAINSTORM_PROMPT,
    ADVISOR_REVIEW_PROMPT,
    DEEP_DIVE_PROMPT,
    FINAL_PLAN_PROMPT,
)

logger = logging.getLogger(__name__)

# 阶段 Prompt 映射
PHASE_PROMPT_MAP = {
    "paper_review": PAPER_REVIEW_PROMPT,
    "brainstorm": BRAINSTORM_PROMPT,
    "advisor_review": ADVISOR_REVIEW_PROMPT,
    "deep_dive": DEEP_DIVE_PROMPT,
    "final_plan": FINAL_PLAN_PROMPT,
}


class LabAgent:
    """课题组成员基类"""

    def __init__(
        self,
        persona: AgentPersona,
        llm_service: LLMService,
        tools: LabTools,
    ):
        self.persona = persona
        self.llm_service = llm_service
        self.tools = tools
        self.memory = AgentMemory()

    # ==================== 核心方法 ====================

    def prepare_and_respond_stream(self, context: LabContext):
        """
        先调用工具收集信息，再流式发言。

        Yields:
            dict: {type, agent, ...} 工具和发言事件
        """
        # 1. 执行工具
        tool_results = self._run_tools(context)
        if tool_results:
            tools_used = list(tool_results.keys())
            yield {
                "type": "tool_done",
                "agent": self.persona.id,
                "agent_name": self.persona.name,
                "agent_emoji": self.persona.emoji,
                "tools_used": tools_used,
            }
            # 将工具结果注入上下文
            context.tool_results = self._format_tool_results(tool_results)

        # 2. 构建 Prompt
        prompt = self._build_prompt(context)
        system_prompt = self._system_prompt()

        # 3. 流式发言（yield 纯文本 chunk）
        full_response = ""
        for chunk in self.llm_service.stream_chat(
            user_message=prompt,
            system_prompt=system_prompt,
        ):
            full_response += chunk
            yield chunk  # 纯文本

        # 4. 更新个体记忆
        if context.current_phase in ("brainstorm", "deep_dive"):
            self.memory.add_idea(full_response[:300])

    # ==================== 工具调用 ====================

    def _run_tools(self, context: LabContext) -> Dict[str, str]:
        """根据阶段和角色自动执行对应工具"""
        results = {}
        phase = context.current_phase

        # 阶段×角色 -> 工具调度表
        dispatch = self._get_tool_dispatch(phase, context)
        for tool_name, tool_kwargs in dispatch:
            try:
                tool_fn = getattr(self.tools, tool_name, None)
                if tool_fn:
                    result = tool_fn(**tool_kwargs)
                    if result:
                        results[tool_name] = result
            except Exception as e:
                logger.warning(f"工具 {tool_name} 执行失败: {e}")

        return results

    def _get_tool_dispatch(
        self, phase: str, context: LabContext
    ) -> List[tuple]:
        """
        按 (phase, agent_id) 返回工具调用计划。
        每项是 (tool_name, kwargs_dict)。
        """
        agent_id = self.persona.id

        # 从论文摘要提取关键词（简单方法）
        keywords = self._extract_keywords(context.paper_summary)

        dispatch_table = {
            # ---- 论文解读 ----
            ("paper_review", "phd_senior"): [
                ("deep_paper_search", {"queries": ["核心方法", "实验设计", "局限性 不足"]}),
            ],
            ("paper_review", "master"): [
                ("literature_survey", {"keywords": keywords[:3]}),
            ],
            # ---- 头脑风暴 ----
            ("brainstorm", "phd_senior"): [
                ("deep_paper_search", {"queries": ["改进", "不足", "未来工作 future work"]}),
            ],
            ("brainstorm", "phd_junior"): [
                ("cross_domain_search", {"method_keywords": " ".join(keywords[:2])}),
                ("analogy_finder", {"core_method": keywords[0] if keywords else "method"}),
            ],
            ("brainstorm", "master"): [
                ("citation_finder", {"technique": keywords[0] if keywords else "method"}),
            ],
            # ---- 导师点评 ----
            ("advisor_review", "advisor"): [
                ("idea_evaluator", {
                    "ideas": context.all_ideas.split("\n") if context.all_ideas else [],
                    "paper_context": context.paper_summary[:1000],
                }),
            ],
            # ---- 深入讨论 ----
            ("deep_dive", "phd_senior"): [
                ("experiment_designer", {
                    "idea": context.selected_direction[:500],
                    "paper_experiment_info": self.tools.deep_paper_search(
                        ["实验设置", "数据集", "评估指标"]
                    )[:500] if context.selected_direction else "",
                }),
            ],
            ("deep_dive", "phd_junior"): [
                ("innovation_challenger", {
                    "idea": context.selected_direction[:500],
                }),
            ],
            ("deep_dive", "master"): [
                ("discussion_summarizer", {
                    "discussion_text": context.discussion_history[:2000],
                }),
            ],
            # ---- 终审分工 ----
            ("final_plan", "advisor"): [
                ("direction_decider", {
                    "evaluation": context.tool_results or context.all_ideas[:1000],
                    "paper_summary": context.paper_summary[:1000],
                }),
            ],
        }

        key = (phase, agent_id)
        return dispatch_table.get(key, [])

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
        """从文本中提取关键词（简单实现）"""
        if not text:
            return ["method"]
        # 取前 500 字符中的中文关键词片段或英文单词
        words = text[:500].replace("，", " ").replace("。", " ").replace("、", " ").split()
        # 过滤过短的
        keywords = [w.strip() for w in words if len(w.strip()) >= 2]
        # 去重保序
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:max_keywords] if unique else ["method"]

    @staticmethod
    def _format_tool_results(results: Dict[str, str]) -> str:
        """格式化工具结果为 Prompt 可用的文本"""
        if not results:
            return "（无补充信息）"
        parts = []
        tool_labels = {
            "deep_paper_search": "📄 论文检索结果",
            "method_comparator": "⚖️ 方法对比",
            "experiment_designer": "🧪 实验方案参考",
            "cross_domain_search": "🌐 跨领域搜索",
            "analogy_finder": "🔗 跨领域类比",
            "innovation_challenger": "⚡ 批判性分析",
            "literature_survey": "📚 文献调研",
            "citation_finder": "📖 引文查找",
            "discussion_summarizer": "📋 讨论纪要",
            "idea_evaluator": "⭐ Idea 评估",
            "direction_decider": "🎯 方向建议",
        }
        for tool_name, result in results.items():
            label = tool_labels.get(tool_name, tool_name)
            # 截断过长结果
            text = result[:800] if len(result) > 800 else result
            parts.append(f"### {label}\n{text}")
        return "\n\n".join(parts)

    # ==================== Prompt 构建 ====================

    def _system_prompt(self) -> str:
        """构建角色 System Prompt"""
        return LAB_SYSTEM_PROMPT.format(
            name=self.persona.name,
            role=self.persona.role,
            expertise=self.persona.expertise,
            personality=self.persona.personality,
            behavior_guide=self.persona.behavior_guide,
        )

    def _build_prompt(self, context: LabContext) -> str:
        """构建发言 Prompt"""
        phase = context.current_phase
        template = PHASE_PROMPT_MAP.get(phase)

        if not template:
            return f"请以{self.persona.name}的身份，对当前讨论做出回应。"

        # 根据阶段填充不同的模板参数
        fmt_kwargs = {
            "paper_title": context.paper_title,
            "paper_summary": context.paper_summary[:2000],
            "agent_name": self.persona.name,
            "tool_results": context.tool_results or "（无补充信息）",
        }

        if phase == "paper_review":
            fmt_kwargs["previous_speakers"] = context.previous_speakers or "（你是第一个发言的）"
            fmt_kwargs["phase_focus"] = context.phase_focus or self.persona.phase_focus.get(phase, "")

        elif phase == "brainstorm":
            fmt_kwargs["discussion_history"] = context.discussion_history[:3000]
            fmt_kwargs["own_ideas"] = context.agent_own_ideas or "（暂无）"

        elif phase == "advisor_review":
            fmt_kwargs["full_discussion"] = context.full_discussion[:4000]
            fmt_kwargs["all_ideas"] = context.all_ideas or "（暂无 Idea）"

        elif phase == "deep_dive":
            fmt_kwargs["discussion_history"] = context.discussion_history[:3000]
            fmt_kwargs["selected_direction"] = context.selected_direction or "（待定）"
            fmt_kwargs["phase_focus"] = context.phase_focus or self.persona.phase_focus.get(phase, "")

        elif phase == "final_plan":
            fmt_kwargs["full_discussion"] = context.full_discussion[:5000]

        try:
            return template.format(**fmt_kwargs)
        except KeyError as e:
            logger.warning(f"Prompt 模板填充缺少字段: {e}")
            return template.format(**{k: fmt_kwargs.get(k, "") for k in template.split("{")[1:]})

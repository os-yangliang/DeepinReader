"""
课题组会议管理器 — 核心调度逻辑
"""
import logging
from enum import Enum
from typing import Dict, List, Optional

from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from agents.lab.base_agent import LabAgent
from agents.lab.memory import SharedMemory, LabContext
from agents.lab.tools import LabTools
from agents.lab.personas import (
    ADVISOR_PERSONA,
    PHD_SENIOR_PERSONA,
    PHD_JUNIOR_PERSONA,
    MASTER_PERSONA,
    PERSONA_MAP,
)
from prompts.lab_templates import PROPOSAL_PROMPT

logger = logging.getLogger(__name__)


class DiscussionPhase(Enum):
    PAPER_REVIEW = "paper_review"
    BRAINSTORM = "brainstorm"
    ADVISOR_REVIEW = "advisor_review"
    DEEP_DIVE = "deep_dive"
    FINAL_PLAN = "final_plan"


PHASE_LABELS = {
    "paper_review": "📄 论文解读",
    "brainstorm": "💡 头脑风暴",
    "advisor_review": "🧑‍🏫 导师点评",
    "deep_dive": "🔬 深入讨论",
    "final_plan": "📋 终审与分工",
}

# 每个阶段的发言顺序
SPEAKING_ORDERS = {
    "paper_review": ["master", "phd_senior", "phd_junior"],
    "brainstorm": ["phd_junior", "phd_senior", "master"],
    "advisor_review": ["advisor"],
    "deep_dive": ["phd_senior", "phd_junior", "master"],
    "final_plan": ["advisor"],
}


class LabSession:
    """
    一次课题组讨论会话。

    使用方式:
        session = LabSession(llm_service, vector_store, paper_summary, paper_title)
        for event in session.run_discussion_stream():
            # 处理事件: phase_start, tool_done, speaking, chunk, phase_end, proposal, done
            ...
    """

    def __init__(
        self,
        llm_service: LLMService,
        vector_store: VectorStoreService,
        paper_summary: str,
        paper_title: str,
        mode: str = "quick",
        user_focus: str = "",
    ):
        self.llm_service = llm_service
        self.vector_store = vector_store
        self.mode = mode  # "quick" (3 阶段) 或 "deep" (5 阶段)
        self.user_focus = user_focus

        # 初始化共享记忆
        self.shared_memory = SharedMemory(
            paper_title=paper_title,
            paper_summary=paper_summary,
            paper_content_brief=paper_summary[:3000],
        )

        # 初始化工具集
        self.tools = LabTools(llm_service, vector_store)

        # 初始化各 Agent
        self.agents: Dict[str, LabAgent] = {}
        for persona in [ADVISOR_PERSONA, PHD_SENIOR_PERSONA, PHD_JUNIOR_PERSONA, MASTER_PERSONA]:
            self.agents[persona.id] = LabAgent(
                persona=persona,
                llm_service=llm_service,
                tools=self.tools,
            )

        # 最终提案
        self.proposal: str = ""

    def _get_phases(self) -> List[DiscussionPhase]:
        """获取讨论阶段列表"""
        if self.mode == "quick":
            return [
                DiscussionPhase.PAPER_REVIEW,
                DiscussionPhase.BRAINSTORM,
                DiscussionPhase.ADVISOR_REVIEW,
            ]
        else:  # deep
            return [
                DiscussionPhase.PAPER_REVIEW,
                DiscussionPhase.BRAINSTORM,
                DiscussionPhase.ADVISOR_REVIEW,
                DiscussionPhase.DEEP_DIVE,
                DiscussionPhase.FINAL_PLAN,
            ]

    def run_discussion_stream(self):
        """
        流式执行整个讨论流程。

        Yields:
            dict: 事件字典，类型包括:
                - phase_start: 阶段开始
                - tool_done: 工具调用完成
                - speaking: Agent 开始发言
                - chunk: 发言文本片段
                - phase_end: 阶段结束
                - proposal_start: 开始生成提案
                - proposal_chunk: 提案文本片段
                - done: 讨论完成
        """
        phases = self._get_phases()
        total_phases = len(phases)

        for phase_idx, phase in enumerate(phases):
            phase_name = phase.value
            phase_label = PHASE_LABELS.get(phase_name, phase_name)
            speaking_order = SPEAKING_ORDERS.get(phase_name, [])

            # === 阶段开始 ===
            yield {
                "type": "phase_start",
                "phase": phase_name,
                "phase_label": phase_label,
                "phase_index": phase_idx,
                "total_phases": total_phases,
            }

            # 本阶段的发言记录（用于 previous_speakers）
            phase_speakers_text = ""

            for agent_id in speaking_order:
                agent = self.agents.get(agent_id)
                if not agent:
                    continue

                # 构建上下文
                context = self._build_context(phase_name, agent_id, phase_speakers_text)

                # === Agent 开始发言 ===
                yield {
                    "type": "speaking",
                    "agent": agent_id,
                    "agent_name": agent.persona.name,
                    "agent_emoji": agent.persona.emoji,
                    "agent_role": agent.persona.role,
                    "phase": phase_name,
                }

                # 流式执行（工具 + 发言）
                full_response = ""
                for event in agent.prepare_and_respond_stream(context):
                    if isinstance(event, dict):
                        # 工具事件
                        yield event
                    else:
                        # 纯文本 chunk
                        full_response += event
                        yield {
                            "type": "chunk",
                            "agent": agent_id,
                            "content": event,
                        }

                # 记录到共享记忆
                self.shared_memory.add_message(
                    speaker_id=agent_id,
                    speaker_name=agent.persona.name,
                    speaker_emoji=agent.persona.emoji,
                    content=full_response,
                    phase=phase_name,
                )

                # 更新本阶段发言记录
                phase_speakers_text += (
                    f"\n\n{agent.persona.emoji} {agent.persona.name}：{full_response}"
                )

                # 如果是导师点评阶段，提取选中方向
                if phase_name == "advisor_review" and agent_id == "advisor":
                    self.shared_memory.selected_direction = full_response

                # 如果是终审阶段，保存最终决策
                if phase_name == "final_plan" and agent_id == "advisor":
                    self.shared_memory.final_decision = full_response

            # === 阶段结束 ===
            yield {
                "type": "phase_end",
                "phase": phase_name,
                "phase_label": phase_label,
            }

        # === 生成最终研究提案 ===
        yield from self._generate_proposal_stream()

        # === 讨论完成 ===
        yield {
            "type": "done",
            "proposal": self.proposal,
            "discussion_summary": self.shared_memory.get_discussion_text(max_chars=5000),
        }

    def _build_context(
        self, phase: str, agent_id: str, phase_speakers_text: str
    ) -> LabContext:
        """为指定 Agent 构建发言上下文"""
        agent = self.agents[agent_id]
        persona = agent.persona

        context = LabContext(
            current_phase=phase,
            paper_title=self.shared_memory.paper_title,
            paper_summary=self.shared_memory.paper_summary,
            discussion_history=self.shared_memory.get_discussion_text(max_chars=4000),
            previous_speakers=phase_speakers_text or "（你是本阶段第一个发言的）",
            agent_own_ideas=agent.memory.get_own_ideas_text(),
            phase_focus=persona.phase_focus.get(phase, ""),
        )

        # 阶段特定字段
        if phase == "advisor_review":
            ideas = self.shared_memory.extract_ideas()
            context.all_ideas = "\n".join(ideas) if ideas else "（暂无 Idea）"
            context.full_discussion = self.shared_memory.get_discussion_text(max_chars=5000)

        elif phase == "deep_dive":
            context.selected_direction = (
                self.shared_memory.selected_direction or "（导师尚未选定方向）"
            )

        elif phase == "final_plan":
            context.full_discussion = self.shared_memory.get_discussion_text(max_chars=6000)
            context.all_ideas = "\n".join(self.shared_memory.extract_ideas())

        # 用户指定关注方向
        if self.user_focus:
            context.phase_focus = (
                f"{context.phase_focus}\n用户特别关注的方向：{self.user_focus}"
            )

        return context

    def _generate_proposal_stream(self):
        """流式生成研究提案"""
        yield {
            "type": "proposal_start",
            "message": "📝 正在生成研究提案...",
        }

        prompt = PROPOSAL_PROMPT.format(
            paper_title=self.shared_memory.paper_title,
            paper_summary=self.shared_memory.paper_summary[:2000],
            full_discussion=self.shared_memory.get_discussion_text(max_chars=5000),
            final_decision=self.shared_memory.final_decision
            or self.shared_memory.selected_direction
            or "（讨论未产生明确决策，请基于讨论自行总结）",
        )

        full_proposal = ""
        try:
            for chunk in self.llm_service.stream_chat(prompt):
                full_proposal += chunk
                yield {
                    "type": "proposal_chunk",
                    "content": chunk,
                }
        except Exception as e:
            logger.error(f"研究提案生成失败: {e}")
            yield {
                "type": "proposal_chunk",
                "content": f"\n\n❌ 提案生成出错: {e}",
            }

        self.proposal = full_proposal

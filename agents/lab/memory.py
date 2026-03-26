"""
课题组记忆系统 — 共享记忆 + 个体记忆
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time


@dataclass
class SharedMemory:
    """课题组共享记忆"""
    paper_title: str = ""
    paper_summary: str = ""             # 来自已有分析结果
    paper_content_brief: str = ""       # 论文内容摘要（截断版）
    discussion_log: List[Dict] = field(default_factory=list)
    # [{speaker_id, speaker_name, speaker_emoji, content, phase, timestamp}]
    agreed_ideas: List[str] = field(default_factory=list)
    action_items: List[Dict] = field(default_factory=list)
    # [{assignee, task, description}]
    selected_direction: str = ""        # 导师选中的方向
    final_decision: str = ""            # 导师最终决策

    def add_message(self, speaker_id: str, speaker_name: str,
                    speaker_emoji: str, content: str, phase: str):
        """记录一条发言"""
        self.discussion_log.append({
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
            "speaker_emoji": speaker_emoji,
            "content": content,
            "phase": phase,
            "timestamp": time.time(),
        })

    def get_discussion_text(self, max_chars: int = 8000) -> str:
        """获取格式化的讨论历史文本"""
        lines = []
        for msg in self.discussion_log:
            line = f"{msg['speaker_emoji']} {msg['speaker_name']}：{msg['content']}"
            lines.append(line)
        text = "\n\n".join(lines)
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text

    def get_phase_discussion(self, phase: str) -> str:
        """获取指定阶段的讨论记录"""
        lines = []
        for msg in self.discussion_log:
            if msg["phase"] == phase:
                line = f"{msg['speaker_emoji']} {msg['speaker_name']}：{msg['content']}"
                lines.append(line)
        return "\n\n".join(lines)

    def extract_ideas(self) -> List[str]:
        """提取讨论中的 Idea（简单方法：搜集头脑风暴阶段的发言）"""
        ideas = []
        for msg in self.discussion_log:
            if msg["phase"] in ("brainstorm", "deep_dive"):
                ideas.append(f"{msg['speaker_name']}: {msg['content'][:300]}")
        return ideas


@dataclass
class AgentMemory:
    """个体记忆"""
    observations: List[str] = field(default_factory=list)
    own_ideas: List[str] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)

    def add_observation(self, text: str):
        """记录观察（其他人说了什么）"""
        self.observations.append(text)

    def add_idea(self, text: str):
        """记录自己的想法"""
        self.own_ideas.append(text)

    def get_own_ideas_text(self) -> str:
        """获取自己之前的想法"""
        if not self.own_ideas:
            return "（暂无）"
        return "\n".join([f"- {idea[:200]}" for idea in self.own_ideas])


@dataclass
class LabContext:
    """Agent 发言时的上下文"""
    current_phase: str
    paper_title: str
    paper_summary: str
    discussion_history: str       # 格式化的讨论历史
    previous_speakers: str        # 本阶段前面的发言
    agent_own_ideas: str          # 该 Agent 自己之前的想法
    tool_results: str = ""        # 工具调用结果
    phase_focus: str = ""         # 本阶段该角色的关注重点
    selected_direction: str = ""  # 导师选中的方向（深入讨论阶段用）
    all_ideas: str = ""           # 所有提出的 Idea（导师点评阶段用）
    full_discussion: str = ""     # 完整讨论记录（终审阶段用）

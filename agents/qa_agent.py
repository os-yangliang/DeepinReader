"""
问答 Agent - 基于 RAG 的论文问答 (支持 Plan-and-Solve)
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import time
import logging
import json

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from services.tools import tool_service
from prompts.templates import (
    QA_PROMPT, 
    CHAT_SYSTEM_PROMPT, 
    PLANNER_PROMPT, 
    SOLVER_PROMPT
)

logger = logging.getLogger(__name__)

@dataclass
class QAResult:
    """问答结果"""
    success: bool
    answer: str = ""
    source_chunks: List[str] = None
    error_message: str = ""
    processing_time: float = 0.0
    
    def __post_init__(self):
        if self.source_chunks is None:
            self.source_chunks = []


class QAAgent:
    """问答 Agent - 基于 Plan-and-Solve 架构"""
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        vector_store: Optional[VectorStoreService] = None
    ):
        self.llm_service = llm_service or LLMService()
        self.vector_store = vector_store or VectorStoreService()
        
        # 聊天历史
        self.chat_history: List[Dict[str, str]] = []
        
        # 当前文档信息
        self.current_doc_id: Optional[str] = None
        self.current_paper_title: str = ""
        self.current_paper_summary: str = ""
        self._cached_suggestions: Optional[List[str]] = None
    
    def set_document_context(
        self,
        doc_id: str,
        paper_title: str = "",
        paper_summary: str = ""
    ) -> bool:
        """
        设置当前文档上下文
        """
        try:
            # 短路：如果已经是同一个文档，更新元信息即可，不重新加载集合
            if self.current_doc_id == doc_id:
                self.current_paper_title = paper_title
                self.current_paper_summary = paper_summary
                return True

            # 加载向量集合（内部已有短路缓存）
            success = self.vector_store.load_collection(doc_id)
            if success:
                self.current_doc_id = doc_id
                self.current_paper_title = paper_title
                self.current_paper_summary = paper_summary
                self.chat_history = []
                self._cached_suggestions = None  # 清除建议问题缓存
                return True
            return False
        except Exception:
            return False
    
    def _plan(self, question: str) -> List[Dict[str, str]]:
        """
        [Planner] 规划求解步骤
        """
        prompt = PLANNER_PROMPT.format(question=question)
        
        # 调用 LLM 生成计划
        # 这里不使用 history，因为 planning 是一个独立的推理过程
        plan_text = self.llm_service.chat_sync(user_message=prompt, chat_history=[])
        
        steps = []
        for line in plan_text.split('\n'):
            line = line.strip()
            if not line.startswith("Step"):
                continue
                
            # 解析: Step 1: [Search Paper] xxx
            try:
                parts = line.split(':', 1)
                if len(parts) < 2: continue
                
                content = parts[1].strip()
                if "[Search Paper]" in content:
                    query = content.replace("[Search Paper]", "").strip()
                    steps.append({"tool": "paper", "query": query})
                elif "[Search Web]" in content:
                    query = content.replace("[Search Web]", "").strip()
                    steps.append({"tool": "web", "query": query})
            except Exception as e:
                logger.warning(f"解析计划步骤失败: {line}, error: {e}")
                
        # 如果没有生成有效计划（可能是简单问题），返回默认单步计划
        if not steps:
            steps.append({"tool": "paper", "query": question})
            
        return steps

    def _execute(self, steps: List[Dict[str, str]]) -> str:
        """
        [Executor] 执行步骤并收集证据
        """
        evidence = []
        
        for i, step in enumerate(steps, 1):
            tool = step["tool"]
            query = step["query"]
            
            result_text = ""
            if tool == "paper":
                # 使用 Hybrid Search (用 get_relevant_documents 避免参数冲突)
                retriever = self.vector_store.get_retriever(k=3)
                try:
                    # 优先使用兼容性更好的方法
                    if hasattr(retriever, 'get_relevant_documents'):
                        docs = retriever.get_relevant_documents(query)
                    else:
                        docs = retriever.invoke(query)
                except Exception as e:
                    logger.warning(f"Retriever error: {e}")
                    docs = []
                result_text = "\n".join([f"- {doc.page_content}" for doc in docs]) if docs else "(未找到相关内容)"
                source = "论文检索"
            elif tool == "web":
                result_text = tool_service.web_search(query)
                source = "网络搜索"
            
            evidence.append(f"### 信息来源 {i} ({source}): {query}\n{result_text}\n")
            
        return "\n".join(evidence)

    def _solve(self, question: str, evidence: str, use_history: bool = True) -> str:
        """
        [Solver] 综合回答
        """
        full_prompt = SOLVER_PROMPT.format(question=question, evidence=evidence)
        
        # 准备历史记录
        history = self.chat_history if use_history else None
        
        # 调用 LLM 生成最终回答
        answer = self.llm_service.chat_sync(
            user_message=full_prompt,
            system_prompt=self._build_system_prompt(), # 保持人设
            chat_history=history
        )
        return answer

    def ask(
        self,
        question: str,
        top_k: int = 5,
        use_history: bool = True
    ) -> QAResult:
        """
        Plan-and-Solve 模式回答问题
        """
        start_time = time.time()
        
        if self.current_doc_id is None:
            return QAResult(success=False, error_message="请先上传并解析论文文档")
        
        try:
            # 1. Plan
            steps = self._plan(question)
            logger.info(f"Generated Plan: {steps}")
            
            # 2. Execute
            evidence = self._execute(steps)
            
            # 3. Solve
            answer = self._solve(question, evidence, use_history)
            
            # 更新历史
            if use_history:
                self.chat_history.append({"role": "user", "content": question})
                self.chat_history.append({"role": "assistant", "content": answer})
                if len(self.chat_history) > 20:
                    self.chat_history = self.chat_history[-20:]
            
            # 简单的来源追踪 (取第一步检索的片段，如果有的话)
            source_chunks = []
            if steps and steps[0]["tool"] == "paper":
                 # 这里简单模拟，实际上 evidence 已经包含了文本
                 source_chunks = [evidence[:200] + "..."]

            return QAResult(
                success=True,
                answer=answer,
                source_chunks=source_chunks,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.exception("Plan-and-Solve failed")
            return QAResult(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
    # ask_async 和 ask_stream 的逻辑类似，这里为了保持一致性暂时简化
    # 真正的流式 Plan-and-Solve 比较复杂（需要流式输出“正在规划...”、“正在搜索...”等状态）
    # 这里我们简单实现 ask_stream，暂不展示中间步骤，只流式输出最终结果
    
    def ask_stream(self, question: str, top_k: int = 5):
        if self.current_doc_id is None:
            yield "请先上传并解析论文文档"
            return

        try:
            # 为了用户体验，先输出一些思考过程
            yield "正在分析问题并制定检索计划...\n"
            steps = self._plan(question)
            
            # 收集引用来源
            source_docs = []
            
            for step in steps:
                tool_name = "论文" if step["tool"] == "paper" else "网络"
                yield f"> 正在检索{tool_name}: {step['query']}...\n"
            
            # Execute 并收集源文档
            evidence_parts = []
            for i, step in enumerate(steps, 1):
                tool = step["tool"]
                query = step["query"]
                
                if tool == "paper":
                    retriever = self.vector_store.get_retriever(k=3)
                    try:
                        if hasattr(retriever, 'get_relevant_documents'):
                            docs = retriever.get_relevant_documents(query)
                        else:
                            docs = retriever.invoke(query)
                    except Exception as e:
                        logger.warning(f"Retriever error: {e}")
                        docs = []
                    
                    for j, doc in enumerate(docs):
                        meta = doc.metadata or {}
                        page = meta.get("page", meta.get("page_number", "?"))
                        source_docs.append({
                            "text": doc.page_content[:200].strip(),
                            "page": page,
                            "section": meta.get("section", ""),
                        })
                    
                    result_text = "\n".join([f"- {doc.page_content}" for doc in docs]) if docs else "(未找到相关内容)"
                    evidence_parts.append(f"### 信息来源 {i} (论文检索): {query}\n{result_text}\n")
                elif tool == "web":
                    result_text = tool_service.web_search(query)
                    evidence_parts.append(f"### 信息来源 {i} (网络搜索): {query}\n{result_text}\n")
            
            evidence = "\n".join(evidence_parts)
            
            yield "> 正在综合信息生成回答...\n\n"
            
            # Solve Stream
            full_prompt = SOLVER_PROMPT.format(question=question, evidence=evidence)
            full_answer = ""
            for chunk in self.llm_service.stream_chat(
                user_message=full_prompt,
                system_prompt=self._build_system_prompt(),
                chat_history=self.chat_history
            ):
                full_answer += chunk
                yield chunk
                
            self.chat_history.append({"role": "user", "content": question})
            self.chat_history.append({"role": "assistant", "content": full_answer})
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]
            
            # 去重并输出引用来源
            seen = set()
            unique_sources = []
            for s in source_docs:
                key = s["text"][:80]
                if key not in seen:
                    seen.add(key)
                    unique_sources.append(s)
            
            if unique_sources:
                yield "\n__SOURCES__" + json.dumps(unique_sources[:5], ensure_ascii=False)
                
        except Exception as e:
            yield f"回答出错: {str(e)}"

    def _build_context(self, documents: List[Document]) -> str:
        """(Legacy) 构建上下文"""
        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(f"[片段 {i}]\n{doc.page_content}")
        return "\n\n".join(context_parts)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return CHAT_SYSTEM_PROMPT.format(
            paper_title=self.current_paper_title or "未知标题",
            paper_summary=self.current_paper_summary[:1000] if self.current_paper_summary else "暂无摘要"
        )
    
    def clear_history(self) -> None:
        self.chat_history = []
    
    def get_chat_history(self) -> List[Dict[str, str]]:
        return self.chat_history.copy()
    
    def get_suggested_questions(self) -> List[str]:
        """根据论文内容动态生成建议问题（带缓存）"""
        # 如果有缓存，直接返回
        if hasattr(self, '_cached_suggestions') and self._cached_suggestions:
            return self._cached_suggestions

        default_questions = [
            "这篇论文的主要研究问题是什么？",
            "论文使用了什么方法来解决问题？",
            "实验结果如何？有什么重要发现？",
            "这篇论文的创新点是什么？",
            "论文有什么局限性或不足？",
            "作者提出了哪些未来研究方向？",
        ]
        
        # 如果有论文摘要，使用 LLM 生成个性化建议问题
        if self.current_paper_summary and len(self.current_paper_summary) > 100:
            try:
                prompt = f"""根据以下论文摘要，生成 6 个对读者最有价值的具体问题。
问题应当具体、有针对性，而不是泛泛而谈。每行一个问题，不要编号。

论文标题: {self.current_paper_title or "未知"}
论文摘要:
{self.current_paper_summary[:1500]}

请直接输出 6 个问题，每行一个："""
                
                result = self.llm_service.generate_with_prompt(prompt, {})
                if result:
                    questions = [q.strip().lstrip("0123456789.、）) ") for q in result.strip().split("\n") if q.strip()]
                    if len(questions) >= 3:
                        self._cached_suggestions = questions[:6]
                        return self._cached_suggestions
            except Exception as e:
                logger.warning(f"动态生成建议问题失败，使用默认问题: {e}")
        
        return default_questions

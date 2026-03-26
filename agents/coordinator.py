"""
协调 Agent - 使用 LangGraph 管理多智能体工作流
"""
from typing import TypedDict, Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
import time

from langgraph.graph import StateGraph, END

from services.document_parser import ParsedDocument
from services.llm_service import LLMService
from services.vector_store import VectorStoreService
from agents.parser_agent import ParserAgent, ParserResult
from agents.summarizer_agent import SummarizerAgent, SummaryResult
from agents.qa_agent import QAAgent, QAResult
from prompts.templates import TRANSLATE_PROMPT, CODE_GENERATION_PROMPT, CODE_GENERATION_SYSTEM_PROMPT


class PaperReaderState(TypedDict):
    """论文阅读系统状态"""
    # 输入
    file_path: Optional[str]
    file_bytes: Optional[bytes]
    filename: Optional[str]
    user_question: Optional[str]
    
    # 处理状态
    current_stage: str
    error_message: Optional[str]
    
    # 解析结果
    document_id: Optional[str]
    parsed_doc: Optional[ParsedDocument]
    structure_info: Optional[str]
    
    # 摘要结果
    summary: Optional[str]
    keywords: Optional[str]
    
    # 问答结果
    qa_answer: Optional[str]
    source_chunks: List[str]
    
    # 统计信息
    processing_times: Dict[str, float]


@dataclass
class ProcessingResult:
    """处理结果汇总"""
    success: bool
    stage: str
    document_id: str = ""
    paper_title: str = ""
    structure_info: str = ""
    summary: str = ""
    keywords: str = ""
    qa_answer: str = ""
    source_chunks: List[str] = field(default_factory=list)
    error_message: str = ""
    total_time: float = 0.0
    stage_times: Dict[str, float] = field(default_factory=dict)


class PaperReaderCoordinator:
    """
    论文阅读协调器 - 管理多智能体工作流
    
    工作流程:
    1. 文档上传 -> 解析 Agent 处理
    2. 解析完成 -> 摘要 Agent 生成分析报告
    3. 用户提问 -> 问答 Agent 回答
    """
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        vector_store: Optional[VectorStoreService] = None
    ):
        # 初始化共享服务
        try:
            self.llm_service = llm_service or LLMService()
        except ValueError as e:
            # API Key 未配置等错误
            raise ValueError(f"LLM 服务初始化失败: {str(e)}")
        
        try:
            self.vector_store = vector_store or VectorStoreService()
        except Exception as e:
            raise ValueError(f"向量存储服务初始化失败: {str(e)}")
        
        # 初始化各个 Agent
        self.parser_agent = ParserAgent(
            vector_store=self.vector_store,
            llm_service=self.llm_service
        )
        self.summarizer_agent = SummarizerAgent(llm_service=self.llm_service)
        self.qa_agent = QAAgent(
            llm_service=self.llm_service,
            vector_store=self.vector_store
        )
        
        # 当前状态
        self.current_state: Optional[PaperReaderState] = None
        
        # 构建工作流图
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """构建 LangGraph 工作流"""
        # 创建状态图
        workflow = StateGraph(PaperReaderState)
        
        # 添加节点
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("qa", self._qa_node)
        workflow.add_node("error", self._error_node)
        
        # 设置入口点
        workflow.set_entry_point("parse")
        
        # 添加边
        workflow.add_conditional_edges(
            "parse",
            self._route_after_parse,
            {
                "summarize": "summarize",
                "error": "error"
            }
        )
        
        workflow.add_conditional_edges(
            "summarize",
            self._route_after_summarize,
            {
                "end": END,
                "error": "error"
            }
        )
        
        workflow.add_edge("qa", END)
        workflow.add_edge("error", END)
        
        return workflow.compile()
    
    def _parse_node(self, state: PaperReaderState) -> PaperReaderState:
        """解析节点"""
        start_time = time.time()
        
        try:
            if state.get("file_bytes") and state.get("filename"):
                # 从字节流解析
                result = self.parser_agent.parse_document_from_bytes(
                    state["file_bytes"],
                    state["filename"]
                )
            elif state.get("file_path"):
                # 从文件路径解析
                result = self.parser_agent.parse_document(state["file_path"])
            else:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": "未提供文件"
                }
            
            if result.success:
                processing_times = state.get("processing_times", {})
                processing_times["parse"] = time.time() - start_time
                
                return {
                    **state,
                    "current_stage": "parsed",
                    "document_id": result.document_id,
                    "parsed_doc": result.parsed_doc,
                    "structure_info": result.structure_info,
                    "processing_times": processing_times
                }
            else:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": result.error_message
                }
                
        except Exception as e:
            return {
                **state,
                "current_stage": "error",
                "error_message": str(e)
            }
    
    def _summarize_node(self, state: PaperReaderState) -> PaperReaderState:
        """摘要节点"""
        start_time = time.time()
        
        try:
            parsed_doc = state.get("parsed_doc")
            if not parsed_doc:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": "缺少解析后的文档"
                }
            
            result = self.summarizer_agent.generate_summary(parsed_doc)
            
            processing_times = state.get("processing_times", {})
            processing_times["summarize"] = time.time() - start_time
            
            if result.success:
                return {
                    **state,
                    "current_stage": "summarized",
                    "summary": result.summary,
                    "keywords": result.keywords,
                    "processing_times": processing_times
                }
            else:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": result.error_message,
                    "processing_times": processing_times
                }
                
        except Exception as e:
            return {
                **state,
                "current_stage": "error",
                "error_message": str(e)
            }
    
    def _qa_node(self, state: PaperReaderState) -> PaperReaderState:
        """问答节点"""
        start_time = time.time()
        
        try:
            question = state.get("user_question")
            if not question:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": "未提供问题"
                }
            
            result = self.qa_agent.ask(question)
            
            processing_times = state.get("processing_times", {})
            processing_times["qa"] = time.time() - start_time
            
            if result.success:
                return {
                    **state,
                    "current_stage": "answered",
                    "qa_answer": result.answer,
                    "source_chunks": result.source_chunks,
                    "processing_times": processing_times
                }
            else:
                return {
                    **state,
                    "current_stage": "error",
                    "error_message": result.error_message,
                    "processing_times": processing_times
                }
                
        except Exception as e:
            return {
                **state,
                "current_stage": "error",
                "error_message": str(e)
            }
    
    def _error_node(self, state: PaperReaderState) -> PaperReaderState:
        """错误处理节点"""
        return {
            **state,
            "current_stage": "failed"
        }
    
    def _route_after_parse(self, state: PaperReaderState) -> Literal["summarize", "error"]:
        """解析后的路由决策"""
        if state.get("current_stage") == "parsed":
            return "summarize"
        return "error"
    
    def _route_after_summarize(self, state: PaperReaderState) -> Literal["end", "error"]:
        """摘要后的路由决策"""
        if state.get("current_stage") == "summarized":
            return "end"
        return "error"
    
    def process_document(
        self,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> ProcessingResult:
        """
        处理文档（完整流程：解析 + 摘要）
        
        Args:
            file_path: 文件路径
            file_bytes: 文件字节流
            filename: 文件名
            
        Returns:
            ProcessingResult: 处理结果
        """
        start_time = time.time()
        
        # 初始化状态
        initial_state: PaperReaderState = {
            "file_path": file_path,
            "file_bytes": file_bytes,
            "filename": filename,
            "user_question": None,
            "current_stage": "start",
            "error_message": None,
            "document_id": None,
            "parsed_doc": None,
            "structure_info": None,
            "summary": None,
            "keywords": None,
            "qa_answer": None,
            "source_chunks": [],
            "processing_times": {}
        }
        
        # 运行工作流
        try:
            final_state = self.workflow.invoke(initial_state)
            self.current_state = final_state
            
            # 设置问答 Agent 的文档上下文
            if final_state.get("document_id"):
                parsed_doc = final_state.get("parsed_doc")
                self.qa_agent.set_document_context(
                    doc_id=final_state["document_id"],
                    paper_title=parsed_doc.title if parsed_doc else "",
                    paper_summary=(final_state.get("summary") or "")[:500]
                )
            
            total_time = time.time() - start_time
            
            if final_state.get("current_stage") in ["summarized", "answered"]:
                parsed_doc = final_state.get("parsed_doc")
                return ProcessingResult(
                    success=True,
                    stage=final_state["current_stage"],
                    document_id=final_state.get("document_id", ""),
                    paper_title=parsed_doc.title if parsed_doc else "",
                    structure_info=final_state.get("structure_info") or "",
                    summary=final_state.get("summary") or "",
                    keywords=final_state.get("keywords") or "",
                    total_time=total_time,
                    stage_times=final_state.get("processing_times", {})
                )
            else:
                return ProcessingResult(
                    success=False,
                    stage=final_state.get("current_stage", "unknown"),
                    error_message=final_state.get("error_message") or "未知错误",
                    total_time=total_time
                )
                
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("process_document 异常")
            return ProcessingResult(
                success=False,
                stage="exception",
                error_message=str(e),
                total_time=time.time() - start_time
            )
    
    def ask_question(self, question: str) -> QAResult:
        """
        回答问题（使用已解析的文档）
        
        Args:
            question: 用户问题
            
        Returns:
            QAResult: 问答结果
        """
        return self.qa_agent.ask(question)
    
    def ask_question_stream(self, question: str):
        """
        流式回答问题
        
        Args:
            question: 用户问题
            
        Yields:
            str: 流式输出的回答片段
        """
        yield from self.qa_agent.ask_stream(question)
    
    def get_suggested_questions(self) -> List[str]:
        """获取建议问题"""
        return self.qa_agent.get_suggested_questions()
    
    def clear_chat_history(self) -> None:
        """清除聊天历史"""
        self.qa_agent.clear_history()

    # ==================== 拆分后的两步流程 ====================

    def parse_and_index(self, file_bytes: bytes, filename: str) -> dict:
        """
        步骤1: 解析文档 + 建立向量索引（快速，~5秒，无 LLM 调用）
        上传后立即可用问答/翻译/代码功能。
        
        Returns:
            dict: 文档信息 {"filename", "title", "document_id", ...}
        Raises:
            Exception: 解析或索引失败
        """
        import hashlib
        from services.document_parser import DocumentParser

        # 解析文档
        parser = DocumentParser()
        parsed_doc = parser.parse_from_bytes(file_bytes, filename)

        # 生成文档 ID
        hash_input = f"{parsed_doc.filename}_{len(parsed_doc.content)}_{parsed_doc.content[:1000]}"
        doc_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]

        # 存入向量库
        self.vector_store.create_collection(doc_id)
        base_metadata = {
            "filename": parsed_doc.filename,
            "file_type": parsed_doc.file_type,
            "title": parsed_doc.title,
            "page_count": parsed_doc.page_count,
        }
        if parsed_doc.chunks:
            metadatas = [base_metadata.copy() for _ in parsed_doc.chunks]
            self.vector_store.add_documents(parsed_doc.chunks, metadatas)
        else:
            self.vector_store.add_document_with_splitting(
                parsed_doc.content, base_metadata
            )

        # 更新状态（此时 QA/Code/Translate 已可用）
        self.current_state = {
            "document_id": doc_id,
            "parsed_doc": parsed_doc,
            "summary": "",
            "structure_info": "",
            "keywords": "",
            "current_stage": "indexed",
        }

        # 设置 QA Agent 上下文（暂无摘要，后续分析完成后更新）
        self.qa_agent.set_document_context(
            doc_id=doc_id,
            paper_title=parsed_doc.title or "",
            paper_summary="",
        )

        return {
            "filename": parsed_doc.filename,
            "title": parsed_doc.title,
            "file_type": parsed_doc.file_type,
            "page_count": parsed_doc.page_count,
            "word_count": parsed_doc.word_count,
            "document_id": doc_id,
        }

    def stream_analysis(self):
        """
        步骤2: 流式 LLM 分析（可选，独立于上传）
        
        Yields:
            dict: {"stage": "analyzing", "chunk": "..."} 或 {"stage": "done", ...}
        """
        from prompts.templates import PAPER_ANALYSIS_PROMPT

        if not self.current_state or not self.current_state.get("parsed_doc"):
            yield {"stage": "error", "message": "请先上传文档"}
            return

        parsed_doc = self.current_state["parsed_doc"]
        doc_id = self.current_state.get("document_id", "")

        # 阶段1: 准备
        yield {"stage": "progress", "percent": 10, "step": "preparing", "message": "正在准备分析..."}

        # 智能截断内容
        content = parsed_doc.content
        max_len = 15000
        if len(content) > max_len:
            head = int(max_len * 0.6)
            tail = max_len - head
            content = content[:head] + "\n\n...(中间部分省略)...\n\n" + content[-tail:]

        yield {"stage": "progress", "percent": 20, "step": "content_ready", "message": "文档内容准备就绪"}

        prompt = PAPER_ANALYSIS_PROMPT.format(paper_content=content)

        yield {"stage": "progress", "percent": 30, "step": "llm_start", "message": "AI 模型开始分析..."}

        full_response = ""
        chunk_count = 0
        try:
            for chunk in self.llm_service.stream_chat(prompt):
                full_response += chunk
                chunk_count += 1
                yield {"stage": "analyzing", "chunk": chunk}
                
                # 每 10 个 chunk 发送一次进度（35% → 90%）
                if chunk_count % 10 == 0:
                    # 基于输出长度估算进度（假设正常分析 ~3000字）
                    est_progress = min(90, 35 + int(len(full_response) / 3000 * 55))
                    yield {"stage": "progress", "percent": est_progress, "step": "analyzing", "message": "AI 正在生成分析报告..."}
        except Exception as e:
            yield {"stage": "error", "message": f"AI 分析失败: {str(e)}"}
            return

        yield {"stage": "progress", "percent": 95, "step": "saving", "message": "正在保存分析结果..."}

        # 更新状态
        self.current_state["summary"] = full_response
        self.current_state["current_stage"] = "analyzed"

        # 用摘要更新 QA Agent
        self.qa_agent.set_document_context(
            doc_id=doc_id,
            paper_title=parsed_doc.title or "",
            paper_summary=full_response[:500],
        )

        yield {
            "stage": "done",
            "message": "分析完成",
            "analysis": full_response,
        }


    def process_document_stream(self, file_bytes: bytes, filename: str):
        """
        流式处理文档（单次 LLM 调用，实时输出）
        
        Yields:
            dict: SSE 事件，格式为:
                {"stage": "parsing|parsed|analyzing|done", "message": "...", ...}
                {"stage": "analyzing", "chunk": "..."}  # LLM 流式输出
        """
        import hashlib
        from services.document_parser import DocumentParser
        from prompts.templates import PAPER_ANALYSIS_PROMPT
        
        start_time = time.time()
        
        # ---- 阶段1: 解析文档 ----
        yield {"stage": "parsing", "message": "正在解析文档..."}
        
        try:
            parser = DocumentParser()
            parsed_doc = parser.parse_from_bytes(file_bytes, filename)
        except Exception as e:
            yield {"stage": "error", "message": f"文档解析失败: {str(e)}"}
            return
        
        # 生成文档ID
        hash_input = f"{parsed_doc.filename}_{len(parsed_doc.content)}_{parsed_doc.content[:1000]}"
        doc_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]
        
        doc_info = {
            "filename": parsed_doc.filename,
            "title": parsed_doc.title,
            "file_type": parsed_doc.file_type,
            "page_count": parsed_doc.page_count,
            "word_count": parsed_doc.word_count,
            "document_id": doc_id,
        }
        
        yield {
            "stage": "parsed",
            "message": f"解析完成：{parsed_doc.page_count} 页，{parsed_doc.word_count} 字",
            "document_info": doc_info,
        }
        
        # ---- 阶段2: 存入向量库 ----
        yield {"stage": "indexing", "message": "正在建立知识索引..."}
        
        try:
            self.vector_store.create_collection(doc_id)
            base_metadata = {
                "filename": parsed_doc.filename,
                "file_type": parsed_doc.file_type,
                "title": parsed_doc.title,
                "page_count": parsed_doc.page_count,
            }
            if parsed_doc.chunks:
                metadatas = [base_metadata.copy() for _ in parsed_doc.chunks]
                self.vector_store.add_documents(parsed_doc.chunks, metadatas)
            else:
                self.vector_store.add_document_with_splitting(
                    parsed_doc.content, base_metadata
                )
        except Exception as e:
            yield {"stage": "error", "message": f"知识索引建立失败: {str(e)}"}
            return
        
        yield {"stage": "indexed", "message": "知识索引建立完成"}
        
        # ---- 阶段3: 流式 LLM 分析（单次调用） ----
        yield {"stage": "analyzing", "message": "AI 正在分析论文..."}
        
        # 智能截断内容
        content = parsed_doc.content
        max_len = 15000
        if len(content) > max_len:
            head = int(max_len * 0.6)
            tail = max_len - head
            content = content[:head] + "\n\n...(中间部分省略)...\n\n" + content[-tail:]
        
        prompt = PAPER_ANALYSIS_PROMPT.format(paper_content=content)
        
        full_response = ""
        try:
            for chunk in self.llm_service.stream_chat(prompt):
                full_response += chunk
                yield {"stage": "analyzing", "chunk": chunk}
        except Exception as e:
            yield {"stage": "error", "message": f"AI 分析失败: {str(e)}"}
            return
        
        # ---- 阶段4: 完成 ----
        total_time = time.time() - start_time
        doc_info["processing_time"] = round(total_time, 1)
        
        # 更新 coordinator 状态
        self.current_state = {
            "document_id": doc_id,
            "parsed_doc": parsed_doc,
            "summary": full_response,
            "structure_info": "",
            "keywords": "",
            "current_stage": "summarized",
        }
        
        # 设置 QA Agent 上下文
        self.qa_agent.set_document_context(
            doc_id=doc_id,
            paper_title=parsed_doc.title or "",
            paper_summary=full_response[:500],
        )
        
        yield {
            "stage": "done",
            "message": "分析完成",
            "document_info": doc_info,
            "analysis": full_response,
            "total_time": round(total_time, 1),
        }
    
    def get_current_document_info(self) -> Optional[Dict[str, Any]]:
        """获取当前文档信息"""
        if self.current_state and self.current_state.get("parsed_doc"):
            parsed_doc = self.current_state["parsed_doc"]
            return {
                "document_id": self.current_state.get("document_id"),
                "filename": parsed_doc.filename,
                "title": parsed_doc.title,
                "page_count": parsed_doc.page_count,
                "word_count": parsed_doc.word_count,
                "file_type": parsed_doc.file_type
            }
        return None
    
    def translate_stream(self, max_chunks: int = 50):
        """
        流式翻译论文全文
        
        Args:
            max_chunks: 最大翻译分块数（防止过长文档）
            
        Yields:
            str: 翻译后的文本片段
        """
        # 获取文档分块
        chunks = self.vector_store.get_all_chunks()
        
        if not chunks:
            yield "❌ 未找到文档内容，请先上传并分析论文。"
            return
        
        # 限制分块数量
        if len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
            yield f"⚠️ 论文较长，仅翻译前 {max_chunks} 个段落。\n\n"
        
        yield f"📝 开始翻译论文（共 {len(chunks)} 个段落）...\n\n"
        yield "---\n\n"
        
        # 逐段翻译
        for i, chunk in enumerate(chunks, 1):
            text = chunk.page_content.strip()
            if not text:
                continue
            
            # 跳过太短的内容（可能是页码、图注等）
            if len(text) < 20:
                continue
            
            yield f"### 段落 {i}\n\n"
            yield f"**原文：**\n> {text[:200]}{'...' if len(text) > 200 else ''}\n\n"
            yield f"**译文：**\n"
            
            # 使用统一的翻译 Prompt 模板
            prompt = TRANSLATE_PROMPT.format(text=text)
            
            try:
                for token in self.llm_service.stream_chat(
                    user_message=prompt,
                    system_prompt="你是专业的学术论文翻译专家。",
                    chat_history=[]  # 翻译不需要历史上下文
                ):
                    yield token
            except Exception as e:
                yield f"\n\n[翻译出错: {str(e)}]"
            
            yield "\n\n---\n\n"
        
        yield "\n✅ 翻译完成！"

    def generate_code_stream(
        self,
        user_request: str = "生成论文核心算法的完整实现代码",
        target_framework: str = "Python (PyTorch)",
    ):
        """
        流式生成论文代码复现
        
        Args:
            user_request: 用户对代码生成的具体需求
            target_framework: 目标框架/语言
            
        Yields:
            str: 生成的代码片段
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 1. 获取论文标题和摘要
        paper_title = ""
        paper_summary = ""
        if self.current_state:
            parsed_doc = self.current_state.get("parsed_doc")
            if parsed_doc:
                paper_title = parsed_doc.title or ""
            paper_summary = self.current_state.get("summary", "") or ""
        
        # 2. 从向量库中检索与代码生成相关的内容
        search_queries = [
            user_request,
            "algorithm method implementation model architecture",
            "experimental setup parameters hyperparameters",
            "training procedure loss function optimization",
        ]
        
        all_contexts = []
        seen_contents = set()
        
        for query in search_queries:
            try:
                results = self.vector_store.search(query, top_k=3)
                for doc in results:
                    content = doc.page_content.strip()
                    if content and content not in seen_contents:
                        seen_contents.add(content)
                        all_contexts.append(content)
            except Exception as e:
                logger.warning(f"向量检索失败: {e}")
        
        if not all_contexts:
            yield "❌ 未找到文档内容，请先上传并分析论文。"
            return
        
        # 3. 限制上下文长度（取最相关的前 8 个分块）
        paper_context = "\n\n---\n\n".join(all_contexts[:8])
        
        # 4. 构建 Prompt
        prompt = CODE_GENERATION_PROMPT.format(
            paper_title=paper_title or "未知标题",
            paper_summary=paper_summary[:1500] if paper_summary else "无摘要信息",
            paper_context=paper_context,
            user_request=user_request,
            target_framework=target_framework,
        )
        
        # 5. 流式生成
        try:
            for token in self.llm_service.stream_chat(
                user_message=prompt,
                system_prompt=CODE_GENERATION_SYSTEM_PROMPT,
                chat_history=[],
            ):
                yield token
        except Exception as e:
            yield f"\n\n[代码生成出错: {str(e)}]"

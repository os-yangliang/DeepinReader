# DeepinReader 项目技术总览与实现细节

## 1. 项目概述

`DeepinReader` 是一个面向学术论文阅读场景的智能系统，目标不是单纯对论文做摘要压缩，而是构建一条从文档解析、结构化理解、检索增强、智能问答到结果解释的完整链路。

系统当前已经形成一个可运行的研究原型，具备以下能力：

- 上传并解析 PDF / Word 论文文档
- 自动生成分析报告与关键词
- 围绕论文内容进行问答
- 将问答建立在 `claim / evidence / result` 等结构化对象上
- 提供问题路由、风险提示、推理路径、Proof Graph 等解释性输出
- 支持全文翻译、代码生成、搜索、多文档对比、历史记录等扩展能力

从定位上看，DeepinReader 兼具两种属性：

1. **工程系统属性**：前后端完整、交互可用、具备多页面工作流和状态持久化。
2. **研究原型属性**：尝试将论文阅读从“文本级摘要/聊天”推进到“结构化理解 + 证据驱动问答 + 可解释输出”。

---

## 2. 总体架构

项目整体采用“前端交互层 + FastAPI 服务层 + 多智能体协调层 + 文档/向量/结构化数据层”的分层架构。

### 2.1 架构分层

#### 2.1.1 前端交互层

位于 `frontend/src/`，基于：

- Vue 3
- Vite
- Tailwind CSS
- Axios
- WebSocket + SSE 双通道流式交互
- `vue-pdf-embed` 实现 PDF 阅读

前端负责：

- 文件上传与文档切换
- PDF 原文阅读
- 分析报告展示
- 聊天式问答交互
- 风险提示 / 推理路径 / Proof Graph 展示
- 标注、导出、主题切换、本地状态持久化

#### 2.1.2 API 服务层

位于根目录 `api.py`。

使用：

- FastAPI
- REST API
- Server-Sent Events（SSE）
- WebSocket 多路复用流式协议

负责：

- 文件上传与解析触发
- 分析、问答、翻译、代码生成等流式接口
- 历史记录、文档切换、导出等辅助接口
- 全局单例协调器和应用状态维护

#### 2.1.3 多智能体与编排层

主要位于 `agents/`，核心是 `PaperReaderCoordinator`。

负责：

- 协调解析、摘要、问答等子智能体
- 管理 LangGraph 工作流
- 在不同能力模块之间传递上下文

#### 2.1.4 数据与知识层

主要位于 `services/`：

- 文档解析：`DocumentParser`
- 向量检索：`VectorStoreService`
- 结构化对象建模：`PaperProfile`、`Claim`、`Evidence`、`ResultItem`
- 图结构检索：`SubgraphRetriever`
- 历史记录持久化：`HistoryStoreService`

---

## 3. 项目目录结构与职责划分

## 3.1 根目录关键文件

### `api.py`

FastAPI 主入口，承载：

- 应用生命周期管理
- CORS 与静态资源挂载
- 全局单例协调器与历史记录服务实例
- 请求/响应模型定义
- REST 与流式接口路由

### `config.py`

统一配置中心，读取 `.env` 环境变量，包括：

- DeepSeek API 配置
- LLM 参数
- ChromaDB 持久化目录
- Embedding 模型名
- 文档切分参数
- CORS 允许来源

### `requirements.txt`

后端依赖管理文件。

### `start.bat`

Windows 一键启动脚本，负责同时启动：

- `uvicorn api:app --port 8001`
- `frontend` 下的 `npm run dev`

---

## 3.2 `agents/` 多智能体模块

### `coordinator.py`

系统的编排核心。定义：

- `PaperReaderState`：LangGraph 中的状态结构
- `ProcessingResult`：文档处理输出结构
- `PaperReaderCoordinator`：顶层协调器

功能：

- 初始化 `ParserAgent`、`SummarizerAgent`、`QAAgent`
- 构建 `parse -> summarize -> end` 的流程图
- 支持文档解析与摘要流程
- 在处理成功后将上下文同步给 QA 模块

### `parser_agent.py`

负责文档解析和知识结构构建。内部流程：

1. 调用 `DocumentParser` 解析原始论文文本
2. 生成文档唯一 ID
3. 使用 `SectionParser` 划分章节
4. 调用 `ScholarlyObjectExtractor` 抽取主张、证据、实验、结果
5. 使用 `PaperGraphBuilder` 构建 `PaperProfile`
6. 将 chunk 写入向量库
7. 将结构化对象写入 `paper_profiles/*.json`
8. 将结构化对象再次索引进向量库

### `summarizer_agent.py`

负责生成长分析报告和关键词。

功能细节：

- 使用 `PAPER_SUMMARY_PROMPT` 生成结构化分析报告
- 使用 `KEYWORD_EXTRACTION_PROMPT` 提取关键词
- 对超长文本做智能截断：
  - 保留前段（摘要、引言、方法）
  - 保留后段（结论）
  - 中间部分采样
- 同时支持同步、异步和流式生成

### `qa_agent.py`

负责论文问答，是系统最有研究特色的模块之一。

内部逻辑：

1. `QuestionRouterAgent` 判断问题类别
2. 根据路由类型构建一个简单 plan
3. 从 `PaperProfile` 和向量库中构建 `EvidenceBundle`
4. 使用 `SubgraphRetriever` 补全图结构邻域信息
5. 用 `CLAIM_EVIDENCE_ANSWER_PROMPT` 生成答案
6. 用 `VerifierAgent` 对答案做支撑度验证
7. 输出：
  - answer
  - route_type
  - warnings
  - reasoning_trace
  - reasoning_paths
  - claim_nodes / evidence_nodes / result_nodes
  - confidence

### `question_router_agent.py`

问答路由模块，采用启发式规则而不是复杂分类模型。

当前支持的路由类型：

- `structure`
- `method`
- `evidence`
- `result`
- `critical`
- `general`

路由依据是问题中的中英文关键词，如：

- “结构 / section / outline” → `STRUCTURE`
- “为什么 / 依据 / support / evidence” → `EVIDENCE`
- “方法 / 模型 / approach” → `METHOD`
- “结果 / 指标 / 数据集” → `RESULT`
- “局限 / 缺点 / weakness” → `CRITICAL`

### `verifier_agent.py`

回答验证模块，用启发式规则计算回答的“支撑强度”。

输入：

- 问题文本
- 生成答案
- `EvidenceBundle`
- 推理路径列表

输出：

- `confidence`
- `supported_points`
- `unsupported_points`
- `warnings`

当前 `confidence` 计算方式是规则累加而非概率模型：

- 基础分 `0.32`
- 命中原文片段、claim、evidence、result、reasoning path 会加分
- 缺失信息、回答过长、缺少证据支撑会扣分
- 最终裁剪到 `[0.18, 0.96]`

这说明当前“置信度”本质上更接近“支撑强度评分”，不是统计学意义上的正确概率。

---

## 3.3 `services/` 核心服务层

### `document_parser.py`

负责原始文档解析。

支持格式：

- PDF（`PyMuPDF / fitz`）
- Word（`python-docx`）

主要职责：

- 检查文件是否存在
- 检查文件大小是否超过 `MAX_FILE_SIZE_MB`
- 按扩展名分发不同解析逻辑
- 对 PDF 提取逐页文本，并加入页码分隔标记
- 自动生成文档标题
- 按 `chunk_size` / `chunk_overlap` 分块
- 支持从字节流直接解析上传文件，避免额外临时 I/O

### `vector_store.py`

混合检索核心，基于：

- ChromaDB 向量存储
- HuggingFaceEmbeddings
- BM25Retriever
- 自定义 `SimpleEnsembleRetriever`

关键技术点：

#### 向量模型

- 使用 `HuggingFaceEmbeddings`
- 默认模型来自配置 `EMBEDDING_MODEL`
- 在 CPU 上运行，并开启 `normalize_embeddings`

#### 多文档集合设计

每篇文档创建独立集合：

- 逻辑集合名：`{COLLECTION_NAME}_{document_id}`

这样可以支持多文档切换而不混淆索引。

#### 混合检索

系统没有只做向量检索，而是把：

- dense retrieval（向量相似度）
- sparse retrieval（BM25）

通过 `SimpleEnsembleRetriever` 组合。

它使用的是简化版的 **RRF（Reciprocal Rank Fusion）**：

- 对每个 retriever 返回结果按 rank 计分
- 根据权重融合多个结果列表
- 最终排序输出

这使系统在学术论文问答中同时保留：

- 语义召回能力
- 关键词匹配能力

### `llm_service.py`

DeepSeek API 统一封装层。

基于：

- `langchain_openai.ChatOpenAI`

能力：

- `chat`：异步对话
- `chat_sync`：同步对话
- `generate_with_prompt`：模板化生成
- `generate_with_prompt_async`：异步模板生成
- `stream_chat`：流式生成

它统一封装了：

- 系统提示词
- 聊天历史拼接
- 模型配置（temperature、max_tokens）

### `paper_schema.py`

项目最核心的数据建模文件之一。

定义了系统中的结构化论文对象：

- `PaperSection`
- `Claim`
- `Evidence`
- `Experiment`
- `ResultItem`
- `PaperProfile`
- `EvidenceBundle`
- `VerificationReport`

这是 DeepinReader 从“文本系统”走向“结构化论文理解系统”的关键基础。

### `object_indexer.py`

负责 `PaperProfile` 的持久化与再索引。

职责：

1. 将 `PaperProfile` 保存成 JSON 文件
2. 从磁盘读取 profile
3. 将 `section / claim / evidence / result` 再次转成文本写入向量库

这样问答阶段可以做两类检索：

- 原始 chunk 检索
- 结构化对象检索

### `subgraph_retriever.py`

面向图结构的邻域检索器。

输入：

- `PaperProfile`
- `QuestionRoute`

流程：

1. 根据问题路由选 anchor 节点
2. 遍历 `graph_edges`
3. 做最多 `max_hops=2` 的 BFS
4. 生成推理路径 `paths`
5. 返回访问过的节点集合 `visited_ids`
6. 再把这些节点回填进 `EvidenceBundle`

作用：

- 不仅检索“最相似文本”
- 还补充“与当前问题相关的结构化邻域”

这正是项目“claim-evidence-result 驱动问答”的重要技术点。

### 其他服务

#### `section_parser.py`

负责从原始文本中切分章节。

#### `scholarly_object_extractor.py`

负责抽取 scholarly objects，如：

- 主张
- 证据
- 实验
- 结果

#### `paper_graph_builder.py`

将章节与对象之间的关系构造成图结构。

#### `history_store.py`

基于 ChromaDB 保存：

- 分析历史
- 聊天历史

#### `text_utils.py`

公共文本工具，主要负责 chunk splitting。

#### `tools.py`

封装联网搜索等辅助能力。

---

## 4. 后端 API 与运行机制

## 4.1 FastAPI 应用初始化

`api.py` 中初始化了：

- FastAPI 应用实例
- CORS 中间件
- 静态上传目录挂载 `/api/uploads`
- lifespan 生命周期函数

生命周期中会自动清理超过 7 天的上传文件。

## 4.2 应用状态管理

`AppState` 是当前的全局运行时状态对象，维护：

- 当前文档 ID
- 当前文档是否已加载
- 当前摘要与结构信息
- 当前历史记录 ID
- 多文档列表

它支持：

- 添加文档
- 切换文档
- 删除文档
- 保存摘要
- 清空状态

这使得系统具备了“单用户、多文档”的内存态能力。

## 4.3 单例服务

为了降低初始化成本，系统维护以下单例：

- `PaperReaderCoordinator`
- `HistoryStoreService`

其中 `get_coordinator(require_llm=True)` 具备一个“延迟升级”机制：

- 初次可只加载解析/索引能力
- 当需要 LLM 时再升级为完整模式

这有助于减少首次启动或部分接口调用时的资源开销。

## 4.4 通信方式

系统同时支持三种通信模式：

### REST API

用于：

- 上传文档
- 获取历史
- 切换文档
- 导出报告
- 获取当前信息

### SSE

用于：

- 流式分析
- 流式翻译
- 流式对比

### WebSocket

用于更统一的多路复用流式任务：

- 问答
- 翻译
- 代码生成
- 对比
- 课题组讨论等

前端优先使用 WebSocket，如不可用再退回 SSE。

---

## 5. 前端架构与页面设计

## 5.1 前端技术栈

位于 `frontend/`。

使用：

- Vue 3 Composition API
- Vite
- Tailwind CSS
- Axios
- WebSocket
- `vue-pdf-embed`
- Lucide 图标
- Mermaid / Highlight.js / Marked 等可视化与渲染库

## 5.2 全局状态管理

`frontend/src/store.js` 维护：

- `documentInfo`
- `pdfUrl`
- `analysisResult`
- `documents`
- `theme`
- `pendingQuestion`

特性：

- 使用 `reactive` 管理共享状态
- 自动从 `localStorage` 恢复 `paperreader_state`
- 保存主题模式到 `paperreader_theme`
- 保存已加载的多文档列表
- 支持从分析页标注跳转到问答页时传递问题

## 5.3 前端 API 层

`frontend/src/api/index.js` 封装了统一访问层。

技术细节：

- 使用 Axios 处理普通接口
- 使用 `fetch + ReadableStream` 处理 SSE
- 使用自定义 `wsRequest` 处理 WebSocket
- 封装 `withFallback` 实现 WS 失败自动降级到 SSE

这说明前端不仅实现了实时流式交互，还考虑了协议降级与兼容性。

---

## 5.4 核心页面

### `Home.vue`

首页 Hero 区域，负责：

- 项目名称展示
- 文件拖拽上传
- 上传状态显示
- 成功后自动跳转分析页
- 展示功能与工作流程概览

### `Analyze.vue`

分析页是系统最重要的页面之一。

主要布局：

- 左侧：PDF 阅读器
- 右侧：分析报告面板
- 可选右侧标注栏

核心功能：

- 上传论文
- 启动流式分析
- 实时进度条
- Markdown 渲染分析报告
- 导出 Markdown / Word
- 文本高亮标注
- 标注导出与标注联动问答

### `Chat.vue`

问答页是项目研究特色的主要展示页面。

布局：

- 左侧 PDF 阅读区
- 右侧聊天区

特性：

- WebSocket 流式问答
- 助手回答附带：
  - route type
  - confidence
  - warnings
  - reasoning trace
  - proof graph
  - source chunks
- 支持清空对话与建议问题
- 支持从分析页标注一键带问题跳转

### 其他页面

项目还包含：

- `Translate.vue`：全文翻译
- `MindMap.vue`：思维导图
- `CodeGen.vue`：代码生成
- `Search.vue`：联网搜索
- `Compare.vue`：多论文对比
- `History.vue`：历史记录
- `ResearchLab.vue`：课题组讨论/扩展研究型交互

这些页面说明 DeepinReader 已经不是单功能 Demo，而是围绕论文阅读构建的完整工作台。

---

## 6. 问答链路的技术细节

DeepinReader 最值得强调的技术路径，就是它的问答链路。

## 6.1 Step 1：问题路由

用户提问后，首先交给 `QuestionRouterAgent`。

它的作用不是回答问题，而是识别：

- 这是结构问题吗？
- 方法问题吗？
- 证据问题吗？
- 结果问题吗？
- 批判性问题吗？

这一步决定了后续检索重点。

## 6.2 Step 2：构建检索计划

`QAAgent._build_plan()` 根据路由生成一组简单 plan，如：

- 定位主张
- 检索证据与结果
- 验证回答是否有支撑

虽然这个 plan 目前不直接驱动外部执行器，但会进入 reasoning trace，用于增强输出可解释性。

## 6.3 Step 3：构建 EvidenceBundle

`_retrieve_bundle()` 会从两个来源装配 `EvidenceBundle`：

### 来源 A：`PaperProfile`

按路由类型直接选：

- relevant sections
- target claims
- evidences
- results

### 来源 B：向量检索结果

调用 `vector_store.search(question, top_k=6)`，再根据 metadata 判断对象类型：

- claim
- evidence
- result
- section
- 普通 chunk

最终 bundle 中包含：

- target_claims
- evidences
- results
- sections
- source_chunks
- missing_information

## 6.4 Step 4：图结构扩展

调用 `SubgraphRetriever.retrieve()`：

- 选 anchor 节点
- 做图遍历
- 得到 reasoning paths
- 回填邻域节点到 bundle

这一步让问答不只停留在“query → top-k chunk”，而是加入了“结构邻接扩展”。

## 6.5 Step 5：答案生成

`_solve()` 使用：

- 当前论文标题
- 当前摘要
- `EvidenceBundle` 的 JSON 表示
- `CLAIM_EVIDENCE_ANSWER_PROMPT`

让 LLM 在结构化证据语境下生成回答。

## 6.6 Step 6：答案验证

`VerifierAgent.verify()` 对生成答案做规则验证：

- 有没有原文 chunk
- 有没有 claim 节点
- 有没有 evidence 节点
- 有没有 result 节点
- 有没有 reasoning path
- 有没有缺失信息与风险项

输出最终：

- 支撑强度分（当前 UI 里叫置信度）
- warnings
- supported / unsupported points

## 6.7 Step 7：前端解释展示

问答页展示的附加信息包括：

- 问题路由标签
- 置信度 / 支撑强度
- 风险提示折叠面板
- 推理路径折叠面板
- Proof Graph
- Source chunks

这使系统与普通聊天机器人形成明显区别：它不只给答案，还给“答案背后的结构与线索”。

---

## 7. 分析链路的技术细节

分析链路主要由：

- `ParserAgent`
- `SummarizerAgent`
- `Analyze.vue`

共同组成。

### 7.1 文档上传

前端选择文件后：

1. 先在前端生成 blob URL 供 PDF 预览
2. 调用后端上传接口
3. 后端解析结构
4. 返回文档信息与永久 URL

### 7.2 文档结构化解析

后端做：

- 原始文本抽取
- chunk 切分
- section 解析
- scholarly object 抽取
- paper graph 构建
- 向量索引写入
- profile JSON 持久化

### 7.3 报告生成

当用户点击“开始智能分析”：

- 前端通过流式接口发起分析
- 后端调用 `SummarizerAgent.generate_summary_stream()`
- LLM 按 prompt 逐步输出分析报告
- 前端实时渲染 Markdown

### 7.4 结果导出

分析页支持：

- 复制 Markdown
- 下载 Markdown
- 导出 Word

并允许用户在 PDF 中做文本高亮与标注。

---

## 8. 数据流与状态流

## 8.1 文档状态流

上传文档后，状态流大致为：

1. 前端上传文件
2. 后端解析并生成 `document_id`
3. 向量库为该文档创建独立 collection
4. 前端把 `documentInfo / pdfUrl / documents[]` 写入 store
5. 切换页面后，其他模块从全局 store 中读取当前文档上下文

## 8.2 聊天状态流

1. 用户提问
2. 前端创建 assistant 占位消息
3. 通过 WS 发起 `chat` 请求
4. 后端流式返回 chunk
5. 最终 `done` 消息附带 route、warnings、paths、confidence 等元信息
6. 前端回填消息对象并渲染额外解释块

## 8.3 本地持久化

前端会把这些信息写入 `localStorage`：

- 当前文档信息
- PDF URL（非 blob）
- 分析结果
- 文档列表
- 当前主题

这使用户刷新页面后仍能恢复部分上下文。

---

## 9. 关键技术设计选择

## 9.1 为什么采用多阶段链路而不是一步到位生成

系统没有选择“把论文内容丢给大模型直接回答”的方式，而是拆成：

- 解析
- 建模
- 检索
- 生成
- 验证

原因：

- 降低黑盒性
- 提升答案的支撑性
- 让结果可解释
- 为后续研究扩展留出模块化空间

## 9.2 为什么使用结构化对象而不是只做 chunk-level RAG

只做 chunk-level RAG 的问题在于：

- 检索粒度粗
- 回答依据隐式
- 难反映论文内部逻辑关系

结构化对象让系统能直接检索：

- claim
- evidence
- result
- section

从而更接近“围绕论文知识结构作答”。

## 9.3 为什么同时保留向量检索与图检索

向量检索擅长：

- 语义相似召回
- 面向用户问题的自然表达检索

图检索擅长：

- 顺着 claim → evidence → result 关系扩展
- 提供 reasoning path
- 提升结构一致性

两者结合后，系统既有召回能力，也有结构支撑能力。

---

## 10. 当前实现的优势与不足

## 10.1 优势

### 工程层面

- 全栈闭环已经打通
- 支持多文档与多页面工作流
- 前端交互相对成熟
- 流式体验较完整

### 方法层面

- 引入结构化论文表示
- 引入 claim-evidence 驱动问答
- 引入回答后验证
- 提供风险提示与推理路径

### 展示层面

- 适合做 Demo
- 适合做学术汇报
- 比“普通论文聊天工具”更能体现差异化

## 10.2 当前不足

### 方法层面

- `QuestionRouterAgent` 仍主要依赖关键词规则
- `VerifierAgent` 的 confidence 是启发式分数，不是统计置信概率
- `ScholarlyObjectExtractor` 的抽取质量高度依赖 LLM
- 缺少系统化 benchmark 和量化评测

### 工程层面

- 前端仍存在部分冗余状态与历史遗留逻辑
- 混合检索器是简化实现，不是完整生产级检索栈
- 大文档 / 多文档场景下 BM25 重建可能有性能开销
- 一些模块命名与品牌重命名尚未彻底统一

---

## 11. 学术价值与研究潜力

从研究角度，DeepinReader 的价值主要在于以下几点：

### 11.1 研究问题层面

它尝试回答一个有意义的问题：

> 如何让论文阅读系统从“文本压缩和自由聊天”，走向“结构化理解、证据驱动问答与可解释输出”？

### 11.2 方法层面

系统已经形成一个清晰的方法链：

- structured representation
- route-aware retrieval
- claim-evidence grounding
- answer verification

### 11.3 扩展潜力

未来可以继续研究：

- 更高质量的结构化对象抽取
- 基于学习的 verifier
- 更可靠的路由器
- 跨论文 claim-evidence 对齐与比较
- benchmark 与用户研究

---

## 12. 总结

DeepinReader 当前不是一个简单的论文摘要工具，而是一个围绕学术论文理解构建的智能阅读系统原型。

它的核心特色在于：

- 将论文表示为显式结构化对象
- 将问答建立在 claim-evidence-result 支撑框架上
- 通过 verifier、风险提示和推理路径提高回答解释性
- 用前后端完整系统形态把上述研究思路落地成可演示原型

如果从学术会议汇报的角度总结，可以概括为：

> DeepinReader 试图推动论文阅读系统从“文本级摘要与检索”走向“结构化论文理解与证据驱动问答”。


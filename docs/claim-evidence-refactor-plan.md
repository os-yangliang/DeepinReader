# PaperReader 重构实施方案：结构化解析 + Claim-Evidence QA

## 1. 目标

本次重构聚焦两个核心创新方向：

1. 面向学术论文的结构化解析与对象建模框架
2. Claim-Evidence 驱动的 Agentic QA 机制

目标是将当前以 `chunk + 向量检索 + LLM` 为主的问答链路，升级为：

`文档解析 -> 章节识别 -> 学术对象抽取 -> 研究对象图谱 -> 多粒度检索 -> 证据聚合 -> 答案验证`

---

## 2. 当前代码库现状

### 已有能力

- `services/document_parser.py`：解析 PDF / Word，提取全文与 chunk
- `agents/parser_agent.py`：解析文档，做结构分析，建立向量索引
- `services/vector_store.py`：Chroma + BM25 混合检索
- `agents/qa_agent.py`：轻量 Plan-and-Solve QA
- `agents/coordinator.py`：工作流编排
- `api.py`：REST / SSE / WebSocket API

### 当前瓶颈

- 文档结构仍然主要是线性文本和 chunk
- QA 缺少明确的问题路由与多粒度检索
- 没有显式的 `Claim / Evidence / Experiment / Result` 中间对象
- 没有答案验证与可解释的推理输出

---

## 3. 重构原则

1. 尽量兼容现有 API 和前端交互
2. 优先增加中间层，不一次性推翻原有逻辑
3. 结构化对象优先服务 QA，不做过度设计
4. 先用内存 + Chroma 元数据实现，不强依赖图数据库

---

## 4. 新增模块设计

### 4.1 Schema 层

新增文件：`services/paper_schema.py`

定义核心对象：

- `SectionType`
- `ClaimType`
- `PaperSection`
- `Claim`
- `Evidence`
- `Experiment`
- `ResultItem`
- `PaperProfile`
- `QuestionRoute`
- `EvidenceBundle`
- `VerificationReport`

作用：

- 为解析、索引、QA、验证提供统一数据结构

---

### 4.2 章节解析层

新增文件：`services/section_parser.py`

职责：

- 从全文中识别章节标题与层级
- 生成 section tree 的扁平表示
- 将 chunk 与 section 建立映射
- 标准化 section type

实现策略：

- 先用规则识别：编号标题、常见章节名
- 若未识别到足够结构，回退为单一 section

输出：

- `List[PaperSection]`

---

### 4.3 学术对象抽取层

新增文件：`services/scholarly_object_extractor.py`

职责：

- 基于 section type，从章节文本中抽取：
  - `Claim`
  - `Evidence`
  - `Experiment`
  - `ResultItem`
  - contribution / limitation 摘要

实现策略：

- 方法章节：抽取方法描述、关键 claim
- 实验/结果章节：抽取 experiment/result/evidence
- 结论章节：抽取 contribution / limitation claim
- 使用 LLM 输出 JSON；失败时回退为空对象，不阻断主流程

---

### 4.4 研究对象图谱构建层

新增文件：`services/paper_graph_builder.py`

职责：

- 将 section / claim / evidence / experiment / result 组装为 `PaperProfile`
- 建立最小关系边：
  - `claim -> evidence`
  - `evidence -> result`
  - `result -> experiment`
- 生成简易 adjacency map，用于 graph-aware retrieval

---

### 4.5 多粒度索引层

新增文件：`services/object_indexer.py`

职责：

- 基于 `PaperProfile` 构建对象级索引
- 写入当前文档向量集合，区分 object_type 元数据
- 支持：
  - `section` 检索
  - `claim` 检索
  - `evidence` 检索
  - `result` 检索

说明：

- 继续复用 `VectorStoreService`
- 在 metadata 中加入：
  - `object_type`
  - `section_id`
  - `claim_id`
  - `evidence_id`
  - `result_id`

---

### 4.6 QA 重构层

新增文件：

- `agents/question_router_agent.py`
- `agents/verifier_agent.py`

重构文件：

- `agents/qa_agent.py`

职责拆分：

#### `QuestionRouterAgent`

- 判断问题类型：
  - `structure`
  - `method`
  - `evidence`
  - `result`
  - `critical`
  - `general`
- 生成检索策略建议

#### `QAAgent`

- 编排：route -> plan -> retrieve -> aggregate -> answer -> verify
- 引入多粒度检索
- 将回答建立在 `EvidenceBundle` 上
- 输出：答案 + 引用证据 + 路由类型 + 置信度 + 警告

#### `VerifierAgent`

- 检查回答是否被 evidence bundle 支持
- 输出：
  - supported_points
  - unsupported_points
  - confidence
  - warnings

---

## 5. 现有文件的具体改造建议

### 5.1 `services/document_parser.py`

保留现有文本解析逻辑，不做大改。

改造建议：

- 继续负责底层文档读取
- 不承担结构化语义抽取职责

---

### 5.2 `agents/parser_agent.py`

重点改造。

新增职责：

1. 调用 `SectionParser` 识别 section
2. 调用 `ScholarlyObjectExtractor` 抽取学术对象
3. 调用 `PaperGraphBuilder` 组装 `PaperProfile`
4. 调用 `ObjectIndexer` 将 section / claim / evidence / result 入索引
5. 将 `paper_profile` 挂到 `ParsedDocument`

建议修改：

- `ParserResult` 增加 `paper_profile`
- `_analyze_structure` 可改为优先使用结构化 section 生成文本摘要
- `_store_document` 升级为：
  - 原始 chunk 入库
  - 结构化对象入库

---

### 5.3 `services/vector_store.py`

尽量最小改动。

建议增加能力：

- 支持 metadata 过滤检索（按 object_type）
- 增加一个统一的 `search(query, object_types=None, k=...)` 接口

若当前版本不方便深度改造，也可以先通过：

- 统一召回 top-k
- 然后在 Python 侧按 metadata 过滤

---

### 5.4 `agents/qa_agent.py`

这是核心重构点。

建议从“轻量 Plan-and-Solve”升级为：

1. `set_document_context(...)`
  - 除加载 collection 外，还加载 `PaperProfile`
2. `ask(question)`
  - route question
  - build plan
  - retrieve evidence bundle
  - synthesize answer
  - verify answer
  - return structured result
3. `ask_stream(question)`
  - 流式输出中增加阶段性提示：
    - 正在识别问题类型
    - 正在检索关键主张与证据
    - 正在验证答案可靠性
4. `QAResult` 增加字段：
  - `route_type`
  - `evidence_summary`
  - `confidence`
  - `warnings`
  - `reasoning_trace`

---

### 5.5 `agents/coordinator.py`

改造点：

- 在文档处理后，把 `paper_profile` 注入 QA agent
- `ask_question` / `ask_question_stream` 不变，但内部自动走新 QA 逻辑
- 在 `parse_and_index` 和 `process_document` 两条路径中都构建 `paper_profile`

---

### 5.6 `api.py`

保持接口尽量兼容。

建议改造：

- `/api/chat` 和 WS `chat` 返回更丰富的字段时，优先兼容现有 `answer/source_chunks`
- 可以额外补充：
  - `confidence`
  - `route_type`
  - `warnings`
  - `evidence_summary`

WS 流式端优先保持纯文本流，最终 `done` 事件可携带结构化摘要。

---

### 5.7 `prompts/templates.py`

新增 prompt：

- `SECTION_CLASSIFICATION_PROMPT`
- `SCHOLARLY_OBJECT_EXTRACTION_PROMPT`
- `QUESTION_ROUTING_PROMPT`
- `CLAIM_EVIDENCE_ANSWER_PROMPT`
- `ANSWER_VERIFICATION_PROMPT`

原则：

- 每个 prompt 只做一件事
- 优先 JSON 输出

---

## 6. 数据持久化建议

### 短期

- `PaperProfile` 保存在内存缓存中
- 同时存到 `uploads/` 或 `chroma_db/` 附近的 JSON 文件
- 文件命名：`paper_profiles/{doc_id}.json`

### 中期

- 可扩展到专门的 profile store

本轮重构建议先采用 JSON 文件持久化，成本最低。

---

## 7. QA 执行链路设计

### 输入

用户问题

### Step 1：Question Routing

输出：

- `route_type`
- `intent`
- `retrieval_targets`

### Step 2：Planning

按 route 生成简化计划：

- method 问题：section + claim
- evidence 问题：claim + evidence + result
- critical 问题：claim + evidence + limitation

### Step 3：Multi-granular Retrieval

从这些粒度检索：

- section
- chunk
- claim
- evidence
- result

### Step 4：Evidence Aggregation

构建 `EvidenceBundle`：

- target claims
- supporting evidences
- related results
- related sections
- missing information

### Step 5：Answer Synthesis

基于 evidence bundle 生成 grounded answer

### Step 6：Verification

输出：

- confidence
- warnings
- unsupported points

### Step 7：Response

保留旧字段：

- `answer`
- `source_chunks`

新增字段：

- `route_type`
- `confidence`
- `warnings`
- `evidence_summary`
- `reasoning_trace`

---

## 8. 分阶段开发顺序

### Phase 1：结构化解析底座

- 新增 schema
- 新增 section parser
- 新增 paper profile 构建
- parser agent 写入 profile JSON

### Phase 2：对象抽取与索引

- 抽 claim/evidence/result
- object indexing
- QA 加载 profile

### Phase 3：Agentic QA

- question router
- evidence bundle retrieval
- verifier
- 兼容现有 API 输出

---

## 9. 本轮实际落地范围建议

为了控制风险，建议本轮代码重构按“最小可用增强”实施：

### 必做

- schema
- section parser
- paper profile 构建
- claim/evidence/result 抽取初版
- profile JSON 持久化
- question router
- QA evidence bundle + verifier

### 暂不做

- 真正的图数据库
- 前端复杂图谱可视化
- 多论文对齐 compare 重构

---

## 10. 验收标准

### 结构化解析成功标准

- 上传文档后，能够得到 section 列表
- 能够抽取至少部分 claim / evidence / result
- 生成 `paper_profile.json`

### QA 成功标准

- 回答能区分问题类型
- 回答带至少 1-3 条证据摘要
- 返回 confidence 和 warnings
- 当证据不足时明确提示，而不是强行编造

---

## 11. 预期收益

### 效果层面

- 方法类问题更稳
- “为什么有效”“证据是什么”类问题明显变强
- 对幻觉更可控

### 技术表达层面

- 从基础 RAG 升级为 research-object-grounded QA
- 具备 claim-evidence-verification 的闭环
- 更适合包装为研究型系统亮点


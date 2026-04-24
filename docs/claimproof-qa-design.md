# PaperReader QA 升级方案：ClaimProof QA / 论文结构知识图谱问答

## 1. 目标定位

本方案不是继续增强传统 `RAG + Prompt` 问答，而是将 QA 升级为一个围绕论文主张、证据、实验、反事实与局限进行推理的研究型系统。

目标能力定义为：

`Question -> Claim Graph Routing -> Subgraph Retrieval -> Proof Assembly -> Counterfactual / Critical Reasoning -> Verification -> Explainable Answer`

系统最终不只是“回答问题”，而是：

1. 识别问题对应的论文主张或论证单元
2. 组装支撑链（claim -> evidence -> result -> experiment）
3. 在必要时引入 limitation / contradiction / counterfactual 条件
4. 输出带证据链、风险项和不确定性分解的答案

建议将该能力命名为：`ClaimProof QA`

---

## 2. 为什么这条路线更有创新性与技术壁垒

相比常规论文 QA，本方案的差异不在“更长的回答”或“更复杂的 prompt”，而在于：

1. **从文本检索转向论证图谱推理**
   - 普通 QA 的单位是 chunk
   - ClaimProof QA 的单位是 claim / evidence / result / limitation / assumption / path

2. **从回答生成转向 proof assembly**
   - 系统输出的是答案 + 支撑链 + 缺口 + 风险
   - 每个答案都对应一个最小论证子图

3. **从静态问答转向反事实问答**
   - 能回答“去掉某模块后是否仍成立”“没有该实验结论是否成立”“局限性如何削弱结论”等问题

4. **从单一 confidence 转向 uncertainty decomposition**
   - 输出不仅有整体置信度，还包括证据充分性、图谱完整性、矛盾风险、泛化风险

这四点共同构成了真正的技术壁垒，而不是停留在 UI 包装或 prompt engineering。

---

## 3. 当前代码库现状与升级空间

### 3.1 已有基础

当前代码库已经具备构建 ClaimProof QA 的雏形：

- `services/paper_schema.py`：已有 `PaperProfile / Claim / Evidence / ResultItem / Experiment / graph`
- `services/section_parser.py`：已有章节解析能力
- `services/scholarly_object_extractor.py`：已有结构化对象抽取雏形
- `services/paper_graph_builder.py`：已有轻量图谱关系构建
- `agents/qa_agent.py`：已有 route-aware + evidence bundle 机制
- `agents/question_router_agent.py`：已有问题路由框架
- `agents/verifier_agent.py`：已有轻量答案校验框架
- `frontend/src/views/Chat.vue`：已有 route / confidence / warnings / reasoning / source chunk 展示

### 3.2 当前瓶颈

但当前系统距离“论文结构知识图谱问答”仍有明显差距：

1. 图谱节点不稳定
   - 结构化抽取经常为空
   - `claims / evidences / results / experiments` 数量不足

2. 图谱关系仍偏占位
   - `claim -> evidence -> result` 的 linking 还不是基于强语义或 provenance

3. QA 仍然以混合检索为主
   - 实际回答仍强依赖 chunk fallback
   - 还没有真正的 subgraph retrieval 和 path reasoning

4. verifier 仍偏规则型
   - 尚未做到 graph-grounded verification

5. 前端解释层还不是“答案子图”
   - 当前展示的是 route / warnings / evidence summary / source chunks
   - 还不是图谱级证据链展示

因此，下一步的设计重点不应是继续堆 prompt，而应补齐下面三层。

---

## 4. ClaimProof QA 的三层核心升级

### 4.1 第一层：Argument Graph Construction（论证图谱构建层）

这是最关键的一层。它决定系统是否真的拥有“图谱可推理对象”，而不是一组名字很好听但实际为空的结构体。

#### 4.1.1 设计目标

把论文转换为一个带 provenance 的论证图谱（argument graph），而不仅是 section / chunk 的集合。

#### 4.1.2 节点类型扩展

建议将当前 schema 从：

- `Section`
- `Claim`
- `Evidence`
- `Experiment`
- `Result`
- `Limitation`

扩展为：

- `Hypothesis`
- `MethodStep`
- `Assumption`
- `Variable`
- `Metric`
- `Dataset`
- `FailureMode`
- `CounterEvidence`
- `AblationCondition`

这些节点不是为了炫技，而是为了支持：

- 方法解释型问题
- 实验对照型问题
- 反事实型问题
- 审稿式批判型问题

#### 4.1.3 关系类型正式化

建议把当前简单 graph 关系升级为 typed edges，例如：

- `section contains claim`
- `claim supported_by evidence`
- `evidence derived_from experiment`
- `result supports claim`
- `result measured_by metric`
- `experiment uses dataset`
- `claim limited_by limitation`
- `claim contradicted_by counter_evidence`
- `claim depends_on assumption`
- `ablation_condition weakens claim`

关系类型越清晰，后续 QA 的 reasoning path 就越稳定。

#### 4.1.4 provenance 设计

每个节点与边都应保留回溯能力：

- `section_id`
- `page_span`
- `char_span`
- `source_text`
- `source_chunk_ids`
- `confidence`

这是图谱 QA 与“普通 LLM 编故事”之间的分水岭。

#### 4.1.5 实现策略

建议将抽取过程拆成多阶段，而不是让一次 prompt 输出所有对象：

1. `Section Parsing`
2. `Claim Extraction`
3. `Evidence / Result Extraction`
4. `Experiment / Dataset / Metric Extraction`
5. `Limitation / Failure Mode Extraction`
6. `Linking & Validation`

每个阶段：

- 单独 schema
- 单独 JSON 校验
- 单独重试策略
- 失败可降级，不阻断整体上传

#### 4.1.6 对应代码切入点

建议主要落在：

- `services/paper_schema.py`
- `services/scholarly_object_extractor.py`
- `services/paper_graph_builder.py`
- `agents/parser_agent.py`
- `services/object_indexer.py`

---

### 4.2 第二层：Subgraph Retrieval & Proof Reasoning（子图检索与证明式推理层）

当第一层把“图”建起来后，第二层要让 QA 真正“按图工作”。

#### 4.2.1 设计目标

将当前 QA 从：

`route -> retrieve docs -> answer`

升级为：

`route -> locate target claim(s) -> expand subgraph -> assemble proof -> verify answer`

#### 4.2.2 引入 Question-to-Proof Planning

问题不直接进入检索，而是先拆成证明任务。

例如：

问题：`为什么 MUG 比 MAD 更可靠？`

系统内部应拆成：

1. 目标主张识别
   - `MUG more reliable than MAD`
2. 证据维度识别
   - hallucination reduction
   - counterfactual verification
   - robustness under unreliable agents
3. 证据路径检索
   - `claim -> evidence -> result -> experiment`
4. 反证与局限扫描
   - limitation / missing condition / external validity
5. 生成 proof-style answer

#### 4.2.3 Subgraph Retrieval 机制

与当前 `bundle` 检索不同，建议新增显式的 subgraph retrieval 逻辑：

1. 根据 route 决定 target node types
2. 根据问题 embedding / symbolic cues 检索 anchor nodes
3. 沿指定 edge types 扩展邻接节点
4. 形成一个受控大小的 reasoning subgraph
5. 对 subgraph 做排序与裁剪

示例：

- `method` 问题：优先 `MethodStep / Claim / Section`
- `evidence` 问题：优先 `Claim / Evidence / Result`
- `critical` 问题：优先 `Claim / Limitation / CounterEvidence`
- `counterfactual` 问题：优先 `Claim / AblationCondition / Result / Assumption`

#### 4.2.4 Proof Assembly

系统输出答案前，应先组装一个最小证明结构：

- `target_claims`
- `supporting_evidences`
- `supporting_results`
- `related_experiments`
- `limitations`
- `missing_information`
- `reasoning_paths`

再将其送入 answer generator。

这样每个答案都不是一段“总结话术”，而是一份 mini proof。

#### 4.2.5 Counterfactual Reasoner

这是最值得做的差异化点。

新增一类问题模式：`counterfactual`

支持问题如：

- 如果去掉某个模块，结论还成立吗？
- 如果没有图像编辑这一步，MUG 是否仍有效？
- 如果作者没有做该消融实验，主张是否证据不足？
- 换一个数据集 / 指标后，该优势是否仍成立？

实现核心：

1. 识别 counterfactual target（模块 / 条件 / 数据集 / metric）
2. 找到与该 target 相关的 claim dependency
3. 找到 ablation / comparison / failure mode / limitation 节点
4. 输出结论变化：
   - strengthened
   - unchanged
   - weakened
   - unsupported

这是产品层非常强的创新点。

#### 4.2.6 Graph-grounded Verification

将当前 verifier 升级为基于图谱验证，而不是只根据 chunk 数量估分。

输出应至少包含：

- `evidence_sufficiency`
- `graph_completeness`
- `contradiction_risk`
- `generalization_risk`
- `unsupported_claims`

即：

- 该答案有没有完整路径支撑？
- 路径中是否存在断裂？
- 是否忽略 limitation / contradiction？
- 是否从实验结论外推出过强结论？

#### 4.2.7 对应代码切入点

建议新增或改造：

- `agents/qa_agent.py`
- `agents/question_router_agent.py`
- `agents/verifier_agent.py`
- 新增 `agents/proof_planner_agent.py`
- 新增 `services/subgraph_retriever.py`
- 新增 `services/counterfactual_reasoner.py`

---

### 4.3 第三层：Graph UX / Explainable Scholarly QA（图谱化交互层）

真正的壁垒不只在后端，也在用户是否能“感知到这不是普通聊天”。

#### 4.3.1 设计目标

将 QA 的可视化输出从：

- answer
- source chunks
- warnings

升级为：

- answer
- proof subgraph
- evidence path
- limitation nodes
- uncertainty decomposition
- unresolved gaps

#### 4.3.2 回答结果结构升级

建议聊天接口的最终 done payload 增加：

- `claim_nodes`
- `evidence_nodes`
- `result_nodes`
- `limitation_nodes`
- `reasoning_paths`
- `counterfactual_assessment`
- `uncertainty`

示例：

```json
{
  "answer": "...",
  "route_type": "evidence",
  "claim_nodes": ["claim_1"],
  "evidence_nodes": ["evidence_2", "evidence_5"],
  "result_nodes": ["result_3"],
  "reasoning_paths": [["claim_1", "evidence_2", "result_3"]],
  "counterfactual_assessment": {
    "condition": "without image editing",
    "impact": "weakened"
  },
  "uncertainty": {
    "evidence_sufficiency": 0.81,
    "contradiction_risk": 0.18,
    "generalization_risk": 0.43
  }
}
```

#### 4.3.3 聊天页展示建议

当前 `Chat.vue` 已有 route / warnings / evidence summary / reasoning trace / source chunks，可以继续升级为三层卡片：

1. `Answer Summary`
2. `Proof Graph`
3. `Risk & Uncertainty`

其中 `Proof Graph` 不必一开始就做 force graph，可先做“路径卡片”或“节点链条”展示：

- Claim card
- Evidence card
- Result card
- Limitation card

用户点击节点后可联动：

- PDF 位置
- 分析页对应 section
- 结构化 profile 详情

#### 4.3.4 图谱与 PDF 联动

建议实现：

- 点击 claim 跳转相关 section
- 点击 evidence 展示原文摘录
- 点击 result 展示数据集与 metric
- 点击 limitation 高亮风险说明

这会让图谱从“看起来有结构”变成“真的能导航阅读”。

#### 4.3.5 用户可感知的不确定性

建议不要只显示一个总 confidence，而是拆分展示：

- 证据充分性
- 图谱覆盖度
- 反证风险
- 泛化风险

这样系统更像研究助手，而不是一个喜欢给百分比的聊天机器人。

#### 4.3.6 对应代码切入点

建议主要落在：

- `frontend/src/views/Chat.vue`
- `frontend/src/api/index.js`
- `api.py` 的 chat SSE / WS payload
- 视情况新增 `frontend/src/components/ProofGraphCard.vue`

---

## 5. 建议新增的 QA 模式

为了让产品更有辨识度，建议把 QA 明确分成三种高级模式，而不是只有一个聊天框。

### 5.1 Proof QA

目标：回答“论文主张是否成立、由什么支撑”。

输出重点：

- target claim
- support chain
- result chain
- missing evidence

### 5.2 Counterfactual QA

目标：回答“去掉条件、替换条件后，结论如何变化”。

输出重点：

- counterfactual target
- affected claims
- changed results
- weakened / unsupported judgement

### 5.3 Critical QA

目标：回答“这篇论文哪里不可靠、哪里证据不充分、哪里可能过度推断”。

输出重点：

- unsupported claims
- limitation nodes
- contradiction risk
- external validity risk

这三种模式共同构成与普通论文 QA 的差异化定位。

---

## 6. 建议的返回数据结构

建议在当前 `QAResult` 基础上扩展为：

- `answer`
- `route_type`
- `claim_nodes`
- `evidence_nodes`
- `result_nodes`
- `limitation_nodes`
- `reasoning_paths`
- `counterfactual_assessment`
- `uncertainty`
- `warnings`
- `source_chunks`

其中：

- `source_chunks` 继续保留，作为 fallback / 原文展示
- 新结构逐步替代当前单薄的 `evidence_summary / reasoning_trace`

---

## 7. 最小可落地版本（MVP）

为了避免一次性重构过大，建议按以下顺序做 MVP。

### Phase 1：让图谱“有内容”

目标：让上传后稳定得到：

- sections
- claims
- evidences
- results
- limitations
- typed edges

完成标准：

- 不再经常出现 `claims = 0 / evidences = 0 / results = 0`
- graph JSON 有足够节点可用于问答

### Phase 2：让 QA 真正“按图回答”

目标：在 `QAAgent` 中新增：

- proof planner
- subgraph retriever
- graph-grounded verifier

完成标准：

- 回答不再主要依赖 chunk fallback
- 能输出 reasoning paths

### Phase 3：让用户“看见 proof”

目标：升级聊天页为：

- answer card
- proof graph card
- uncertainty card

完成标准：

- 用户能明确看到答案依据、路径、风险与缺口

### Phase 4：加入 Counterfactual QA

目标：支持：

- without module X
- without experiment Y
- under dataset Z
- under metric M

完成标准：

- 系统可稳定输出 `weakened / unsupported / unchanged` 等判断

---

## 8. 对当前项目的落地建议

基于当前代码库，最推荐的实施顺序如下：

1. **先补数据层，不先做炫酷图谱前端**
   - 优先稳定 claim / evidence / result 抽取
   - 优先把 graph edges 做真

2. **将 `QAAgent` 改成 graph-first, chunk-fallback**
   - 当前是混合检索
   - 下一步应明确“图谱优先，chunk 兜底”

3. **将 `reasoning_trace` 升级成 `reasoning_paths`**
   - 从抽象步骤描述转为真实节点路径

4. **将 `VerifierAgent` 升级为 uncertainty decomposition**
   - 不只返回一个 confidence

5. **前端先做“Proof Graph Card”，暂不强上 force graph**
   - 先用清晰的信息结构建立产品价值
   - 等图谱内容丰富后再做真正网络图可视化

---

## 9. 一句话总结

如果目标是做一个真正有创新性、技术壁垒的论文 QA，正确方向不是继续做更复杂的 RAG，而是：

**把 QA 从“文本问答”升级成“围绕论文主张构建与检验论证链的 ClaimProof QA”。**

其核心是三层：

1. `Argument Graph Construction`
2. `Subgraph Retrieval & Proof Reasoning`
3. `Graph UX / Explainable Scholarly QA`

其中最核心的创新点是：

- 以 claim 为中心组织知识
- 以 subgraph 为单位进行检索与推理
- 以 counterfactual 与 critical reasoning 形成差异化
- 以 proof / uncertainty / limitation 暴露构成真正的研究型问答体验

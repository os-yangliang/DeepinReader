# CE-RAG 正式研究方案（增强版）

## 1. 研究题目

中文题目：**基于主张-证据推理链增强检索的学术论文问答方法**

英文题目：**CE-RAG: Claim-Evidence Reasoning Chain Enhanced Retrieval-Augmented Generation for Academic Paper Question Answering**

方法简称：**CE-RAG**。

本方案将原“主张-证据图谱增强检索”升级为“主张-证据推理链检索 + 证据充分性估计”。CE-RAG 不仅构建论文内部图谱，还从图谱中检索可解释的 Claim-Evidence-Experiment-Result 推理链，并判断当前证据是否足以支持回答。

## 2. 研究定位

本研究面向学术论文智能阅读与问答任务，解决普通 RAG 在论文场景中存在的结构理解不足、证据链缺失、回答可信性不足和无依据生成等问题。

普通 RAG 多将论文切分为文本块，通过向量相似度检索 top-k 片段，再由大语言模型生成回答。这类方法难以显式利用论文中天然存在的“主张—证据—实验—结果”论证结构。现有 GraphRAG 多以通用实体关系图或层次摘要树为核心，科学事实验证工作则多以给定 claim 的验证为目标，而非面向用户多类型问题的开放式论文问答。

CE-RAG 将学术论文建模为由章节、主张、证据、实验、结果和局限性等对象构成的结构化论证图谱，并进一步提出主张-证据推理链检索和证据充分性估计机制，以提升问答的准确性、证据支撑性、可解释性和可信性。

## 3. 研究目标

本研究目标是提出并实现一种面向学术论文问答的主张-证据推理链增强检索生成方法，使系统能够：

1. 显式建模论文内部的主张、证据、实验和结果关系；
2. 根据问题类型动态选择检索策略；
3. 从论文图谱中检索可解释的主张-证据推理链；
4. 判断当前证据是否足以回答用户问题；
5. 基于充分证据生成可信回答；
6. 对生成答案进行证据一致性验证；
7. 降低无依据回答、过度概括和幻觉现象。

## 4. 核心研究问题

- **RQ1**：CE-RAG 是否能够提升学术论文问答质量？
- **RQ2**：主张-证据图谱是否能够提升证据检索效果？
- **RQ3**：主张-证据推理链检索是否能够提升回答可解释性？
- **RQ4**：问题路由机制是否能够改善不同类型问题的检索效果？
- **RQ5**：证据充分性估计是否能够降低无依据回答？
- **RQ6**：答案验证机制是否能够降低幻觉率？

## 5. 方法框架

```text
输入论文 D
   ↓
文档解析与章节切分
   ↓
学术对象抽取
   ↓
主张-证据图谱构建
   ↓
用户问题 q
   ↓
问题路由
   ↓
主张-证据推理链检索
   ↓
证据充分性估计
   ↓
证据约束答案生成
   ↓
答案验证
   ↓
输出答案、证据链、充分性评分、置信度与风险提示
```

核心模块：

1. Scholarly Object Extraction：学术对象抽取；
2. Claim-Evidence Graph Construction：主张-证据图谱构建；
3. Question Routing：问题路由；
4. Claim-Evidence Reasoning Chain Retrieval：主张-证据推理链检索；
5. Evidence Sufficiency Estimation：证据充分性估计；
6. Evidence-grounded Generation and Verification：证据约束生成与答案验证。

其中第 4、5 点是增强版方案的主要突破点。

## 6. 形式化定义

给定论文 \(D\)，表示为：

\[
D = \{S, C, E, X, R, L\}
\]

其中 \(S\) 为章节集合，\(C\) 为主张集合，\(E\) 为证据集合，\(X\) 为实验集合，\(R\) 为结果集合，\(L\) 为局限性集合。

构建主张-证据图谱：

\[
G = (V, A), \quad V = S \cup C \cup E \cup X \cup R \cup L
\]

边集合 \(A\) 表示章节包含、证据支撑、实验产生结果、结果支撑主张、局限约束主张等关系。

给定问题 \(q\)，CE-RAG 输出答案 \(a\)、证据集合 \(B\)、推理链集合 \(\mathcal{P}\) 和证据充分性评分 \(Suff\)：

\[
a, B, \mathcal{P}, Suff = CE\text{-}RAG(D, G, q)
\]

## 7. 主张-证据图谱

节点类型包括 Section、Claim、Evidence、Experiment、Result、Limitation。

边类型包括：

| 边类型 | 说明 |
|---|---|
| CONTAINS | 章节包含某对象 |
| SUPPORTED_BY | 主张由证据支撑 |
| DERIVED_FROM | 结果来源于实验 |
| SUPPORTS | 证据或结果支撑主张 |
| LIMITED_BY | 主张受到某局限影响 |
| RELATED_TO | 一般相关关系 |

## 8. 问题路由

问题类型包括 structure、method、evidence、result、critical、general 和 insufficient / unanswerable。

| 问题类型 | 重点检索对象 | 典型推理链 |
|---|---|---|
| structure | Section | Section → Section |
| method | Method Section, Claim | Section → Claim |
| evidence | Claim, Evidence, Experiment, Result | Claim → Evidence → Experiment → Result |
| result | Experiment, Result | Experiment → Result → Claim |
| critical | Limitation, Weak Evidence, Claim | Claim → Limitation / Missing Evidence |
| general | Section, Claim, Evidence | Section → Claim → Evidence |
| insufficient | Missing Evidence | Question → Missing Information |

## 9. 主张-证据推理链检索

传统 RAG 检索文本块：

\[
TopK = Retrieve(q, Chunks)
\]

CE-RAG 检索可解释推理链：

\[
\mathcal{P}_q = RetrieveChains(q, G, r)
\]

一条推理链表示为：

\[
P = c_i \rightarrow e_j \rightarrow x_k \rightarrow r_l
\]

表示主张 \(c_i\) 由证据 \(e_j\) 支撑，证据来源于实验 \(x_k\)，实验产生结果 \(r_l\)。

候选链评分函数：

\[
Score(P, q) = \alpha Sim(P, q) + \beta TypeMatch(P, r) + \gamma EdgeConf(P) + \delta EvidenceStrength(P)
\]

其中 \(Sim\) 表示问题与路径文本的语义相似度，\(TypeMatch\) 表示路径类型与问题类型匹配度，\(EdgeConf\) 表示边关系置信度，\(EvidenceStrength\) 表示证据强度。

系统选择 top-k 推理链：

\[
\mathcal{P}_q^* = TopK_{P \in \mathcal{P}(G)} Score(P, q)
\]

最终 Evidence Bundle 包含文本片段、章节、主张、证据、实验、结果和 top-k 推理链。

## 10. 证据充分性估计

CE-RAG 在生成答案前判断证据是否足够：

\[
Suff(q, B) = \lambda_1 Coverage(q, B) + \lambda_2 Support(q, B) + \lambda_3 Consistency(B) - \lambda_4 Missing(q, B)
\]

其中 Coverage 表示证据覆盖度，Support 表示证据支持度，Consistency 表示证据一致性，Missing 表示关键信息缺失程度。

若：

\[
Suff(q, B) < \tau
\]

系统执行以下策略之一：扩展检索、改变检索策略、降低置信度、拒答或输出证据不足提示。

该模块用于处理不可回答或证据不足问题，例如用户询问论文是否在未出现的数据集上取得 SOTA。若论文中没有相关实验，系统应提示证据不足，而不是编造回答。

## 11. 证据约束生成与答案验证

CE-RAG 将 Evidence Bundle 和 top-k 推理链作为生成上下文，要求模型只基于已检索证据回答。如果证据不足，系统应明确说明。

答案生成后，Verifier 检查答案是否被证据和推理链支持：

\[
V = Verify(q, a, B, \mathcal{P}_q^*)
\]

验证结果包括 supported points、unsupported points、warnings 和 confidence score。

## 12. 预期创新点

1. **主张-证据图谱表示**：将论文建模为包含章节、主张、证据、实验、结果和局限性的结构化论证图谱。
2. **问题感知的主张-证据推理链检索**：根据问题类型检索 Claim-Evidence-Experiment-Result 路径，而非仅检索文本块或孤立节点。
3. **证据充分性估计机制**：在生成答案前判断证据是否足够，并在证据不足时扩展检索、拒答或提示风险。
4. **证据约束生成与验证**：利用 Evidence Bundle 和 reasoning chains 约束生成，并验证答案证据一致性。
5. **可解释输出**：输出答案、支持证据、推理链、充分性评分、置信度和风险提示。

## 13. 实验设计

### 数据集

Pilot 阶段：5 篇论文，每篇 5～6 个问题，总计 25～30 个问题。

正式阶段：30～50 篇论文，每篇 5～6 个问题，总计 150～300 个问题。

为验证证据充分性估计，数据集应加入约 10% 不可回答或证据不足问题。

样本格式：

```json
{
  "paper_id": "paper_001",
  "question_id": "paper_001_q1",
  "question": "这篇论文提出的方法核心思想是什么？",
  "question_type": "method",
  "answerable": true,
  "gold_answer": "该论文提出了……",
  "gold_evidence": [
    { "section": "Method", "text": "The proposed method ..." }
  ],
  "gold_reasoning_chain": ["claim_1", "evidence_1", "experiment_1", "result_1"]
}
```

不可回答问题样例：

```json
{
  "paper_id": "paper_001",
  "question_id": "paper_001_q6",
  "question": "该方法是否在 ImageNet 上达到 SOTA？",
  "question_type": "unanswerable",
  "answerable": false,
  "gold_answer": "论文中没有提供 ImageNet 上的实验结果，无法根据论文证据判断。",
  "gold_evidence": []
}
```

### Baselines

- Naive RAG：向量检索 top-k chunk。
- BM25-RAG：关键词检索。
- Hybrid RAG：向量检索 + BM25。
- Long-context LLM：论文截断上下文直接回答。
- GraphRAG-style Baseline：检索图节点或子图，但不做推理链评分和证据充分性估计。
- CE-RAG：完整方法。

### 消融实验

| 方法变体 | 说明 |
|---|---|
| CE-RAG Full | 完整方法 |
| w/o Question Router | 去掉问题路由 |
| w/o Claim-Evidence Graph | 不使用图谱 |
| w/o Reasoning Chain Retrieval | 只检索节点，不检索路径 |
| w/o Evidence Sufficiency | 不进行证据充分性估计 |
| w/o Verifier | 不做答案验证 |

### 评价指标

检索指标：Evidence Recall@3、Evidence Recall@5、Evidence Precision@5、MRR、NDCG@5。

推理链指标：Chain Recall@k、Chain Completeness、Path Relevance、Path Faithfulness。

答案质量指标：Correctness、Completeness、Faithfulness、Relevance、Readability。

证据充分性指标：Sufficiency Accuracy、Abstention Precision、Abstention Recall、Unsupported Answer Rate。

幻觉率：统计答案中无证据支持内容的比例。

## 14. 预期结果表格

主实验表：

| Method | Correctness | Faithfulness | Evidence Recall@5 | Chain Recall@3 | Hallucination Rate |
|---|---:|---:|---:|---:|---:|
| Naive RAG | - | - | - | - | - |
| BM25-RAG | - | - | - | - | - |
| Hybrid RAG | - | - | - | - | - |
| GraphRAG-style | - | - | - | - | - |
| CE-RAG | - | - | - | - | - |

证据充分性实验表：

| Method | Sufficiency Accuracy | Abstention Precision | Abstention Recall | Unsupported Answer Rate |
|---|---:|---:|---:|---:|
| Hybrid RAG | - | - | - | - |
| GraphRAG-style | - | - | - | - |
| CE-RAG w/o Sufficiency | - | - | - | - |
| CE-RAG Full | - | - | - | - |

## 15. 论文结构规划

1. 摘要；
2. 引言；
3. 相关工作；
4. 方法：对象抽取、图谱构建、问题路由、推理链检索、证据充分性估计、答案生成与验证；
5. 实验设计；
6. 实验结果与分析；
7. 系统实现；
8. 结论。

## 16. 当前项目增强点

| 研究模块 | 当前代码对应模块 | 后续增强点 |
|---|---|---|
| 主张-证据结构 | `services/paper_schema.py` | 增加 chain、sufficiency 字段 |
| 图谱构建 | `services/paper_graph_builder.py` | 增强边置信度和路径关系 |
| 子图检索 | `services/subgraph_retriever.py` | 升级为 reasoning chain retrieval |
| 问题路由 | `agents/question_router_agent.py` | 加入 insufficient 类型 |
| 问答生成 | `agents/qa_agent.py` | 引入 chain-aware prompt 和 sufficiency handling |
| 答案验证 | `agents/verifier_agent.py` | 增加 sufficiency score 与 unsupported claim 检查 |
| Web API | `api.py` | 输出 reasoning chains 和 sufficiency score |

## 17. 方案结论

本研究最终确定为：**基于主张-证据推理链增强检索的学术论文问答方法 CE-RAG**。

该方法聚焦单篇学术论文问答任务，通过构建论文内部的主张-证据图谱，并进一步引入主张-证据推理链检索和证据充分性估计机制，提高学术论文问答的准确性、证据支撑性、可解释性和可信性。

增强后的 CE-RAG 相比原始方案具有更清晰的方法创新点，更容易支撑 CCF-C 类会议或中文核心期刊投稿。

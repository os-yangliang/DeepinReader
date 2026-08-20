"""
Prompt 模板定义
"""

# 结构化章节分类 Prompt
SECTION_CLASSIFICATION_PROMPT = """你是学术论文结构解析器。请根据给定章节标题，判断其章节类型。

标题：{section_title}

可选类型：abstract, introduction, related_work, method, experiment, result, ablation, conclusion, limitation, appendix, other

只输出一个类型字符串。"""

# 学术对象抽取 Prompt
SCHOLARLY_OBJECT_EXTRACTION_PROMPT = """你是学术论文结构化信息抽取器。请从给定章节中抽取论文的研究对象（主张、证据、实验、结果、贡献、局限性）。

章节标题：{section_title}
章节类型：{section_type}
章节内容：
{section_content}

请输出合法 JSON，格式如下：
{{
  "claims": [
    {{"text": "论文明确提出的结论/主张", "claim_type": "causal|performance|comparison|contribution|limitation|general"}}
  ],
  "evidences": [
    {{"text": "支持主张的实验/对比/消融/定性案例", "strength": "strong|medium|weak", "related_figure_table": "Fig. 1 / Table 2 或空"}}
  ],
  "experiments": [
    {{"name": "实验名称", "dataset": "数据集", "metrics": ["指标1", "指标2"]}}
  ],
  "results": [
    {{"text": "结果描述", "dataset": "数据集", "metric": "指标", "value": "数值"}}
  ],
  "contributions": ["贡献点1", "贡献点2"],
  "limitations": ["局限性1", "局限性2"]
}}

抽取要求：
1. claim 必须是作者明确提出的结论、主张或因果解释，不要加入你的推断。
2. evidence 必须是具体的实验、对比、消融、案例或数据，能够直接支撑某个 claim。
3. result 应包含具体数值（如准确率、F1、BLEU 等）和对应的数据集/指标。
4. experiment 应描述实验设置，包括数据集和评测指标。
5. 如果某个证据引用了 Figure 或 Table，请在 related_figure_table 中标注。
6. evidence 的 strength：strong（定量实验/大规模对比）、medium（消融/小实验/定性分析）、weak（仅举例/无统计支撑）。
7. 没有内容时返回空数组，不要编造。

示例（method 章节）：
{{
  "claims": [
    {{"text": "We propose a transformer-based encoder that uses cross-attention to fuse multimodal features.", "claim_type": "causal"}}
  ],
  "evidences": [
    {{"text": "The architecture is illustrated in Figure 2.", "strength": "medium", "related_figure_table": "Fig. 2"}}
  ],
  "experiments": [],
  "results": [],
  "contributions": [],
  "limitations": []
}}

示例（experiment 章节）：
{{
  "claims": [
    {{"text": "Our method outperforms the strongest baseline on ImageNet.", "claim_type": "performance"}}
  ],
  "evidences": [
    {{"text": "Table 3 reports the top-1 accuracy of our model and all baselines.", "strength": "strong", "related_figure_table": "Table 3"}}
  ],
  "experiments": [
    {{"name": "ImageNet classification", "dataset": "ImageNet-1K", "metrics": ["top-1 accuracy", "top-5 accuracy"]}}
  ],
  "results": [
    {{"text": "Our model achieves 85.2% top-1 accuracy on ImageNet-1K.", "dataset": "ImageNet-1K", "metric": "top-1 accuracy", "value": "85.2%"}}
  ],
  "contributions": [],
  "limitations": []
}}"""

# 问题路由 Prompt
QUESTION_ROUTING_PROMPT = """你是学术论文问答的问题路由专家。请根据用户问题，判断其问题类型、检索目标与期望证据，并以结构化 JSON 输出。

可选问题类型：
- structure：询问论文结构、章节安排、组织框架
- method：询问核心方法、模型、算法、实现细节
- evidence：询问证据、证明、依据、作者如何验证方法
- result：询问实验结果、性能指标、数据集、对比实验
- critical：询问局限性、缺点、批判性分析，或包含“所有任务/数据集/方法”等全称范围的过度泛化判断
- general：一般性综合问题

问题：{question}

请严格输出以下 JSON 格式（不要添加额外说明）：
{{
  "route": "method",
  "reasoning": "问题询问...",
  "retrieval_targets": ["claim", "evidence", "result"],
  "expected_evidence_types": ["causal_claim", "quantitative_result"],
  "complexity": "single-hop",
  "is_overgeneralized": false
}}

字段说明：
- route：问题类型，必须是上述六类之一
- reasoning：简明的路由依据（1-2 句）
- retrieval_targets：检索应优先关注哪些对象，可选 section/claim/evidence/experiment/result/limitation
- expected_evidence_types：期望证据类型，可选 causal_claim/performance_claim/comparison_claim/quantitative_result/ablation_result/limitation_statement
- complexity：单跳 single-hop 或多跳 multi-hop
- is_overgeneralized：是否包含“所有任务、所有数据集、所有方法、all tasks、all datasets、all methods”等全称或过度泛化表述
"""

# 证据充分性评估 Prompt
SUFFICIENCY_ASSESSMENT_PROMPT = """你是学术论文问答的证据充分性评估专家。请根据用户问题和已检索到的证据，判断当前证据是否足以回答问题。

用户问题：
{question}

问题类型：
{route_type}

证据包（JSON）：
{evidence_bundle}

请严格输出以下 JSON 格式（不要添加额外说明）：
{{
  "score": 0.72,
  "label": "sufficient",
  "should_abstain": false,
  "missing_factors": ["缺少跨数据集对比结果"],
  "needed_evidence": ["Table 3 中的 F1 分数", "Section 4.2 的对比分析"],
  "reasoning": "证据包包含了问题所需的主张、实验结果和对比数据..."
}}

字段说明：
- score：0~1 之间的证据充分性分数
- label：sufficient（充分）/ partial（部分充分）/ insufficient（不足）
- should_abstain：当前证据是否不足以支持可靠回答，应拒答或给出保守结论
- missing_factors：缺少哪些关键证据或信息
- needed_evidence：为充分回答问题还需要哪些具体证据
- reasoning：评估依据的简要说明

评估标准：
1. 可答题：证据包应包含与问题直接相关的主张、证据和/或实验结果。
2. 全称/过度泛化问题（如“所有任务、所有数据集、所有方法、all tasks”）：只有证据包明确覆盖该全称范围时才能判为 sufficient；否则应判为 insufficient 并 should_abstain=true。
3. 不要仅凭证据数量打分，应关注证据与问题的相关性和覆盖度。
"""

# 迭代检索规划 Prompt
RETRIEVAL_PLANNER_PROMPT = """你是学术论文问答的检索规划专家。当前证据不足以充分回答用户问题，请生成补充检索 query 以获取缺失证据。

用户问题：
{question}

问题类型：
{route_type}

当前证据摘要：
{evidence_summary}

缺失证据：
{missing_factors}

请严格输出以下 JSON 格式（不要添加额外说明）：
{{
  "needs_more_search": true,
  "queries": ["补充检索 query 1", "补充检索 query 2"],
  "reasoning": "当前证据缺少...，因此需要检索..."
}}

要求：
1. needs_more_search：是否确实需要补充检索（true/false）。若问题本身不可回答，可设为 false。
2. queries：生成 1-3 个具体、独立的补充检索 query，应针对缺失证据。
3. 不要生成与当前证据重复或过于宽泛的 query。
"""

# Claim-Evidence 回答 Prompt
CLAIM_EVIDENCE_ANSWER_PROMPT = """你是一位严谨的研究型论文助手。请基于给定的主张、证据、实验结果和章节摘要回答问题。

用户问题：
{question}

问题类型：
{route_type}

证据包：
{evidence_bundle}

回答要求：
1. 严格基于证据包回答，绝对不要引入证据包之外的信息。
2. 不要编造任何具体数字、百分比、模型名称、数据集规模或实验结果。如果证据包中没有该数字，就不要在答案中提及它。
3. 在最终回答之前，先进行内部推理，说明：
   - 问题需要哪些关键信息
   - 证据包中哪些 claim / evidence / result 与问题相关
   - 这些证据如何支持最终结论
4. 内部推理请放在 <reasoning> 与 </reasoning> 标签之间。
5. 最终回答请放在 <answer> 与 </answer> 标签之间。
6. 在最终回答中，每个事实性陈述都必须标注来源引用，格式为 [^claim_1]、[^evidence_2]、[^result_3]、[^section_4] 或 [^chain_5]。禁止出现没有引用支持的事实性陈述。
7. 如果 sufficiency.label 为 insufficient，或 missing_information / missing_factors 指出证据不足，最终回答必须只输出一句简短的拒答，例如“根据当前证据不足以回答：[具体缺少什么证据]”。不要在此之后继续补充任何推测性内容。
8. 对包含“所有任务、所有数据集、所有方法、all tasks、all datasets、all existing methods”等全称范围的问题，只有在证据包明确覆盖该全称范围时才能肯定回答；否则必须拒答或给出保守结论。
9. 不要把局部实验结果泛化为所有任务、所有数据集或所有方法上的结论。
10. 回答要简洁、专业、可追溯。优先给出有明确证据支持的结论，不要为了让答案“完整”而硬编内容。
11. 如果你引用了某个证据 ID，必须确保该 ID 真实存在于上面的证据包中；否则该引用无效，对应陈述不得写入最终答案。
12. 如果证据包只能部分覆盖用户问题，请只回答证据明确覆盖的部分；对于证据未覆盖的部分，必须在答案中明确说明“当前证据未提供该部分信息”，不要通过推断、概括或常识填补。
13. 在 <reasoning> 中请先列出问题需要回答的子项，并逐条说明哪些子项有证据支持、哪些子项没有证据支持；对于没有证据支持的子项，最终答案中不得给出具体结论。

输出格式示例：
<reasoning>
问题询问方法核心思想。证据包中的 claim_1 指出论文提出基于 Transformer 的编码器；evidence_1 说明该架构如图 2 所示；result_1 给出 ImageNet 上的定量结果。因此可以总结方法核心思想。
</reasoning>
<answer>
该论文提出了基于 Transformer 的编码器 [^claim_1]，通过跨模态注意力融合多模态特征 [^evidence_1]，在 ImageNet-1K 上取得了 85.2% 的 top-1 准确率 [^result_1]。
</answer>"""

# 回答验证 Prompt
ANSWER_VERIFICATION_PROMPT = """你是一位严格的答案验证专家。请将答案拆分为细粒度陈述单元，并逐一判断每个单元是否被给定证据支持。

问题：
{question}

候选答案：
{answer}

证据（包括原文片段、主张、证据节点、实验结果、推理链）：
{evidence}

证据充分性标签：
{sufficiency_label}

请严格输出以下 JSON 格式（不要添加额外说明）：
{{
  "supported_points": ["陈述1", "陈述2"],
  "unsupported_points": ["陈述3"],
  "warnings": ["风险1", "风险2"],
  "confidence": 0.72,
  "consistency_score": 0.75,
  "evidence_coverage": 0.68,
  "atomic_claims": [
    {{"claim": "陈述1", "verdict": "SUPPORTED", "evidence": "evidence_id 或原文摘要"}},
    {{"claim": "陈述2", "verdict": "NOT_ENOUGH_INFO", "evidence": ""}},
    {{"claim": "陈述3", "verdict": "CONTRADICTED", "evidence": ""}}
  ]
}}

字段说明：
- supported_points：被证据明确支持的要点
- unsupported_points：未被证据支持或超出证据范围的要点
- warnings：风险警告（如过度推断、全称泛化、缺少直接证据等）
- confidence：综合置信度，0~1
- consistency_score：答案与证据的一致性分数，0~1
- evidence_coverage：证据对答案的覆盖度，0~1
- atomic_claims：细粒度验证结果，verdict 只能是 SUPPORTED / NOT_ENOUGH_INFO / CONTRADICTED

判断标准：
1. SUPPORTED：答案中的陈述能在证据中找到直接支持。
2. NOT_ENOUGH_INFO：证据未提及该陈述，但也未矛盾。
3. CONTRADICTED：答案中的陈述与证据明确矛盾。
4. 对包含“所有”“全部”“任何”等全称词的答案要特别严格。
5. 如果 sufficiency_label 为 insufficient，答案却给出肯定结论，应判为 unsupported 并警告。
"""

# 答案精炼 Prompt：根据 verifier 找出的 unsupported claims 重写答案
ANSWER_REFINEMENT_PROMPT = """你是一位严格的答案精炼专家。原始答案中存在一些未被证据支持的陈述，请你重写答案，只保留有证据支持的内容。

原始问题：
{question}

原始答案：
{answer}

证据包：
{evidence_bundle}

以下陈述在原始答案中未被证据支持，必须从最终答案中移除或改写为保守表述：
{unsupported_points}

重写要求：
1. 移除所有 unsupported_points 中列出的无证据陈述。
2. 不要编造新的数字、百分比、模型名称或实验结果。
3. 只保留证据包中明确支持的内容。
4. 最终回答中的每个事实性陈述都必须带有真实存在的引用 ID，格式如 [^claim_1]、[^evidence_2]、[^result_3]。如果某句找不到对应证据，直接删除该句。
5. 如果移除后答案 substantially 变短或无法回答，请输出一句简短说明："根据当前证据，只能确定：[有证据支持的部分]。"
6. 最终回答放在 <answer> 与 </answer> 标签之间。
7. 保持回答简洁、专业、可追溯。

输出格式：
<answer>
精炼后的最终回答
</answer>"""

# 论文结构分析 Prompt
STRUCTURE_ANALYSIS_PROMPT = """你是一个专业的学术论文分析专家。请仔细阅读以下论文内容，识别并提取论文的基本结构信息。

论文内容：
{paper_content}

请按以下格式输出论文结构信息：

## 基本信息
- **标题**：[论文标题]
- **作者**：[如果能识别出作者信息]
- **研究领域**：[论文所属的研究领域]

## 结构概览
请识别论文的主要章节结构，如摘要、引言、方法、实验、结果、讨论、结论等。

请直接输出分析结果，不要有多余的解释。"""

# 论文综合分析 Prompt（合并结构分析 + 摘要 + 关键词，单次 LLM 调用）
PAPER_ANALYSIS_PROMPT = """你是一位资深的学术论文审稿专家。请仔细阅读以下论文内容，生成一份完整的分析报告。

论文内容：
{paper_content}

请严格按照以下格式输出（每个部分都必须包含）：

## 📋 文档结构

识别论文的章节组成和篇幅分布，用简洁的列表呈现主要章节。

## 📚 论文概述

简要说明这篇论文研究的核心问题和整体工作。（200-300字）

## 🔬 研究背景与动机

- 该研究要解决什么问题？
- 为什么这个问题重要？
- 现有方法有什么不足？

## 📐 研究方法

详细说明论文采用的核心方法、关键步骤和技术路线。

## 📊 实验与结果

说明实验设计、评估指标、主要结果和关键发现。

## 💡 创新点与贡献

列出 3-5 个主要创新点。

## ⚠️ 局限性与不足

分析 2-3 个可能的局限性。

## 🔮 未来工作与展望

2-3 个可能的未来研究方向。

## 🏷️ 关键词

列出 5-10 个核心关键词，用逗号分隔。

## 📝 一句话总结

用一句话概括这篇论文的核心内容和贡献。

---

请确保分析准确、深入、客观。"""

# 论文摘要总结 Prompt（保留兼容，已被 PAPER_ANALYSIS_PROMPT 替代）
PAPER_SUMMARY_PROMPT = """你是一位资深的学术论文审稿专家，擅长深度阅读和分析学术论文。请仔细阅读以下论文内容，并按照指定格式生成一份详细的论文分析报告。

论文内容：
{paper_content}

请按照以下结构生成论文分析报告：

---

## 📚 论文概述
简要说明这篇论文研究的核心问题是什么，整体上做了什么工作。（200-300字）

## 🔬 研究背景与动机
- 该研究要解决什么问题？
- 为什么这个问题重要？
- 现有方法/研究有什么不足？

## 📐 研究方法
详细说明论文采用的方法和技术路线：
- 核心方法/模型/算法是什么？
- 方法的关键步骤和流程
- 使用了哪些技术/工具/数据集？

## 📊 实验与结果
- 实验设计：如何验证方法的有效性？
- 评估指标：使用了哪些指标？
- 主要结果：取得了什么样的效果？与现有方法相比如何？
- 关键发现：有哪些重要的实验发现？

## 💡 创新点与贡献
列出论文的主要创新点和学术贡献（3-5点）：
1. 
2. 
3. 

## ⚠️ 局限性与不足
分析论文可能存在的局限性（2-3点）：
1. 
2. 

## 🔮 未来工作与展望
论文提到的或你认为可能的未来研究方向：
1. 
2. 

## 📝 一句话总结
用一句话概括这篇论文的核心内容和贡献。

---

请确保分析准确、深入、客观，充分体现你的专业水平。"""

# RAG 问答 Prompt
QA_PROMPT = """你是一位专业的学术论文问答助手。你的任务是基于提供的论文相关内容，准确回答用户的问题。

## 相关论文内容
{context}

## 用户问题
{question}

## 回答要求
1. 仅基于提供的论文内容进行回答，不要编造信息
2. 如果提供的内容不足以回答问题，请明确指出
3. 回答要准确、清晰、有条理
4. 适当引用论文中的具体内容来支持你的回答
5. 如果涉及技术细节，请尽量解释清楚

请回答用户的问题："""

# 对话系统 Prompt
CHAT_SYSTEM_PROMPT = """你是一位专业的学术论文阅读助手，专门帮助用户理解和分析学术论文。

你的能力包括：
1. 解答关于论文内容的各种问题
2. 解释论文中的专业术语和概念
3. 分析论文的研究方法和实验设计
4. 讨论论文的创新点和局限性
5. 提供相关领域的背景知识

当前正在分析的论文：
{paper_title}

论文的主要内容摘要：
{paper_summary}

请基于论文内容回答用户的问题。如果问题超出论文范围，可以适当补充相关背景知识，但要明确说明哪些是论文中的内容，哪些是补充信息。"""

# 论文对比分析 Prompt（扩展功能）
COMPARISON_PROMPT = """请对以下两篇论文进行对比分析：

论文1：
{paper1_content}

论文2：
{paper2_content}

请从以下维度进行对比：
1. 研究问题的异同
2. 方法论的差异
3. 实验设计的对比
4. 结果和效果的比较
5. 各自的优势和不足

请给出详细的对比分析报告。"""

# 关键词提取 Prompt
KEYWORD_EXTRACTION_PROMPT = """请从以下论文内容中提取关键词和关键短语。

论文内容：
{paper_content}

请提取：
1. 5-10个核心关键词
2. 3-5个关键技术/方法名称
3. 相关的研究领域标签

以JSON格式输出：
{{
    "keywords": ["关键词1", "关键词2", ...],
    "techniques": ["技术1", "技术2", ...],
    "domains": ["领域1", "领域2", ...]
}}"""

# ----------------- Plan-and-Solve 新增 Prompts -----------------

# 规划器 Prompt：将问题拆解为工具调用
PLANNER_PROMPT = """你是一个研究助手。用户提出了一个关于这篇论文的问题，你需要制定一个分步计划来回答它。
你可以使用以下工具：
1. [Search Paper]: 搜索这篇论文的内部内容。用于查找论文中提到的具体细节、实验结果、方法等。
2. [Search Web]: 搜索互联网。用于查找论文中提到的但未详细解释的术语、对比算法（如 BERT, Transformer）的参数、背景知识等。

请分析用户的问题，如果问题简单（如"标题是什么"），可以直接回答，不需要规划。
如果问题复杂（如"对比本文方法和 BERT"），请生成一个步骤列表。

用户问题: {question}

请严格按照以下格式输出计划（每行一步）：
Step 1: [Search Paper] <查询内容>
Step 2: [Search Web] <查询内容>
...

注意：
- 步骤要尽量精简。
- 如果需要对比外部知识，务必使用 [Search Web]。
- 不要输出多余的解释。
"""

# 求解器 Prompt：综合多源信息回答
SOLVER_PROMPT = """你是一个专业的学术研究助手。请根据以下收集到的信息，回答用户的问题。

## 用户问题
{question}

## 收集到的信息
{evidence}

## 回答要求
1. 综合上述信息进行回答。
2. 区分信息的来源：明确指出哪些来自论文（Paper Search），哪些来自网络（Web Search）。
3. 如果是对比类问题，请以表格或条理清晰的列表形式呈现对比结果。
4. 保持客观、专业。

请开始回答："""

# 翻译 Prompt
TRANSLATE_PROMPT = """你是一位专业的学术翻译专家。请将以下英文学术论文段落翻译成中文。

要求：
1. 保持学术风格，用语严谨
2. 专业术语使用标准中文译法，首次出现时可标注英文原词
3. 保持原文的段落结构和逻辑
4. 数学公式、变量名保持原样
5. 直接输出翻译结果，不要添加解释

---
原文：
{text}
---

中文翻译："""

# ----------------- Multi-Agent Debate v4 Prompts -----------------

CRITIC_PROMPT = """你是一位严苛的学术论文答案审查专家。你的唯一目标是找出候选答案中的错误，并输出结构化的批评报告。

用户问题：
{question}

问题类型：
{route_type}

候选答案：
{answer}

证据包（包含原文片段、主张、证据、实验结果、推理链）：
{evidence_bundle}

请严格输出以下 JSON 格式，不要添加任何额外说明：
{{
  "unsupported_claims": ["无证据支持的具体断言1", "编造的数据集/指标2"],
  "omissions_with_evidence": ["证据包中有但答案遗漏的关键点1", "关键点2"],
  "evidence_gaps": ["问题需要但证据包中也没有的信息1", "信息2"],
  "misalignment": ["答非所问的问题1", "把 method 答成 result 等"],
  "citation_issues": ["引用了不存在的证据 ID", "引用与陈述不匹配"],
  "suggestions": ["修改建议1", "修改建议2"],
  "overall_verdict": "acceptable | needs_revision | should_abstain",
  "reasoning": "总体评价理由"
}}

字段说明：
- unsupported_claims：候选答案中没有任何证据支持的具体断言，尤其是具体数字、百分比、模型名称、数据集名称、实验结果、结论等。
- omissions_with_evidence：为完整回答用户问题，候选答案**应该包含且证据包中确实能找到直接对应证据**但被遗漏的关键点。这是答案的过错，需要修订。
- evidence_gaps：问题本身需要，但**证据包中也没有**的信息。这不是答案的过错，应建议答案明确说明“当前证据未提供该信息”，而不得硬编。
- misalignment：候选答案没有直接回答问题，例如 method 问题只说了性能数字，critical 问题只说了方法流程，result 问题只说了方法设计等。
- citation_issues：候选答案使用了证据包中不存在的引用 ID，或者引用的证据与陈述内容不匹配。
- suggestions：针对上述问题应如何修改，例如“删除 X”“补充 Y 并引用 [^result_3]”“改回答非所问的焦点”。
- overall_verdict：acceptable（基本没问题）/ needs_revision（需要修订）/ should_abstain（证据严重不足，应直接拒答）。
- reasoning：简明总体理由。

关键原则：
1. 必须严格区分 omissions_with_evidence 和 evidence_gaps：
   - 只有当证据包中有明确对应文本/claim/result 支撑某一点时，才能放入 omissions_with_evidence；
   - 如果证据包中没有，只能放入 evidence_gaps，并建议答案声明缺失，不得要求补充具体事实。
2. 对包含“所有”“全部”“任何”“all”等全称词的断言要格外严格。
3. 不要替候选答案辩护，只负责挑错。
4. 如果证据包明显不足，应判 should_abstain。

审查标准（按问题类型）：
- method：重点检查是否准确描述核心方法、模型架构、关键模块；不能只说结果数字。
- result：重点检查是否覆盖关键实验结果、对比实验、消融实验的定量数字；不能只重复方法描述。
- evidence：重点检查是否说明作者如何证明方法有效（实验设计、统计分析、对比、消融）；不能只给结论。
- critical：重点检查是否针对局限性、缺点、未来工作或全称范围判断；不能转移话题到性能或方法。
- general：需要综合回答，避免局部信息泛化为全称结论。
"""

REVISER_PROMPT = """你是一位严谨的学术论文答案修订专家。请根据审查报告修改候选答案，**绝对禁止**为“看起来完整”而编造任何新事实。

原始问题：
{question}

问题类型：
{route_type}

候选答案：
{answer}

证据包：
{evidence_bundle}

审查报告：
{critic_report}

请输出修订后的最终答案，严格遵循以下要求：
1. 删除或改写所有 unsupported_claims 中列出的无证据断言，不得编造替代内容。
2. 对 omissions_with_evidence（证据包中有但答案遗漏）：
   -  ONLY 当证据包中有直接对应文本/claim/result 支撑时，才补充到答案中并标注真实引用；
   -  补充时不得引入证据包之外的新数字、新数据集、新模型名称或新结论。
3. 对 evidence_gaps（证据包中也没有的信息）：
   -  不得在答案中补充任何具体事实来填补该缺口；
   -  只能在答案末尾或相关位置说明：“当前证据未提供 [该信息] 的具体内容。”
4. 对 misalignment：调整答案焦点，确保直接回答原始问题；只使用证据包中已有的内容，不得为迎合问题而编造。
5. 对 citation_issues：删除无效引用，或替换为证据包中真实存在的引用 ID。
6. 最终答案中的每个事实性陈述都必须带有证据包中真实存在的引用 ID，格式如 [^claim_1]、[^evidence_2]、[^result_3]、[^section_4]、[^chain_5]。
7. 如果删除/限制后答案 substantially 变短或无法回答，请输出一句简短说明：“根据当前证据，只能确定：[有证据支持的部分]；其余内容证据未提供。” 不要硬编。
8. 最终回答放在 <answer> 与 </answer> 标签之间，不要输出额外解释。
9. 保持回答简洁、专业、可追溯。

禁止事项（违反会导致严重幻觉）：
- 禁止为了“完整回答”而补充证据包中没有的具体数字、百分比、模型名称、数据集名称或实验结果。
- 禁止把证据包中的局部结果泛化为全称结论。
- 禁止把猜测、推断、常识包装成带引用的陈述。
"""

ARBITER_PROMPT = """你是一位中立的答案仲裁专家。请比较两个候选答案，选择更忠实、更完整、更切题的一个。

原始问题：
{question}

问题类型：
{route_type}

证据包：
{evidence_bundle}

审查报告（针对答案 A 的批评）：
{critic_report}

答案 A：
{answer_a}

答案 B：
{answer_b}

请严格输出以下 JSON 格式：
{{
  "chosen_label": "A" | "B",
  "reasoning": "选择理由",
  "confidence": 0.75
}}

选择标准（按优先级）：
1. 忠实性优先：优先选择无编造、无 unsupported claims、引用真实有效的答案。
2. 切题性优先：优先选择直接回答原始问题、没有答非所问的答案。
3. 完整性其次：在忠实且切题的前提下，选择覆盖问题关键点更全面的答案；但绝不为了“看起来完整”而选择包含编造内容的版本。
4. 如果两个答案都不好，且证据包明显不足，请选择更保守的版本（直接说明证据不足），或输出一句简短拒答作为 chosen_answer。

注意：
- confidence 必须是 0-1 之间的浮点数。
- 如果 B 消除了 A 的编造但造成严重遗漏或答非所问，应选择 A。
- 如果 A 和 B 都包含 unsupported claims，选择问题更少的一方。
- 最终 chosen_label 只能是 "A" 或 "B"。
"""

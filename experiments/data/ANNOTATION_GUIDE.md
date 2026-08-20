# Pilot 数据集标注指南

你已经将 5 篇论文放在：

```text
experiments/data/papers/
```

当前已生成 Pilot 标注模板：

```text
experiments/data/qa_dataset.pilot.template.jsonl
```

建议复制一份作为正式 pilot 数据集：

```text
experiments/data/qa_dataset.pilot.jsonl
```

然后在 `qa_dataset.pilot.jsonl` 中逐条填写。

## 每篇论文 6 个问题

每篇论文包含以下问题类型：

1. `method`：方法核心思想
2. `evidence`：作者如何证明方法有效
3. `result`：主要实验结果
4. `critical`：局限性或潜在不足
5. `general`：主要贡献
6. `unanswerable`：证据不足/不可回答问题

## 每条样本需要填写的字段

### title

填写论文标题。

### gold_answer

填写人工标准答案。建议 2～6 句话即可，不需要太长。

### gold_evidence

填写支持标准答案的论文原文片段。

格式：

```json
"gold_evidence": [
  {
    "section": "Method",
    "text": "The proposed method ..."
  }
]
```

建议每题填 1～3 条 evidence。

### gold_reasoning_chain

Pilot 阶段可以先保持空数组：

```json
"gold_reasoning_chain": []
```

后续等系统自动抽取出 claim/evidence/result 节点 ID 后，再补充。

## 不可回答问题怎么标

对于 `question_type = "unanswerable"` 的样本：

```json
"answerable": false,
"gold_answer": "论文没有提供相关证据，无法根据本文判断。",
"gold_evidence": []
```

目标是测试 CE-RAG 是否会在证据不足时避免胡乱回答。

## 标注建议

- 优先从 Abstract、Introduction、Method、Experiments、Results、Conclusion、Limitations 中找证据。
- gold evidence 尽量贴论文原文，不要贴自己改写后的内容。
- gold answer 可以是中文概括。
- 如果论文没有明确 limitation，可以根据实验范围、数据集范围、方法假设做谨慎总结，但 evidence 应来自论文相关段落。
- 每篇论文先完成 3 个核心问题：method、evidence、result，再补 critical、general 和 unanswerable。

## 标注完成后运行

CE-RAG：

```bash
python experiments/run_ce_rag.py --dataset experiments/data/qa_dataset.pilot.jsonl --output experiments/outputs/ce_rag_pilot_results.jsonl
```

Naive RAG：

```bash
python experiments/run_naive_rag.py --dataset experiments/data/qa_dataset.pilot.jsonl --output experiments/outputs/naive_rag_pilot_results.jsonl
```

Hybrid RAG：

```bash
python experiments/run_hybrid_rag.py --dataset experiments/data/qa_dataset.pilot.jsonl --output experiments/outputs/hybrid_rag_pilot_results.jsonl
```

生成评价表：

```bash
python experiments/evaluate_template.py --predictions experiments/outputs/ce_rag_pilot_results.jsonl --output experiments/outputs/ce_rag_pilot_eval.csv
```


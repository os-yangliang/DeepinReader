# CE-RAG Experiments

This directory contains batch experiment scripts for the CE-RAG research plan.

## Dataset format

Input datasets are JSONL files. Each line is one QA sample:

```json
{
  "paper_id": "paper_001",
  "paper_path": "experiments/data/papers/paper_001.pdf",
  "title": "Example Paper",
  "question_id": "paper_001_q1",
  "question": "这篇论文提出的方法核心思想是什么？",
  "question_type": "method",
  "answerable": true,
  "gold_answer": "...",
  "gold_evidence": [
    { "section": "Method", "text": "..." }
  ],
  "gold_reasoning_chain": ["claim_1", "evidence_1", "experiment_1", "result_1"],
  "metadata": {}
}
```

## Unified output format

All runners write JSONL outputs with the same fields:

```json
{
  "question_id": "paper_001_q1",
  "paper_id": "paper_001",
  "method": "ce_rag",
  "question": "...",
  "answer": "...",
  "answerable": true,
  "pred_answerable": true,
  "route_type": "method",
  "source_chunks": [],
  "evidence_summary": [],
  "reasoning_trace": [],
  "reasoning_paths": [],
  "claim_nodes": [],
  "evidence_nodes": [],
  "result_nodes": [],
  "sufficiency_score": null,
  "confidence": 0.0,
  "warnings": [],
  "error": "",
  "latency_seconds": 0.0,
  "extra": {}
}
```

## AI-assisted annotation

Generate AI pre-labels from the pilot template:

```bash
python experiments/auto_annotate_dataset.py --template experiments/data/qa_dataset.pilot.template.jsonl --output experiments/data/qa_dataset.pilot.ai.jsonl
```

Dry run without calling the LLM, useful for checking PDF parsing and selected context:

```bash
python experiments/auto_annotate_dataset.py --dry-run --question-limit 3
```

Annotate only the first paper first:

```bash
python experiments/auto_annotate_dataset.py --paper-limit 1 --output experiments/data/qa_dataset.pilot.ai.paper1.jsonl
```

The generated file is an AI pre-annotation. Review `metadata.needs_human_review` rows before treating them as gold labels.

## First-run commands

Run CE-RAG on the sample dataset:

```bash
python experiments/run_ce_rag.py --dataset experiments/data/qa_dataset.sample.jsonl --output experiments/outputs/ce_rag_results.jsonl
```

Run Naive RAG:

```bash
python experiments/run_naive_rag.py --dataset experiments/data/qa_dataset.sample.jsonl --output experiments/outputs/naive_rag_results.jsonl
```

Create an evaluation template CSV:

```bash
python experiments/evaluate_template.py --predictions experiments/outputs/ce_rag_results.jsonl --output experiments/outputs/ce_rag_eval_template.csv
```

## Notes

- Put pilot PDFs under `experiments/data/papers/`.
- The sample dataset uses placeholder PDF paths; replace them before running real experiments.
- Scripts are designed to produce structured output even when a sample fails, so failed cases can be inspected later.

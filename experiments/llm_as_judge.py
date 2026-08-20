"""LLM-as-Judge evaluation for CE-RAG experiments."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.schema import read_jsonl
from services.llm_service import LLMService

SYSTEM = """You are a strict evaluator for scientific paper QA. Judge only according to the gold answer, gold evidence, and retrieved evidence. Do not reward unsupported plausible claims. Return valid JSON only."""

PROMPT = """Evaluate this scientific paper QA result.

Question: {question}
Gold answer: {gold_answer}
Gold evidence: {gold_evidence}
Answerable label: {answerable}

Method: {method}
Candidate answer: {answer}
Candidate predicted answerable: {pred_answerable}
Retrieved evidence/context: {evidence}

Rubric:
- correctness_score: 1-5, whether the answer correctly addresses the question.
- faithfulness_score: 1-5, whether the answer is supported by evidence and avoids unsupported claims.
- evidence_coverage_score: 1-5, whether the evidence/answer covers key supporting facts.
- relevance_score: 1-5, whether the answer is relevant.
- readability_score: 1-5, whether the answer is clear and fluent.
- hallucination_flag: 0 or 1, where 1 means unsupported or over-generalized claims exist.
- sufficiency_judgment_score: 1-5, whether the method correctly handles answerable vs insufficient-evidence cases.

Return exactly this JSON schema:
{{"correctness_score":1,"faithfulness_score":1,"evidence_coverage_score":1,"relevance_score":1,"readability_score":1,"hallucination_flag":0,"sufficiency_judgment_score":1,"rationale":"brief reason"}}
"""

FIELDS = [
    "method", "count", "answerability_accuracy", "correctness", "faithfulness",
    "evidence_coverage", "relevance", "readability", "hallucination_rate",
    "sufficiency_judgment", "avg_latency",
]


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run LLM-as-Judge for experiment predictions.")
    p.add_argument("--dataset", required=True)
    p.add_argument("--predictions", nargs="+", required=True)
    p.add_argument("--output", default="experiments/outputs/llm_judge_results.jsonl")
    p.add_argument("--summary", default="experiments/outputs/llm_judge_summary.csv")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--sleep", type=float, default=0.0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-evidence-chars", type=int, default=4500)
    return p.parse_args()


def path(x: str | Path) -> Path:
    x = Path(x)
    return x if x.is_absolute() else ROOT / x


def compact(v: Any, n: int = 3000) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        s = "\n".join(compact(x, 800) for x in v[:8])
    elif isinstance(v, dict):
        s = "; ".join(f"{k}: {compact(val, 500)}" for k, val in v.items())
    else:
        s = str(v)
    return re.sub(r"\s+", " ", s).strip()[:n]


def method_name(pred_path: Path) -> str:
    name = pred_path.stem.lower()
    if "ce_rag" in name:
        return "ce_rag"
    if "hybrid" in name:
        return "hybrid_rag"
    if "naive" in name or "chunk" in name:
        return "naive_rag"
    return pred_path.stem


def extract_json(text: str) -> Dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*", "", (text or "").strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def as_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        x = int(v)
    except Exception:
        return default
    return max(lo, min(hi, x))


def normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "correctness_score": as_int(d.get("correctness_score"), 1, 5, 1),
        "faithfulness_score": as_int(d.get("faithfulness_score"), 1, 5, 1),
        "evidence_coverage_score": as_int(d.get("evidence_coverage_score"), 1, 5, 1),
        "relevance_score": as_int(d.get("relevance_score"), 1, 5, 1),
        "readability_score": as_int(d.get("readability_score"), 1, 5, 1),
        "hallucination_flag": as_int(d.get("hallucination_flag"), 0, 1, 1),
        "sufficiency_judgment_score": as_int(d.get("sufficiency_judgment_score"), 1, 5, 1),
        "rationale": compact(d.get("rationale", ""), 1000),
    }


def evidence(pred: Dict[str, Any], max_chars: int) -> str:
    parts = [
        "Evidence summary: " + compact(pred.get("evidence_summary", []), 1200),
        "Source chunks: " + compact(pred.get("source_chunks", []), 2600),
        "Reasoning chains: " + compact(pred.get("reasoning_chains", []), 1200),
        "Warnings: " + compact(pred.get("warnings", []), 600),
    ]
    return "\n".join(parts)[:max_chars]


def done_keys(out: Path) -> set[tuple[str, str]]:
    if not out.exists():
        return set()
    return {(r.get("method", ""), r.get("question_id", "")) for r in read_jsonl(out)}


def summarize(rows: List[Dict[str, Any]], out: Path) -> None:
    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(r["method"], []).append(r)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for method, xs in sorted(by.items()):
            n = len(xs)
            acc = sum(1 for x in xs if x.get("answerable") == x.get("pred_answerable")) / n if n else 0
            w.writerow({
                "method": method,
                "count": n,
                "answerability_accuracy": round(acc, 4),
                "correctness": round(sum(x["correctness_score"] for x in xs) / n, 4) if n else 0,
                "faithfulness": round(sum(x["faithfulness_score"] for x in xs) / n, 4) if n else 0,
                "evidence_coverage": round(sum(x["evidence_coverage_score"] for x in xs) / n, 4) if n else 0,
                "relevance": round(sum(x["relevance_score"] for x in xs) / n, 4) if n else 0,
                "readability": round(sum(x["readability_score"] for x in xs) / n, 4) if n else 0,
                "hallucination_rate": round(sum(x["hallucination_flag"] for x in xs) / n, 4) if n else 0,
                "sufficiency_judgment": round(sum(x["sufficiency_judgment_score"] for x in xs) / n, 4) if n else 0,
                "avg_latency": round(sum(float(x.get("latency_seconds") or 0) for x in xs) / n, 4) if n else 0,
            })


def main() -> None:
    a = args()
    gold = {r["question_id"]: r for r in read_jsonl(path(a.dataset))}
    out = path(a.output)
    summary = path(a.summary)
    llm = LLMService(temperature=0.0)
    finished = done_keys(out) if a.resume else set()
    rows = read_jsonl(out) if a.resume and out.exists() else []
    jobs = []
    for pred_file in a.predictions:
        pred_path = path(pred_file)
        preds = read_jsonl(pred_path)
        if a.limit:
            preds = preds[:a.limit]
        hint = method_name(pred_path)
        for pred in preds:
            method = pred.get("method") or hint
            qid = pred.get("question_id", "")
            if qid in gold and (method, qid) not in finished:
                jobs.append((method, pred, gold[qid]))
    print(f"[llm_judge] jobs={len(jobs)} output={out}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with out.open("a", encoding="utf-8") as f:
        for i, (method, pred, g) in enumerate(jobs, 1):
            prompt = PROMPT.format(
                question=g.get("question", pred.get("question", "")),
                gold_answer=compact(g.get("gold_answer", ""), 1600),
                gold_evidence=compact(g.get("gold_evidence", []), 2200),
                answerable=g.get("answerable", ""),
                method=method,
                answer=compact(pred.get("answer", ""), 2000),
                pred_answerable=pred.get("pred_answerable", ""),
                evidence=evidence(pred, a.max_evidence_chars),
            )
            try:
                raw = llm.chat_sync(prompt, system_prompt=SYSTEM, chat_history=[])
                judge = normalize(extract_json(raw))
                status = "ok"
            except Exception as exc:
                judge = normalize({"rationale": str(exc)})
                status = "failed"
            row = {
                "method": method,
                "question_id": pred.get("question_id", ""),
                "paper_id": pred.get("paper_id", ""),
                "question_type": g.get("question_type", ""),
                "answerable": g.get("answerable", None),
                "pred_answerable": pred.get("pred_answerable", None),
                "latency_seconds": pred.get("latency_seconds", 0),
                "judge_status": status,
                **judge,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            avg = (time.time() - start) / i
            print(f"[llm_judge] {i}/{len(jobs)} {method} {row['question_id']} avg={avg:.1f}s eta={(len(jobs)-i)*avg/60:.1f}m", flush=True)
            if a.sleep:
                time.sleep(a.sleep)
    summarize(rows, summary)
    print(f"Wrote judgments to {out}")
    print(f"Wrote summary to {summary}")


if __name__ == "__main__":
    main()

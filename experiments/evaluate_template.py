"""
Create a manual evaluation CSV template from prediction JSONL.

The CSV includes empty score columns for human annotation:
- correctness_score
- completeness_score
- faithfulness_score
- relevance_score
- readability_score
- hallucination_flag
- notes
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import read_jsonl


FIELDNAMES = [
    "question_id",
    "paper_id",
    "method",
    "question",
    "answerable",
    "pred_answerable",
    "route_type",
    "answer",
    "evidence_summary",
    "reasoning_paths",
    "reasoning_chains",
    "source_chunks_preview",
    "sufficiency_score",
    "sufficiency_label",
    "consistency_score",
    "evidence_coverage",
    "confidence",
    "warnings",
    "error",
    "correctness_score",
    "completeness_score",
    "faithfulness_score",
    "relevance_score",
    "readability_score",
    "hallucination_flag",
    "chain_quality_score",
    "sufficiency_judgment_score",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create manual evaluation CSV template.")
    parser.add_argument("--predictions", required=True, help="Prediction JSONL path.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    return parser.parse_args()


def compact(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(compact(v) for v in value[:5])
    if isinstance(value, dict):
        return "; ".join(f"{k}={compact(v)}" for k, v in value.items())
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text[:3000]


def to_eval_row(pred: Dict) -> Dict:
    chunks = pred.get("source_chunks") or []
    preview = []
    for chunk in chunks[:3]:
        preview.append(str(chunk)[:500])
    return {
        "question_id": pred.get("question_id", ""),
        "paper_id": pred.get("paper_id", ""),
        "method": pred.get("method", ""),
        "question": pred.get("question", ""),
        "answerable": pred.get("answerable", ""),
        "pred_answerable": pred.get("pred_answerable", ""),
        "route_type": pred.get("route_type", ""),
        "answer": compact(pred.get("answer", "")),
        "evidence_summary": compact(pred.get("evidence_summary", [])),
        "reasoning_paths": compact(pred.get("reasoning_paths", [])),
        "reasoning_chains": compact(pred.get("reasoning_chains", [])),
        "source_chunks_preview": compact(preview),
        "sufficiency_score": pred.get("sufficiency_score", ""),
        "sufficiency_label": pred.get("sufficiency_label", ""),
        "consistency_score": pred.get("consistency_score", ""),
        "evidence_coverage": pred.get("evidence_coverage", ""),
        "confidence": pred.get("confidence", ""),
        "warnings": compact(pred.get("warnings", [])),
        "error": pred.get("error", ""),
        "correctness_score": "",
        "completeness_score": "",
        "faithfulness_score": "",
        "relevance_score": "",
        "readability_score": "",
        "hallucination_flag": "",
        "chain_quality_score": "",
        "sufficiency_judgment_score": "",
        "notes": "",
    }


def main() -> None:
    args = parse_args()
    input_path = PROJECT_ROOT / args.predictions if not os.path.isabs(args.predictions) else Path(args.predictions)
    output_path = PROJECT_ROOT / args.output if not os.path.isabs(args.output) else Path(args.output)
    predictions = read_jsonl(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for pred in predictions:
            writer.writerow(to_eval_row(pred))

    print(f"Wrote evaluation template for {len(predictions)} predictions to {output_path}")


if __name__ == "__main__":
    main()

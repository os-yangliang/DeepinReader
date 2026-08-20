"""失败案例采样与对比分析。

Selects representative cases where CE-RAG and a baseline differ significantly,
and writes a Markdown report with question, gold answer, predictions, evidence,
and reasoning chains.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import read_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate case study report.")
    parser.add_argument("--dataset", required=True, help="Gold dataset JSONL.")
    parser.add_argument("--ce-rag", required=True, help="CE-RAG predictions JSONL.")
    parser.add_argument("--baseline", required=True, help="Baseline predictions JSONL.")
    parser.add_argument("--baseline-name", default="naive_rag", help="Baseline method name.")
    parser.add_argument("--metric", default="correctness_score", help="Metric for scoring (from judge output).")
    parser.add_argument("--output", default="experiments/outputs/case_study.md", help="Output Markdown.")
    parser.add_argument("--max-cases", type=int, default=5, help="Max cases per category.")
    return parser.parse_args()


def load_map(path: Path) -> Dict[str, Dict[str, Any]]:
    return {row["question_id"]: row for row in read_jsonl(path)}


def compact(text: str, max_len: int = 600) -> str:
    text = " ".join((text or "").split())
    return text[:max_len] + ("..." if len(text) > max_len else "")


def main() -> None:
    args = parse_args()
    gold_map = load_map(Path(args.dataset))
    ce_map = load_map(Path(args.ce_rag))
    base_map = load_map(Path(args.baseline))

    categories = {
        "ce_rag_better": [],
        "baseline_better": [],
        "both_wrong": [],
        "abstention_difference": [],
    }

    for qid in gold_map:
        if qid not in ce_map or qid not in base_map:
            continue
        gold = gold_map[qid]
        ce = ce_map[qid]
        base = base_map[qid]

        ce_score = ce.get(args.metric, 0)
        base_score = base.get(args.metric, 0)
        ce_abstain = not ce.get("pred_answerable", True)
        base_abstain = not base.get("pred_answerable", True)
        gold_abstain = not gold.get("answerable", True)

        if ce_abstain != base_abstain:
            categories["abstention_difference"].append((qid, ce_score - base_score))
        elif ce_score > base_score + 1:
            categories["ce_rag_better"].append((qid, ce_score - base_score))
        elif base_score > ce_score + 1:
            categories["baseline_better"].append((qid, base_score - ce_score))
        elif ce_score <= 2 and base_score <= 2:
            categories["both_wrong"].append((qid, 0))

    lines = ["# CE-RAG 案例研究\n"]

    for cat, items in categories.items():
        lines.append(f"\n## {cat}\n")
        # 按分数差排序，取前 max_cases
        items.sort(key=lambda x: abs(x[1]), reverse=True)
        for idx, (qid, diff) in enumerate(items[:args.max_cases], start=1):
            gold = gold_map[qid]
            ce = ce_map[qid]
            base = base_map[qid]
            lines.append(f"\n### 案例 {idx}：{qid}\n")
            lines.append(f"**问题类型**: {gold.get('question_type', 'unknown')}\n")
            lines.append(f"**问题**: {gold.get('question', '')}\n")
            lines.append(f"**标准答案**: {compact(gold.get('gold_answer', ''))}\n")
            lines.append(f"**是否可答（gold）**: {gold.get('answerable', True)}\n")
            lines.append(f"\n**CE-RAG** (score={ce.get(args.metric, 'N/A')}):")
            lines.append(f"\n{compact(ce.get('answer', ''))}\n")
            if ce.get("sufficiency_label"):
                lines.append(f"- 充分性: {ce.get('sufficiency_label')} ({ce.get('sufficiency_score')})")
            if ce.get("reasoning_chains"):
                lines.append(f"- 推理链: {compact(str(ce.get('reasoning_chains')))}")
            lines.append(f"\n**{args.baseline_name}** (score={base.get(args.metric, 'N/A')}):")
            lines.append(f"\n{compact(base.get('answer', ''))}\n")
            lines.append("---\n")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[case_study] wrote report to {output_path}")


if __name__ == "__main__":
    main()

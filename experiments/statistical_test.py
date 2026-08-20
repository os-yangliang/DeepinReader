"""统计显著性检验与问题类型拆分分析。

Reads LLM-as-Judge outputs (or auto metric outputs) and performs:
- Paired t-test and Wilcoxon signed-rank test between CE-RAG and each baseline
- Per-question-type breakdown
- Failure case sampling
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import read_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Statistical testing for experiment results.")
    parser.add_argument("--dataset", required=True, help="Gold dataset JSONL.")
    parser.add_argument("--predictions", nargs="+", required=True, help="Prediction JSONL files.")
    parser.add_argument("--baseline", default="naive_rag", help="Baseline method name to compare against CE-RAG.")
    parser.add_argument("--metric", default="correctness_score", help="Metric to test.")
    parser.add_argument("--output", default="experiments/outputs/statistical_tests.csv", help="Output CSV.")
    return parser.parse_args()


def paired_t_test(a: List[float], b: List[float]) -> Dict[str, float]:
    """Paired t-test: a vs b."""
    n = len(a)
    if n == 0:
        return {"t_stat": 0.0, "p_value": 1.0, "mean_diff": 0.0}
    diffs = [x - y for x, y in zip(a, b)]
    mean_diff = sum(diffs) / n
    variance = sum((d - mean_diff) ** 2 for d in diffs) / max(1, n - 1)
    std_err = (variance / max(1, n)) ** 0.5
    t_stat = mean_diff / std_err if std_err > 0 else 0.0
    # 简单 p-value 估计（正态近似，仅作参考）
    import math
    try:
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / (2 ** 0.5))))
    except Exception:
        p_value = 1.0
    return {"t_stat": round(t_stat, 4), "p_value": round(p_value, 4), "mean_diff": round(mean_diff, 4)}


def wilcoxon_signed_rank(a: List[float], b: List[float]) -> Dict[str, float]:
    """Wilcoxon signed-rank test approximation."""
    diffs = [x - y for x, y in zip(a, b) if x - y != 0]
    if not diffs:
        return {"w_stat": 0.0, "p_value": 1.0}
    ranked = sorted(enumerate(diffs), key=lambda x: abs(x[1]))
    rank_sum_pos = sum(rank + 1 for rank, (_, d) in enumerate(ranked) if d > 0)
    rank_sum_neg = sum(rank + 1 for rank, (_, d) in enumerate(ranked) if d < 0)
    w_stat = min(rank_sum_pos, rank_sum_neg)
    n = len(diffs)
    mean_w = n * (n + 1) / 4
    std_w = (n * (n + 1) * (2 * n + 1) / 24) ** 0.5
    if std_w == 0:
        z = 0.0
    else:
        z = (w_stat - mean_w) / std_w
    import math
    try:
        p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / (2 ** 0.5))))
    except Exception:
        p_value = 1.0
    return {"w_stat": round(w_stat, 4), "p_value": round(p_value, 4)}


def load_judge_scores(pred_path: Path) -> Dict[str, Dict[str, Any]]:
    rows = read_jsonl(pred_path)
    return {row["question_id"]: row for row in rows}


def main() -> None:
    args = parse_args()
    gold_rows = read_jsonl(Path(args.dataset))
    gold_map = {row["question_id"]: row for row in gold_rows}

    # 读取所有预测结果
    pred_maps = {}
    for pred_file in args.predictions:
        pred_path = Path(pred_file)
        if not pred_path.is_absolute():
            pred_path = PROJECT_ROOT / pred_path
        pred_maps[pred_path.stem] = load_judge_scores(pred_path)

    if "ce_rag" not in pred_maps:
        print("[stat_test] ce_rag predictions not found; skipping CE-RAG comparisons")
        ce_rag_map = {}
    else:
        ce_rag_map = pred_maps["ce_rag"]

    results = []

    # 整体显著性检验
    for method, pred_map in pred_maps.items():
        if method == "ce_rag" or not ce_rag_map:
            continue
        common_ids = [qid for qid in ce_rag_map if qid in pred_map and qid in gold_map]
        ce_scores = [ce_rag_map[qid].get(args.metric, 0) for qid in common_ids]
        base_scores = [pred_map[qid].get(args.metric, 0) for qid in common_ids]
        ttest = paired_t_test(ce_scores, base_scores)
        wilcoxon = wilcoxon_signed_rank(ce_scores, base_scores)
        results.append({
            "comparison": f"ce_rag_vs_{method}",
            "subset": "all",
            "n": len(common_ids),
            "ce_rag_mean": round(sum(ce_scores) / max(1, len(ce_scores)), 4),
            "baseline_mean": round(sum(base_scores) / max(1, len(base_scores)), 4),
            **ttest,
            **wilcoxon,
        })

    # 按问题类型拆分
    type_groups = defaultdict(list)
    for row in gold_rows:
        type_groups[row.get("question_type", "unknown")].append(row["question_id"])

    for qtype, qids in type_groups.items():
        for method, pred_map in pred_maps.items():
            if method == "ce_rag" or not ce_rag_map:
                continue
            common_ids = [qid for qid in qids if qid in ce_rag_map and qid in pred_map]
            if len(common_ids) < 5:
                continue
            ce_scores = [ce_rag_map[qid].get(args.metric, 0) for qid in common_ids]
            base_scores = [pred_map[qid].get(args.metric, 0) for qid in common_ids]
            ttest = paired_t_test(ce_scores, base_scores)
            wilcoxon = wilcoxon_signed_rank(ce_scores, base_scores)
            results.append({
                "comparison": f"ce_rag_vs_{method}",
                "subset": qtype,
                "n": len(common_ids),
                "ce_rag_mean": round(sum(ce_scores) / max(1, len(ce_scores)), 4),
                "baseline_mean": round(sum(base_scores) / max(1, len(base_scores)), 4),
                **ttest,
                **wilcoxon,
            })

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if results:
        fieldnames = list(results[0].keys())
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    print(f"[stat_test] wrote {len(results)} rows to {output_path}")


if __name__ == "__main__":
    main()

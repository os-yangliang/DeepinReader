"""顺序运行 CE-RAG 主实验与所有 baseline / 消融实验。

要求：论文已预索引（batch_index_papers.py），各 runner 会自动复用已存在的
ChromaDB collection，从而避免重复 parse_and_index。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET = "experiments/data/qa_dataset.papers300.gold.jsonl"

METHODS: List[Tuple[str, str]] = [
    ("ce_rag", "experiments/run_ce_rag.py"),
    ("naive_rag", "experiments/run_naive_rag.py"),
    ("hybrid_rag", "experiments/run_hybrid_rag.py"),
    ("longcontext", "experiments/run_longcontext.py"),
    ("graphrag", "experiments/run_graphrag_baseline.py"),
    ("paperqa", "experiments/run_paperqa_baseline.py"),
    ("selfrag", "experiments/run_selfrag_baseline.py"),
]

ABLATION_VARIANTS = [
    "ce_rag_full",
    "w/o_routing",
    "w/o_graph",
    "w/o_chain",
    "w/o_sufficiency",
    "w/o_verification",
    "w/o_iterative",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all CE-RAG experiments sequentially.")
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--methods", nargs="+", default=None, help="Subset of methods to run.")
    parser.add_argument("--output-suffix", default="", help="Suffix appended to output filenames (e.g. 'subset50').")
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--skip-baselines", action="store_true")
    return parser.parse_args()


def run_method(name: str, script: str, dataset: str, suffix: str = "") -> None:
    base = f"{name}_{suffix}" if suffix else name
    output = f"experiments/outputs/{base}_results.jsonl"
    cmd = [sys.executable, script, "--dataset", dataset, "--output", output]
    print(f"\n[run_all] ===== Running {name} =====")
    print(f"[run_all] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    print(f"[run_all] {name} done -> {output}")


def run_ablation(variant: str, dataset: str, suffix: str = "") -> None:
    base = f"{variant.replace('/', '_')}_{suffix}" if suffix else variant.replace('/', '_')
    output = f"experiments/outputs/ablation_{base}_results.jsonl"
    cmd = [
        sys.executable, "experiments/run_ablation.py",
        "--dataset", dataset,
        "--variants", variant,
        "--output-dir", "experiments/outputs",
    ]
    print(f"\n[run_all] ===== Running ablation {variant} =====")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    print(f"[run_all] ablation {variant} done -> {output}")


def main() -> None:
    args = parse_args()
    dataset = args.dataset

    methods = METHODS
    if args.methods:
        methods = [(n, s) for n, s in methods if n in args.methods]

    if not args.skip_baselines:
        for name, script in methods:
            run_method(name, script, dataset, args.output_suffix)

    if not args.skip_ablation:
        for variant in ABLATION_VARIANTS:
            run_ablation(variant, dataset, args.output_suffix)

    print("\n[run_all] all requested experiments completed.")


if __name__ == "__main__":
    main()

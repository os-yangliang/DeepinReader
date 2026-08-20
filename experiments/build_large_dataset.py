"""Build the expanded CE-RAG QA dataset (200+ papers / 1200+ QA).

Steps:
1. (Assume papers are already in experiments/data/papers, including arXiv downloads.)
2. Rename any arXiv-style PDFs to paper_XXX.pdf.
3. Generate QA templates.
4. AI-annotate gold answers and evidence.
5. Merge with existing gold dataset if provided.

Usage:
    python experiments/build_large_dataset.py \
        --papers-dir experiments/data/papers \
        --output experiments/data/qa_dataset.papers200.gold.jsonl \
        --merge-existing experiments/data/qa_dataset.papers53.gold.jsonl
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build expanded CE-RAG QA dataset.")
    parser.add_argument("--papers-dir", default="experiments/data/papers", help="Directory with PDFs.")
    parser.add_argument("--template-output", default="experiments/data/qa_dataset.papers200.template.jsonl")
    parser.add_argument("--annotated-output", default="experiments/data/qa_dataset.papers200.ai.jsonl")
    parser.add_argument("--output", default="experiments/data/qa_dataset.papers200.gold.jsonl")
    parser.add_argument("--merge-existing", default="experiments/data/qa_dataset.papers53.gold.jsonl", help="Optional existing gold dataset to merge.")
    parser.add_argument("--questions-per-paper", type=int, default=6)
    parser.add_argument("--skip-rename", action="store_true", help="Skip renaming arXiv PDFs.")
    parser.add_argument("--skip-template", action="store_true", help="Skip template generation.")
    parser.add_argument("--skip-annotate", action="store_true", help="Skip AI annotation.")
    return parser.parse_args()


def run_python(script_args: List[str]) -> None:
    cmd = [sys.executable] + script_args
    print(f"[build_large_dataset] running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    args = parse_args()
    papers_dir = Path(args.papers_dir)
    if not papers_dir.is_absolute():
        papers_dir = PROJECT_ROOT / papers_dir

    if not args.skip_rename:
        run_python(["experiments/rename_arxiv_papers.py", "--papers-dir", str(papers_dir)])

    if not args.skip_template:
        run_python([
            "experiments/build_qa_template_from_papers.py",
            "--papers-dir", str(papers_dir),
            "--output", args.template_output,
            "--questions-per-paper", str(args.questions_per_paper),
        ])

    if not args.skip_annotate:
        run_python([
            "experiments/auto_annotate_dataset.py",
            "--template", args.template_output,
            "--output", args.annotated_output,
            "--raw-output", "experiments/outputs/ai_annotation_papers200_raw.jsonl",
            "--context-chars", "10000",
            "--chunks-per-question", "6",
        ])

    # 合并 AI 标注结果与现有 gold 数据
    ai_rows = read_jsonl(Path(args.annotated_output)) if not args.skip_annotate else []
    merged = []
    seen_ids = set()
    for row in ai_rows:
        # 只保留成功标注的样本
        if row.get("gold_answer"):
            merged.append(row)
            seen_ids.add(row["question_id"])

    if args.merge_existing:
        existing_rows = read_jsonl(Path(args.merge_existing))
        for row in existing_rows:
            if row["question_id"] not in seen_ids:
                merged.append(row)
                seen_ids.add(row["question_id"])

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    write_jsonl(output_path, merged)
    print(f"[build_large_dataset] wrote {len(merged)} samples to {output_path}")

    # 统计
    from collections import Counter
    print(f"[build_large_dataset] papers: {len(set(r['paper_id'] for r in merged))}")
    print(f"[build_large_dataset] question types: {Counter(r.get('question_type', 'unknown') for r in merged)}")
    print(f"[build_large_dataset] answerable: {Counter(r.get('answerable', True) for r in merged)}")


if __name__ == "__main__":
    main()

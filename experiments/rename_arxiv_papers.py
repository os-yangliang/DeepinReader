"""Rename arXiv-style PDFs to paper_XXX.pdf sequence, starting after existing paper_*.pdfs.

Usage:
    python experiments/rename_arxiv_papers.py --papers-dir experiments/data/papers --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename arXiv PDFs to paper_XXX.pdf.")
    parser.add_argument("--papers-dir", default="experiments/data/papers", help="Directory with PDFs.")
    parser.add_argument("--dry-run", action="store_true", help="Print renames without executing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = Path(args.papers_dir)
    if not papers_dir.is_absolute():
        papers_dir = PROJECT_ROOT / papers_dir

    existing = sorted(papers_dir.glob("paper_*.pdf"))
    max_idx = 0
    for p in existing:
        m = re.match(r"paper_(\d+)\.pdf", p.name)
        if m:
            max_idx = max(max_idx, int(m.group(1)))

    arxiv_pattern = re.compile(r"^\d{4}\.\d+(?:v\d+)?\.pdf$")
    arxiv_pdfs = sorted([p for p in papers_dir.glob("*.pdf") if arxiv_pattern.match(p.name)])

    next_idx = max_idx + 1
    print(f"[rename] existing paper_*.pdf max index={max_idx}, {len(arxiv_pdfs)} arXiv PDFs to rename")

    for old_path in arxiv_pdfs:
        new_name = f"paper_{next_idx:03d}.pdf"
        new_path = papers_dir / new_name
        print(f"[rename] {old_path.name} -> {new_name}")
        if not args.dry_run:
            old_path.rename(new_path)
        next_idx += 1


if __name__ == "__main__":
    main()

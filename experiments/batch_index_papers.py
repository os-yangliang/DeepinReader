"""一次性预索引实验中所有论文 PDF，供后续各 runner 复用。

Usage:
    python experiments/batch_index_papers.py --papers-dir experiments/data/papers --paper-limit 300
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.coordinator import PaperReaderCoordinator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-index all paper PDFs for experiments.")
    parser.add_argument("--papers-dir", default="experiments/data/papers")
    parser.add_argument("--paper-limit", type=int, default=0)
    parser.add_argument("--output", default="experiments/outputs/batch_index_log.jsonl")
    parser.add_argument("--resume", action="store_true", help="Skip papers already present in existing log.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    papers_dir = Path(args.papers_dir)
    if not papers_dir.is_absolute():
        papers_dir = PROJECT_ROOT / papers_dir

    papers = sorted(papers_dir.glob("paper_*.pdf"))
    if args.paper_limit:
        papers = papers[: args.paper_limit]
    if not papers:
        raise FileNotFoundError(f"No papers found in {papers_dir}")

    # 如果 resume，读取已完成的 paper_id
    completed: set = set()
    output_path = PROJECT_ROOT / args.output
    if args.resume and output_path.exists():
        try:
            with output_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("status") == "ok":
                        completed.add(row.get("paper_id"))
            print(f"[index] resume: {len(completed)} papers already indexed", flush=True)
        except Exception as exc:
            print(f"[index] failed to read existing log: {exc}", flush=True)

    coordinator = PaperReaderCoordinator(require_llm=True)
    log_lines: List[str] = []
    start_time = time.time()

    for idx, paper_path in enumerate(papers, start=1):
        if paper_path.stem in completed:
            print(f"[index] {idx}/{len(papers)} {paper_path.name} skipped (already indexed)", flush=True)
            continue

        paper_start = time.time()
        try:
            with paper_path.open("rb") as f:
                file_bytes = f.read()
            info = coordinator.parse_and_index(file_bytes, paper_path.name)
            elapsed = time.time() - paper_start
            print(f"[index] {idx}/{len(papers)} {paper_path.name} {info['title'][:50]}... pages={info['page_count']} elapsed={elapsed:.1f}s", flush=True)
            log_lines.append(f"{{\"paper_id\": \"{paper_path.stem}\", \"status\": \"ok\", \"document_id\": \"{info['document_id']}\", \"title\": {repr(info['title'])!r}, \"elapsed\": {elapsed:.2f}}}")
        except Exception as exc:
            elapsed = time.time() - paper_start
            print(f"[index] {idx}/{len(papers)} {paper_path.name} FAILED: {exc} elapsed={elapsed:.1f}s", flush=True)
            log_lines.append(f"{{\"paper_id\": \"{paper_path.stem}\", \"status\": \"failed\", \"error\": {repr(str(exc))!r}, \"elapsed\": {elapsed:.2f}}}")

    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"[index] done. total={len(papers)} elapsed={time.time()-start_time:.1f}s log={output_path}")


if __name__ == "__main__":
    main()

"""从 arXiv 下载论文 PDF，用于扩展 CE-RAG 实验数据集。

Usage:
    python experiments/download_papers.py \
        --categories cs.CL cs.LG cs.AI cs.CV cs.SE cs.DB \
        --max-per-category 25 \
        --output-dir experiments/data/papers
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Set
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf/{id}.pdf"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download papers from arXiv.")
    parser.add_argument("--categories", nargs="+", default=["cs.CL", "cs.LG", "cs.AI", "cs.CV", "cs.SE", "cs.DB"], help="arXiv categories")
    parser.add_argument("--max-per-category", type=int, default=25, help="Max papers per category")
    parser.add_argument("--output-dir", default="experiments/data/papers", help="Where to save PDFs")
    parser.add_argument("--resume", action="store_true", help="Skip existing PDFs")
    parser.add_argument("--sleep", type=float, default=5.0, help="Seconds between arXiv API requests")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def fetch_url(url: str, timeout: int = 60, retries: int = 5) -> bytes:
    """带重试的 URL 获取。"""
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CE-RAG-dataset-builder/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            wait = min(2 ** attempt * 3, 60)
            print(f"[arxiv] fetch retry {attempt + 1}/{retries} for {url}: {exc} (sleep {wait}s)", flush=True)
            time.sleep(wait)
    raise last_exc or RuntimeError(f"Failed to fetch {url}")


def fetch_arxiv_ids(category: str, max_results: int) -> List[str]:
    """使用 arXiv API 搜索论文 ID，带重试。"""
    query = f"cat:{category}"
    ids = []
    batch = 100
    for start in range(0, max_results, batch):
        page_size = min(batch, max_results - start)
        url = (
            f"{ARXIV_API}?search_query={urllib.parse.quote(query)}"
            f"&start={start}&max_results={page_size}&sortBy=submittedDate&sortOrder=descending"
        )
        print(f"[arxiv] fetching {category} start={start} size={page_size}", flush=True)
        xml_bytes = fetch_url(url, timeout=60, retries=5)
        xml = xml_bytes.decode("utf-8")
        root = ET.fromstring(xml)
        for entry in root.findall("atom:entry", NS):
            id_url = entry.find("atom:id", NS)
            if id_url is None:
                continue
            arxiv_id = id_url.text.split("/")[-1]
            if "v" in arxiv_id:
                arxiv_id = arxiv_id.split("v")[0]
            ids.append(arxiv_id)
        time.sleep(3)
    return ids


def download_pdf(arxiv_id: str, output_dir: Path, resume: bool) -> bool:
    pdf_path = output_dir / f"{arxiv_id}.pdf"
    if resume and pdf_path.exists():
        return True
    url = ARXIV_PDF.format(id=arxiv_id)
    try:
        data = fetch_url(url, timeout=120, retries=5)
        if len(data) < 1000:
            return False
        pdf_path.write_bytes(data)
        return True
    except Exception as e:
        print(f"[arxiv] failed to download {arxiv_id}: {e}", flush=True)
        return False


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 统计当前已有 paper_*.pdf 数量
    existing_papers = sorted(output_dir.glob("paper_*.pdf"))
    print(f"[arxiv] existing papers: {len(existing_papers)}", flush=True)

    all_ids: Set[str] = set()
    for category in args.categories:
        ids = fetch_arxiv_ids(category, args.max_per_category * 2)
        unique_ids = list(dict.fromkeys(ids))
        random.shuffle(unique_ids)
        selected = unique_ids[: args.max_per_category]
        all_ids.update(selected)
        print(f"[arxiv] category={category} selected={len(selected)}", flush=True)
        time.sleep(args.sleep)

    print(f"[arxiv] total unique papers to download: {len(all_ids)}", flush=True)
    success = 0
    for idx, arxiv_id in enumerate(sorted(all_ids), start=1):
        if download_pdf(arxiv_id, output_dir, args.resume):
            success += 1
            print(f"[arxiv] {idx}/{len(all_ids)} downloaded {arxiv_id}", flush=True)
        else:
            print(f"[arxiv] {idx}/{len(all_ids)} failed {arxiv_id}", flush=True)
        time.sleep(args.sleep)

    print(f"[arxiv] done. success={success}/{len(all_ids)} saved to {output_dir}")


if __name__ == "__main__":
    main()

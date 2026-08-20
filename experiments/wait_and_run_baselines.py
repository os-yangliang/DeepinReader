"""等待预索引完成后，顺序运行除 longcontext 外的所有 baseline / CE-RAG 主实验。

该脚本设计为后台任务运行：它会轮询 paper_profiles/ 目录与 batch_index 日志，
当检测到 300 篇论文索引完成后，自动调用 run_all_methods.py 顺序执行指定方法。
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.chroma_client import get_chroma_client

DATASET = "experiments/data/qa_dataset.papers300.gold.jsonl"
INDEX_LOG = PROJECT_ROOT / "experiments" / "outputs" / "batch_index_papers300_log.jsonl"
PROFILE_DIR = PROJECT_ROOT / "paper_profiles"
POLL_INTERVAL_SECONDS = 60


def count_profiles() -> int:
    return len(list(PROFILE_DIR.glob("*.json")))


def count_collections() -> int:
    try:
        return len(get_chroma_client().list_collections())
    except Exception:
        return 0


def index_done() -> bool:
    """通过日志文件或 profile 数量判断索引是否完成。"""
    if INDEX_LOG.exists():
        try:
            with INDEX_LOG.open("r", encoding="utf-8") as f:
                text = f.read()
            if "[index] done" in text:
                return True
        except Exception:
            pass
    return count_profiles() >= 300


def main() -> None:
    print("[wait_and_run] waiting for batch indexing to complete...", flush=True)
    while not index_done():
        profiles = count_profiles()
        collections = count_collections()
        print(
            f"[wait_and_run] indexing not ready yet: profiles={profiles}/300 collections={collections}, "
            f"sleep {POLL_INTERVAL_SECONDS}s",
            flush=True,
        )
        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"[wait_and_run] indexing ready (profiles={count_profiles()}). Starting baselines.", flush=True)

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "experiments" / "run_all_methods.py"),
        "--dataset", DATASET,
        "--skip-ablation",
        "--methods", "ce_rag", "naive_rag", "hybrid_rag", "graphrag", "paperqa", "selfrag",
    ]
    print(f"[wait_and_run] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
    print("[wait_and_run] all baselines finished.", flush=True)


if __name__ == "__main__":
    main()

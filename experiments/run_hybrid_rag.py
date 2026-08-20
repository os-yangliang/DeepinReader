"""
Hybrid RAG baseline runner.

Pipeline:
1. Parse and index the paper with existing parser/vector store.
2. Retrieve top-k chunks through VectorStoreService.get_retriever(), which uses
   vector + BM25 when the BM25 index is available.
3. Ask the LLM to answer using retrieved chunks only.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.coordinator import PaperReaderCoordinator
from experiments.index_utils import load_paper_reuse
from experiments.schema import ExperimentOutput, Timer, load_samples, output_to_dict, write_jsonl


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def log_progress(method: str, done: int, total: int, start_time: float, current: str = "") -> None:
    elapsed = time.time() - start_time
    avg = elapsed / done if done else 0.0
    eta = avg * (total - done) if done else 0.0
    suffix = f" | {current}" if current else ""
    print(
        f"[{method}] progress {done}/{total} ({done / total * 100:.1f}%) "
        f"elapsed={format_duration(elapsed)} avg={avg:.1f}s ETA={format_duration(eta)}{suffix}",
        flush=True,
    )


HYBRID_RAG_PROMPT = """你是学术论文问答助手。请只根据给定的混合检索结果回答问题。
如果检索结果中没有足够信息，请明确回答“根据当前证据不足以回答”。

问题：
{question}

检索结果：
{context}

请用中文回答，保持简洁、准确，并避免引入检索结果之外的信息。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hybrid RAG baseline experiments.")
    parser.add_argument("--dataset", default="experiments/data/qa_dataset.sample.jsonl", help="Input QA dataset JSONL.")
    parser.add_argument("--output", default="experiments/outputs/hybrid_rag_results.jsonl", help="Output predictions JSONL.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve.")
    parser.add_argument("--skip-missing-papers", action="store_true", help="Write error rows instead of failing on missing PDFs.")
    return parser.parse_args()


def load_paper(coordinator: PaperReaderCoordinator, paper_path: str) -> Dict:
    return load_paper_reuse(coordinator, paper_path)


def retrieve_hybrid(coordinator: PaperReaderCoordinator, question: str, top_k: int):
    retriever = coordinator.vector_store.get_retriever(k=top_k)
    if hasattr(retriever, "invoke"):
        return retriever.invoke(question)
    return retriever.get_relevant_documents(question)


def main() -> None:
    args = parse_args()
    samples = load_samples(PROJECT_ROOT / args.dataset if not os.path.isabs(args.dataset) else args.dataset)

    by_paper: Dict[str, List] = defaultdict(list)
    for sample in samples:
        by_paper[sample.paper_id].append(sample)

    coordinator = PaperReaderCoordinator(require_llm=True)
    outputs: List[dict] = []
    total_questions = len(samples)
    completed_questions = 0
    run_start = time.time()
    print(f"[hybrid_rag] Starting run: papers={len(by_paper)} questions={total_questions}", flush=True)

    for paper_index, (paper_id, paper_samples) in enumerate(by_paper.items(), start=1):
        first = paper_samples[0]
        paper_start = time.time()
        print(
            f"[hybrid_rag] Loading paper {paper_index}/{len(by_paper)}: {paper_id} "
            f"questions={len(paper_samples)}",
            flush=True,
        )
        resolved_path = PROJECT_ROOT / first.paper_path if not os.path.isabs(first.paper_path) else Path(first.paper_path)

        if not resolved_path.exists():
            if not args.skip_missing_papers:
                raise FileNotFoundError(f"Paper not found for {paper_id}: {resolved_path}")
            for sample in paper_samples:
                outputs.append(output_to_dict(ExperimentOutput(
                    question_id=sample.question_id,
                    paper_id=sample.paper_id,
                    method="hybrid_rag",
                    question=sample.question,
                    answerable=sample.answerable,
                    error=f"paper_not_found: {resolved_path}",
                )))
            continue

        try:
            info = load_paper(coordinator, first.paper_path)
            reused = info.get("reused", False)
        except Exception as exc:
            for sample in paper_samples:
                outputs.append(output_to_dict(ExperimentOutput(
                    question_id=sample.question_id,
                    paper_id=sample.paper_id,
                    method="hybrid_rag",
                    question=sample.question,
                    answerable=sample.answerable,
                    error=f"paper_load_failed: {exc}",
                )))
            continue

        action = "Reused index" if reused else "Indexed"
        print(f"[hybrid_rag] {action} paper {paper_id} in {format_duration(time.time() - paper_start)}", flush=True)

        for question_index, sample in enumerate(paper_samples, start=1):
            with Timer() as timer:
                try:
                    docs = retrieve_hybrid(coordinator, sample.question, args.top_k)
                    chunks = [doc.page_content for doc in docs[:args.top_k]]
                    context = "\n\n---\n\n".join(chunks)
                    prompt = HYBRID_RAG_PROMPT.format(question=sample.question, context=context)
                    answer = coordinator.llm_service.chat_sync(user_message=prompt, chat_history=[])
                    pred_answerable = "不足" not in answer and "无法" not in answer
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="hybrid_rag",
                        question=sample.question,
                        answer=answer,
                        answerable=sample.answerable,
                        pred_answerable=pred_answerable,
                        route_type="baseline",
                        source_chunks=chunks,
                        confidence=0.0,
                        latency_seconds=time.perf_counter() - timer.start,
                    )
                except Exception as exc:
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="hybrid_rag",
                        question=sample.question,
                        answerable=sample.answerable,
                        error=str(exc),
                        latency_seconds=time.perf_counter() - timer.start,
                    )
            outputs.append(output_to_dict(output))
            completed_questions += 1
            log_progress(
                "hybrid_rag",
                completed_questions,
                total_questions,
                run_start,
                current=f"paper={paper_id} q={question_index}/{len(paper_samples)} latency={output.latency_seconds:.1f}s",
            )

    output_path = PROJECT_ROOT / args.output if not os.path.isabs(args.output) else Path(args.output)
    write_jsonl(output_path, outputs)
    print(f"Wrote {len(outputs)} Hybrid RAG predictions to {output_path}")


if __name__ == "__main__":
    main()

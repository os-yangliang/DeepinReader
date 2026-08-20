"""GraphRAG-style baseline runner.

Builds the scholarly object graph but retrieves plain graph nodes (claims,
evidence, results) without the CE-RAG reasoning-chain scoring, sufficiency
estimation, or verifier. This isolates the value of the graph representation
from the CE-RAG retrieval and verification components.
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
from experiments.index_utils import collection_exists, compute_doc_id
from experiments.schema import ExperimentOutput, Timer, load_samples, output_to_dict, write_jsonl
from services.document_parser import DocumentParser
from services.paper_schema import Claim, Evidence, PaperProfile, ResultItem


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


GRAPHRAG_PROMPT = """你是学术论文问答助手。请根据给定的论文图节点信息（主张、证据、实验结果）回答问题。
如果信息不足，请明确回答“根据当前证据不足以回答”。

问题：
{question}

图节点信息：
{context}

请用中文回答，保持简洁、准确。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GraphRAG-style baseline experiments.")
    parser.add_argument("--dataset", default="experiments/data/qa_dataset.sample.jsonl", help="Input QA dataset JSONL.")
    parser.add_argument("--output", default="experiments/outputs/graphrag_results.jsonl", help="Output predictions JSONL.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of graph nodes to retrieve.")
    parser.add_argument("--skip-missing-papers", action="store_true", help="Write error rows instead of failing on missing PDFs.")
    return parser.parse_args()


def load_profile(coordinator: PaperReaderCoordinator, paper_path: str) -> PaperProfile:
    path = PROJECT_ROOT / paper_path if not os.path.isabs(paper_path) else Path(paper_path)
    with path.open("rb") as f:
        file_bytes = f.read()

    parsed = DocumentParser().parse_from_bytes(file_bytes, path.name)
    doc_id = compute_doc_id(parsed.filename, parsed.content)

    # 优先复用已持久化的 profile
    if collection_exists(doc_id):
        coordinator.vector_store.load_collection(doc_id)
        profile = coordinator.object_indexer.load_profile(doc_id)
        if profile:
            return profile

    result = coordinator.parser_agent.parse_document_from_bytes(file_bytes, path.name)
    if not result.success or not result.paper_profile:
        raise ValueError(result.error_message or "parse failed")
    return result.paper_profile


def retrieve_graph_nodes(profile: PaperProfile, question: str, top_k: int) -> List[str]:
    """简单图节点检索：按问题与节点文本的词重叠排序，返回 top-k 节点文本。"""
    q_terms = _terms(question)
    candidates = []
    for node in list(profile.claims) + list(profile.evidences) + list(profile.results):
        text = _node_text(node)
        overlap = len(q_terms & _terms(text)) / max(1, len(q_terms))
        candidates.append((overlap, text))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in candidates[:top_k]]


def _node_text(node) -> str:
    if isinstance(node, Claim):
        return f"[CLAIM] {node.text}"
    if isinstance(node, Evidence):
        return f"[EVIDENCE] {node.text}"
    if isinstance(node, ResultItem):
        return f"[RESULT] {node.text}"
    return str(node)


def _terms(text: str):
    import re
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}", text or "") if len(t.strip()) >= 2}


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
    print(f"[graphrag] Starting run: papers={len(by_paper)} questions={total_questions}", flush=True)

    for paper_index, (paper_id, paper_samples) in enumerate(by_paper.items(), start=1):
        first = paper_samples[0]
        paper_start = time.time()
        print(
            f"[graphrag] Loading paper {paper_index}/{len(by_paper)}: {paper_id} "
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
                    method="graphrag",
                    question=sample.question,
                    answerable=sample.answerable,
                    error=f"paper_not_found: {resolved_path}",
                )))
            continue

        try:
            profile = load_profile(coordinator, first.paper_path)
        except Exception as exc:
            for sample in paper_samples:
                outputs.append(output_to_dict(ExperimentOutput(
                    question_id=sample.question_id,
                    paper_id=sample.paper_id,
                    method="graphrag",
                    question=sample.question,
                    answerable=sample.answerable,
                    error=f"paper_load_failed: {exc}",
                )))
            continue

        print(f"[graphrag] Indexed paper {paper_id} in {format_duration(time.time() - paper_start)}", flush=True)

        for question_index, sample in enumerate(paper_samples, start=1):
            with Timer() as timer:
                try:
                    nodes = retrieve_graph_nodes(profile, sample.question, args.top_k)
                    context = "\n\n".join(nodes)
                    prompt = GRAPHRAG_PROMPT.format(question=sample.question, context=context)
                    answer = coordinator.llm_service.chat_sync(user_message=prompt, chat_history=[])
                    pred_answerable = "不足" not in answer and "无法" not in answer and "insufficient" not in answer.lower()
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="graphrag",
                        question=sample.question,
                        answer=answer,
                        answerable=sample.answerable,
                        pred_answerable=pred_answerable,
                        route_type="baseline",
                        source_chunks=nodes,
                        confidence=0.0,
                        latency_seconds=time.perf_counter() - timer.start,
                    )
                except Exception as exc:
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="graphrag",
                        question=sample.question,
                        answerable=sample.answerable,
                        error=str(exc),
                        latency_seconds=time.perf_counter() - timer.start,
                    )
            outputs.append(output_to_dict(output))
            completed_questions += 1
            log_progress(
                "graphrag",
                completed_questions,
                total_questions,
                run_start,
                current=f"paper={paper_id} q={question_index}/{len(paper_samples)} latency={output.latency_seconds:.1f}s",
            )

    output_path = PROJECT_ROOT / args.output if not os.path.isabs(args.output) else Path(args.output)
    write_jsonl(output_path, outputs)
    print(f"Wrote {len(outputs)} GraphRAG-style predictions to {output_path}")


if __name__ == "__main__":
    main()

"""PaperQA-style multi-step retrieval agent baseline.

Mimics the PaperQA agentic retrieval loop: generate search queries, retrieve
chunks, evaluate whether enough evidence is gathered, and answer with citations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


QUERY_GEN_PROMPT = """你是学术论文检索专家。请为以下问题生成 1-3 个检索 query，用于从论文中查找相关信息。
只输出 JSON 数组，例如：["query1", "query2"]。

问题：{question}

已检索信息摘要：
{retrieved_summary}
"""

EVIDENCE_JUDGE_PROMPT = """你是证据充分性判断专家。请判断当前检索到的信息是否足以回答问题。
只输出 JSON：{{"sufficient": true/false, "reason": "..."}}。

问题：{question}

已检索信息：
{context}
"""

ANSWER_PROMPT = """你是学术论文问答助手。请根据检索到的论文片段回答问题，并在关键事实后标注来源片段编号 [^1], [^2] 等。
如果信息不足，请明确回答“根据当前证据不足以回答”。

问题：
{question}

检索片段：
{context}

请用中文回答。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PaperQA-style baseline experiments.")
    parser.add_argument("--dataset", default="experiments/data/qa_dataset.sample.jsonl", help="Input QA dataset JSONL.")
    parser.add_argument("--output", default="experiments/outputs/paperqa_results.jsonl", help="Output predictions JSONL.")
    parser.add_argument("--top-k", type=int, default=5, help="Chunks per retrieval step.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max retrieval rounds.")
    parser.add_argument("--skip-missing-papers", action="store_true", help="Write error rows instead of failing on missing PDFs.")
    return parser.parse_args()


def load_paper(coordinator: PaperReaderCoordinator, paper_path: str) -> Dict:
    return load_paper_reuse(coordinator, paper_path)


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("无法提取 JSON")


def generate_queries(llm_service, question: str, retrieved_chunks: List[str]) -> List[str]:
    summary = "\n".join(retrieved_chunks[:3])[:1000]
    prompt = QUERY_GEN_PROMPT.format(question=question, retrieved_summary=summary)
    raw = llm_service.chat_sync(user_message=prompt, chat_history=[])
    try:
        queries = _extract_json(raw)
        if isinstance(queries, list):
            return [q for q in queries if isinstance(q, str)][:3]
        if isinstance(queries, dict) and "queries" in queries:
            return [q for q in queries["queries"] if isinstance(q, str)][:3]
    except Exception:
        pass
    return [question]


def judge_sufficient(llm_service, question: str, chunks: List[str]) -> bool:
    context = "\n\n---\n\n".join(chunks[:8])
    prompt = EVIDENCE_JUDGE_PROMPT.format(question=question, context=context)
    raw = llm_service.chat_sync(user_message=prompt, chat_history=[])
    try:
        result = _extract_json(raw)
        return bool(result.get("sufficient", False))
    except Exception:
        return len(chunks) >= 8


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
    print(f"[paperqa] Starting run: papers={len(by_paper)} questions={total_questions}", flush=True)

    for paper_index, (paper_id, paper_samples) in enumerate(by_paper.items(), start=1):
        first = paper_samples[0]
        paper_start = time.time()
        print(
            f"[paperqa] Loading paper {paper_index}/{len(by_paper)}: {paper_id} "
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
                    method="paperqa",
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
                    method="paperqa",
                    question=sample.question,
                    answerable=sample.answerable,
                    error=f"paper_load_failed: {exc}",
                )))
            continue

        action = "Reused index" if reused else "Indexed"
        print(f"[paperqa] {action} paper {paper_id} in {format_duration(time.time() - paper_start)}", flush=True)

        for question_index, sample in enumerate(paper_samples, start=1):
            with Timer() as timer:
                try:
                    retrieved_chunks: List[str] = []
                    for _ in range(args.max_rounds):
                        queries = generate_queries(coordinator.llm_service, sample.question, retrieved_chunks)
                        for query in queries:
                            docs = coordinator.vector_store.search(query, top_k=args.top_k)
                            for doc in docs:
                                content = doc.page_content
                                if content not in retrieved_chunks:
                                    retrieved_chunks.append(content)
                        if judge_sufficient(coordinator.llm_service, sample.question, retrieved_chunks):
                            break

                    context = "\n\n---\n\n".join(retrieved_chunks[:10])
                    prompt = ANSWER_PROMPT.format(question=sample.question, context=context)
                    answer = coordinator.llm_service.chat_sync(user_message=prompt, chat_history=[])
                    pred_answerable = "不足" not in answer and "无法" not in answer and "insufficient" not in answer.lower()
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="paperqa",
                        question=sample.question,
                        answer=answer,
                        answerable=sample.answerable,
                        pred_answerable=pred_answerable,
                        route_type="baseline",
                        source_chunks=retrieved_chunks[:10],
                        confidence=0.0,
                        latency_seconds=time.perf_counter() - timer.start,
                    )
                except Exception as exc:
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="paperqa",
                        question=sample.question,
                        answerable=sample.answerable,
                        error=str(exc),
                        latency_seconds=time.perf_counter() - timer.start,
                    )
            outputs.append(output_to_dict(output))
            completed_questions += 1
            log_progress(
                "paperqa",
                completed_questions,
                total_questions,
                run_start,
                current=f"paper={paper_id} q={question_index}/{len(paper_samples)} latency={output.latency_seconds:.1f}s",
            )

    output_path = PROJECT_ROOT / args.output if not os.path.isabs(args.output) else Path(args.output)
    write_jsonl(output_path, outputs)
    print(f"Wrote {len(outputs)} PaperQA-style predictions to {output_path}")


if __name__ == "__main__":
    main()

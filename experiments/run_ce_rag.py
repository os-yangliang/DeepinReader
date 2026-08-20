"""
Batch runner for CE-RAG experiments.

This script reuses the existing PaperReader coordinator and QA agent. It is a
minimal experiment entrypoint: parse/index each paper once, then answer all
questions for that paper with the current CE-RAG pipeline.
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
from experiments.schema import ExperimentOutput, Timer, load_samples, output_to_dict, read_jsonl, write_jsonl


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CE-RAG batch experiments.")
    parser.add_argument("--dataset", default="experiments/data/qa_dataset.sample.jsonl", help="Input QA dataset JSONL.")
    parser.add_argument("--output", default="experiments/outputs/ce_rag_results.jsonl", help="Output predictions JSONL.")
    parser.add_argument("--skip-missing-papers", action="store_true", help="Write error rows instead of failing on missing PDFs.")
    parser.add_argument("--resume", action="store_true", help="Only rerun questions with empty answer or error in existing output.")
    return parser.parse_args()


def _needs_rerun(row: dict) -> bool:
    """判断已有结果是否需要重跑。"""
    if row.get("error"):
        return True
    if not row.get("answer"):
        return True
    return False


def load_paper(coordinator: PaperReaderCoordinator, paper_path: str) -> Dict:
    return load_paper_reuse(coordinator, paper_path)


def main() -> None:
    args = parse_args()
    samples = load_samples(PROJECT_ROOT / args.dataset if not os.path.isabs(args.dataset) else args.dataset)
    all_qids = [s.question_id for s in samples]

    output_path = PROJECT_ROOT / args.output if not os.path.isabs(args.output) else Path(args.output)

    # 若 resume，加载已有结果并标记需要重跑或补跑的样本
    existing_rows: Dict[str, dict] = {}
    rerun_qids: set = set()
    if args.resume and output_path.exists():
        for row in read_jsonl(output_path):
            qid = row.get("question_id")
            if qid:
                existing_rows[qid] = row
                if _needs_rerun(row):
                    rerun_qids.add(qid)
        print(f"[ce_rag] resume: {len(existing_rows)} existing rows, {len(rerun_qids)} need rerun", flush=True)

    # resume 模式：输出文件存在时，跳过已有且非空的条目，仅补跑缺失/失败/空答案的条目
    do_resume = args.resume and output_path.exists()

    by_paper: Dict[str, List] = defaultdict(list)
    for sample in samples:
        if not do_resume or sample.question_id in rerun_qids or sample.question_id not in existing_rows:
            by_paper[sample.paper_id].append(sample)

    coordinator = PaperReaderCoordinator(require_llm=True)
    # 保留不需要重跑的已有结果
    result_map: Dict[str, dict] = {qid: row for qid, row in existing_rows.items() if qid not in rerun_qids}
    total_questions = sum(len(qs) for qs in by_paper.values()) if do_resume else len(samples)
    completed_questions = 0
    run_start = time.time()
    print(f"[ce_rag] Starting run: papers={len(by_paper)} questions={total_questions}", flush=True)

    for paper_index, (paper_id, paper_samples) in enumerate(by_paper.items(), start=1):
        first = paper_samples[0]
        paper_start = time.time()
        print(
            f"[ce_rag] Loading paper {paper_index}/{len(by_paper)}: {paper_id} "
            f"questions={len(paper_samples)}",
            flush=True,
        )
        paper_path = first.paper_path
        resolved_path = PROJECT_ROOT / paper_path if not os.path.isabs(paper_path) else Path(paper_path)

        if not resolved_path.exists():
            if not args.skip_missing_papers:
                raise FileNotFoundError(f"Paper not found for {paper_id}: {resolved_path}")
            for sample in paper_samples:
                result_map[sample.question_id] = output_to_dict(ExperimentOutput(
                    question_id=sample.question_id,
                    paper_id=sample.paper_id,
                    method="ce_rag",
                    question=sample.question,
                    answerable=sample.answerable,
                    pred_answerable=None,
                    error=f"paper_not_found: {resolved_path}",
                ))
            continue

        reused = False
        try:
            info = load_paper(coordinator, paper_path)
            reused = info.get("reused", False)
        except Exception as exc:
            for sample in paper_samples:
                result_map[sample.question_id] = output_to_dict(ExperimentOutput(
                    question_id=sample.question_id,
                    paper_id=sample.paper_id,
                    method="ce_rag",
                    question=sample.question,
                    answerable=sample.answerable,
                    pred_answerable=None,
                    error=f"paper_load_failed: {exc}",
                ))
            continue

        action = "Reused index" if reused else "Indexed"
        print(f"[ce_rag] {action} paper {paper_id} in {format_duration(time.time() - paper_start)}", flush=True)

        for question_index, sample in enumerate(paper_samples, start=1):
            with Timer() as timer:
                try:
                    result = coordinator.ask_question(sample.question)
                    # Use sufficiency score directly to avoid over-conservative abstention.
                    # Threshold 0.05 was selected from subset50 answerability-F1 sweep.
                    pred_answerable = bool(result.sufficiency_score is not None and result.sufficiency_score >= 0.05)
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="ce_rag",
                        question=sample.question,
                        answer=result.answer,
                        answerable=sample.answerable,
                        pred_answerable=pred_answerable,
                        route_type=result.route_type,
                        source_chunks=result.source_chunks,
                        evidence_summary=result.evidence_summary,
                        reasoning_trace=result.reasoning_trace,
                        reasoning_paths=result.reasoning_paths,
                        reasoning_chains=result.reasoning_chains,
                        claim_nodes=result.claim_nodes,
                        evidence_nodes=result.evidence_nodes,
                        result_nodes=result.result_nodes,
                        sufficiency_score=result.sufficiency_score,
                        sufficiency_label=result.sufficiency_label,
                        sufficiency_factors=result.sufficiency_factors,
                        consistency_score=result.consistency_score,
                        evidence_coverage=result.evidence_coverage,
                        confidence=result.confidence,
                        warnings=result.warnings,
                        latency_seconds=time.perf_counter() - timer.start,
                    )
                except Exception as exc:
                    output = ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method="ce_rag",
                        question=sample.question,
                        answerable=sample.answerable,
                        pred_answerable=None,
                        error=str(exc),
                        latency_seconds=time.perf_counter() - timer.start,
                    )
            result_map[sample.question_id] = output_to_dict(output)
            completed_questions += 1
            log_progress(
                "ce_rag",
                completed_questions,
                total_questions,
                run_start,
                current=f"paper={paper_id} q={question_index}/{len(paper_samples)} latency={output.latency_seconds:.1f}s",
            )

        # 每处理完一篇论文就落盘一次，避免任务超时/中断导致全部结果丢失
        # 此时只写出已完成的条目；最终结束后再按 all_qids 顺序整理
        write_jsonl(output_path, list(result_map.values()))
        print(f"[ce_rag] checkpoint written for {paper_id}", flush=True)

    outputs = [result_map[qid] for qid in all_qids]
    write_jsonl(output_path, outputs)
    print(f"Wrote {len(outputs)} CE-RAG predictions to {output_path}")


if __name__ == "__main__":
    main()

"""CE-RAG ablation study runner.

Runs the same QA dataset with multiple QAAgent ablation configurations:
- full: CE-RAG complete pipeline
- no_routing: fixed general route
- no_graph: no claim-evidence graph (chunk-only retrieval)
- no_chain: graph nodes but no reasoning-chain retrieval
- no_sufficiency: no evidence-sufficiency estimation
- no_verification: no answer verification
- no_iterative: no iterative retrieval expansion
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

from agents.parser_agent import ParserAgent
from agents.qa_agent import QAAgent
from config import COLLECTION_NAME
from experiments.index_utils import collection_exists, compute_doc_id
from experiments.schema import ExperimentOutput, Timer, load_samples, output_to_dict, write_jsonl
from services.chroma_client import get_chroma_client
from services.document_parser import DocumentParser
from services.llm_service import LLMService
from services.object_indexer import ObjectIndexer
from services.paper_graph_builder import PaperGraphBuilder
from services.vector_store import VectorStoreService


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


ABLATION_VARIANTS = {
    "ce_rag_full": {},
    "w/o_routing": {"use_routing": False},
    "w/o_graph": {"use_graph": False, "use_chain": False},
    "w/o_chain": {"use_chain": False},
    "w/o_sufficiency": {"use_sufficiency": False, "use_iterative": False},
    "w/o_verification": {"use_verification": False},
    "w/o_iterative": {"use_iterative": False},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CE-RAG ablation experiments.")
    parser.add_argument("--dataset", default="experiments/data/qa_dataset.sample.jsonl", help="Input QA dataset JSONL.")
    parser.add_argument("--output-dir", default="experiments/outputs", help="Output directory.")
    parser.add_argument("--variants", nargs="+", default=list(ABLATION_VARIANTS.keys()), help="Ablation variants to run.")
    parser.add_argument("--skip-missing-papers", action="store_true", help="Write error rows instead of failing on missing PDFs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_samples(PROJECT_ROOT / args.dataset if not os.path.isabs(args.dataset) else args.dataset)

    by_paper: Dict[str, List] = defaultdict(list)
    for sample in samples:
        by_paper[sample.paper_id].append(sample)

    llm_service = LLMService()
    vector_store = VectorStoreService()
    parser_agent = ParserAgent(vector_store=vector_store, llm_service=llm_service)
    object_indexer = ObjectIndexer(vector_store)

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for variant in args.variants:
        if variant not in ABLATION_VARIANTS:
            print(f"[ablation] skip unknown variant: {variant}")
            continue
        config = ABLATION_VARIANTS[variant]
        output_path = output_dir / f"ablation_{variant.replace('/', '_')}_results.jsonl"
        outputs: List[dict] = []
        total_questions = len(samples)
        completed_questions = 0
        run_start = time.time()
        print(f"\n[ablation:{variant}] Starting run: papers={len(by_paper)} questions={total_questions}", flush=True)

        for paper_index, (paper_id, paper_samples) in enumerate(by_paper.items(), start=1):
            first = paper_samples[0]
            paper_start = time.time()
            print(
                f"[ablation:{variant}] Loading paper {paper_index}/{len(by_paper)}: {paper_id} "
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
                        method=variant,
                        question=sample.question,
                        answerable=sample.answerable,
                        error=f"paper_not_found: {resolved_path}",
                    )))
                continue

            reused = False
            try:
                with resolved_path.open("rb") as f:
                    file_bytes = f.read()
                parsed = DocumentParser().parse_from_bytes(file_bytes, resolved_path.name)
                doc_id = compute_doc_id(parsed.filename, parsed.content)

                if collection_exists(doc_id):
                    vector_store.load_collection(doc_id)
                    profile = object_indexer.load_profile(doc_id)
                    reused = True
                else:
                    parse_result = parser_agent.parse_document_from_bytes(file_bytes, resolved_path.name)
                    if not parse_result.success or not parse_result.parsed_doc:
                        raise ValueError(parse_result.error_message or "parse failed")
                    doc_id = parse_result.document_id
                    profile = parse_result.paper_profile
            except Exception as exc:
                for sample in paper_samples:
                    outputs.append(output_to_dict(ExperimentOutput(
                        question_id=sample.question_id,
                        paper_id=sample.paper_id,
                        method=variant,
                        question=sample.question,
                        answerable=sample.answerable,
                        error=f"paper_load_failed: {exc}",
                    )))
                continue

            action = "Reused index" if reused else "Indexed"
            print(f"[ablation:{variant}] {action} paper {paper_id} in {format_duration(time.time() - paper_start)}", flush=True)

            # 创建该变体的 QAAgent
            qa_agent = QAAgent(llm_service=llm_service, vector_store=vector_store, ablation_config=config)
            qa_agent.set_document_context(doc_id=doc_id, paper_title=(profile.title if profile else parsed.title) or "", paper_summary="")
            qa_agent.current_profile = profile

            for question_index, sample in enumerate(paper_samples, start=1):
                with Timer() as timer:
                    try:
                        result = qa_agent.ask(sample.question)
                        pred_answerable = bool(result.sufficiency_label not in {"insufficient", "unknown"})
                        if result.warnings and any("不足" in w or "无法" in w or "过度泛化" in w or "全称" in w for w in result.warnings):
                            pred_answerable = False
                        output = ExperimentOutput(
                            question_id=sample.question_id,
                            paper_id=sample.paper_id,
                            method=variant,
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
                            method=variant,
                            question=sample.question,
                            answerable=sample.answerable,
                            error=str(exc),
                            latency_seconds=time.perf_counter() - timer.start,
                        )
                outputs.append(output_to_dict(output))
                completed_questions += 1
                log_progress(
                    f"ablation:{variant}",
                    completed_questions,
                    total_questions,
                    run_start,
                    current=f"paper={paper_id} q={question_index}/{len(paper_samples)} latency={output.latency_seconds:.1f}s",
                )

        write_jsonl(output_path, outputs)
        print(f"[ablation:{variant}] Wrote {len(outputs)} predictions to {output_path}")


if __name__ == "__main__":
    main()

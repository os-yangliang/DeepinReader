"""
Shared schemas and helpers for CE-RAG experiments.

The experiment runners use JSONL files for both input datasets and outputs.
This module keeps the output format consistent across CE-RAG and baselines.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class GoldEvidence:
    section: str = ""
    text: str = ""


@dataclass
class QASample:
    paper_id: str
    question_id: str
    question: str
    paper_path: str = ""
    title: str = ""
    question_type: str = "general"
    answerable: bool = True
    gold_answer: str = ""
    gold_evidence: List[Dict[str, Any]] = field(default_factory=list)
    gold_reasoning_chain: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentOutput:
    question_id: str
    paper_id: str
    method: str
    question: str
    answer: str = ""
    answerable: bool = True
    pred_answerable: Optional[bool] = None
    route_type: str = "general"
    source_chunks: List[str] = field(default_factory=list)
    evidence_summary: List[str] = field(default_factory=list)
    reasoning_trace: List[str] = field(default_factory=list)
    reasoning_paths: List[List[str]] = field(default_factory=list)
    reasoning_chains: List[Dict[str, Any]] = field(default_factory=list)
    claim_nodes: List[str] = field(default_factory=list)
    evidence_nodes: List[str] = field(default_factory=list)
    result_nodes: List[str] = field(default_factory=list)
    sufficiency_score: Optional[float] = None
    sufficiency_label: str = "unknown"
    sufficiency_factors: List[str] = field(default_factory=list)
    consistency_score: float = 0.0
    evidence_coverage: float = 0.0
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    latency_seconds: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end = time.perf_counter()
        self.elapsed = self.end - self.start


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {file_path}")
    rows: List[Dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {file_path}:{line_no}: {exc}") from exc
    return rows


def load_samples(path: str | Path) -> List[QASample]:
    samples: List[QASample] = []
    for row in read_jsonl(path):
        samples.append(QASample(**row))
    return samples


def append_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def output_to_dict(output: ExperimentOutput) -> Dict[str, Any]:
    return asdict(output)


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())

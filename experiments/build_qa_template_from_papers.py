"""Build a QA template JSONL from a directory of paper PDFs.

This script creates question templates only. Use auto_annotate_dataset.py next to
fill gold_answer and gold_evidence with LLM-assisted annotation.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import write_jsonl


DEFAULT_QUESTIONS = [
    {
        "suffix": "q1",
        "question_type": "method",
        "answerable": True,
        "question": "这篇论文提出的核心方法是什么？",
    },
    {
        "suffix": "q2",
        "question_type": "evidence",
        "answerable": True,
        "question": "作者是如何证明所提方法有效的？",
    },
    {
        "suffix": "q3",
        "question_type": "result",
        "answerable": True,
        "question": "这篇论文报告了哪些关键实验结果？",
    },
    {
        "suffix": "q4",
        "question_type": "general",
        "answerable": True,
        "question": "这篇论文的主要贡献是什么？",
    },
    {
        "suffix": "q5",
        "question_type": "critical",
        "answerable": True,
        "question": "这篇论文存在哪些局限性或未来工作方向？",
    },
    {
        "suffix": "q6",
        "question_type": "unanswerable",
        "answerable": False,
        "question": "这篇论文是否证明了该方法在所有任务和所有数据集上都优于已有方法？",
    },
]


EXTENDED_QUESTIONS = DEFAULT_QUESTIONS + [
    {
        "suffix": "q7",
        "question_type": "evidence",
        "answerable": True,
        "question": "这篇论文使用了哪些数据集或实验设置来支持结论？",
    },
    {
        "suffix": "q8",
        "question_type": "result",
        "answerable": True,
        "question": "论文中的消融实验或对比实验说明了什么？",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build QA template JSONL from paper PDFs.")
    parser.add_argument("--papers-dir", default="experiments/data/papers", help="Directory containing PDF papers.")
    parser.add_argument("--output", default="experiments/data/qa_dataset.papers.template.jsonl", help="Output template JSONL path.")
    parser.add_argument("--questions-per-paper", type=int, default=6, choices=[6, 8], help="Generate 6 or 8 fixed questions per paper.")
    parser.add_argument("--paper-limit", type=int, default=0, help="Only use the first N papers. 0 means all.")
    parser.add_argument("--absolute-paths", action="store_true", help="Write absolute paper_path values instead of project-relative paths.")
    parser.add_argument("--prefix", default="paper", help="Fallback paper_id prefix when filename has no stable stem.")
    parser.add_argument("--no-title-extract", action="store_true", help="Skip lightweight PDF title extraction.")
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def safe_id(stem: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", stem.strip()).strip("_").lower()
    return cleaned or fallback


def import_pymupdf():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        pass
    try:
        import fitz
        if not hasattr(fitz, "open"):
            return None
        return fitz
    except Exception:
        return None


def clean_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) < 6:
        return ""
    if len(text) > 220:
        return text[:220]
    return text


def extract_title(pdf_path: Path) -> str:
    pymupdf = import_pymupdf()
    if pymupdf is None:
        return ""
    try:
        doc = pymupdf.open(str(pdf_path))
        metadata = doc.metadata or {}
        title = clean_title(metadata.get("title") or "")
        if title and title.lower() not in {"untitled", "unknown"}:
            doc.close()
            return title
        first_page_text = doc[0].get_text() if len(doc) else ""
        doc.close()
    except Exception:
        return ""

    for line in first_page_text.splitlines():
        candidate = clean_title(line)
        if 8 <= len(candidate) <= 220 and not re.match(r"^(abstract|keywords|introduction)\b", candidate, re.I):
            return candidate
    return ""


def build_rows(papers: List[Path], questions: List[Dict], absolute_paths: bool, prefix: str, extract_titles: bool) -> List[Dict]:
    rows: List[Dict] = []
    total = len(papers)
    for index, pdf_path in enumerate(papers, start=1):
        paper_id = safe_id(pdf_path.stem, f"{prefix}_{index:03d}")
        paper_path = str(pdf_path.resolve()) if absolute_paths else project_relative(pdf_path)
        title = extract_title(pdf_path) if extract_titles else ""
        for q_index, spec in enumerate(questions, start=1):
            question_id = f"{paper_id}_{spec['suffix']}"
            rows.append({
                "paper_id": paper_id,
                "paper_path": paper_path,
                "title": title,
                "question_id": question_id,
                "question": spec["question"],
                "question_type": spec["question_type"],
                "answerable": spec["answerable"],
                "gold_answer": "",
                "gold_evidence": [],
                "gold_reasoning_chain": [],
                "metadata": {
                    "source": "auto_template_from_papers",
                    "paper_index": index,
                    "paper_count": total,
                    "question_index": q_index,
                    "needs_ai_annotation": True,
                    "needs_human_review": True,
                },
            })
    return rows


def main() -> None:
    args = parse_args()
    papers_dir = resolve(args.papers_dir)
    if not papers_dir.exists():
        raise FileNotFoundError(f"papers-dir not found: {papers_dir}")
    papers = sorted(papers_dir.glob("*.pdf"))
    if args.paper_limit:
        papers = papers[: args.paper_limit]
    if not papers:
        raise FileNotFoundError(f"No PDF files found in {papers_dir}")

    questions = EXTENDED_QUESTIONS if args.questions_per_paper == 8 else DEFAULT_QUESTIONS
    rows = build_rows(
        papers=papers,
        questions=questions,
        absolute_paths=args.absolute_paths,
        prefix=args.prefix,
        extract_titles=not args.no_title_extract,
    )
    output_path = resolve(args.output)
    write_jsonl(output_path, rows)
    print(f"Found {len(papers)} papers in {papers_dir}")
    print(f"Generated {len(rows)} QA template rows ({len(questions)} questions per paper)")
    print(f"Wrote template to {output_path}")
    print("Next: run experiments/auto_annotate_dataset.py to fill gold answers and evidence.")


if __name__ == "__main__":
    main()

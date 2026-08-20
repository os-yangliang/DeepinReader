"""AI-assisted dataset annotation for CE-RAG with progress logging and resume.

Improvements over original:
- Appends results after each paper (crash-safe, resumable).
- Flushes progress to stdout after each question.
- Skips already-annotated question_ids when output files exist.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import QASample, append_jsonl, load_samples, write_jsonl

KEYWORDS = {
    "method": ["method", "approach", "model", "framework", "proposed", "architecture", "方法", "模型"],
    "evidence": ["experiment", "evaluation", "dataset", "baseline", "ablation", "实验", "评估"],
    "result": ["result", "performance", "outperform", "improve", "table", "结果", "提升"],
    "critical": ["limitation", "discussion", "future work", "threat", "局限", "未来"],
    "general": ["contribution", "abstract", "introduction", "conclusion", "贡献", "摘要"],
    "unanswerable": ["all", "sota", "state-of-the-art", "dataset", "所有", "证明"],
}

SYSTEM_PROMPT = """你是严谨的学术论文数据标注助手。请只根据给定论文片段生成数据集标注。
要求：
1. 只能依据给定片段，不要使用外部知识。
2. gold_answer 用中文，2-6 句话。
3. gold_evidence 必须摘录给定片段中的论文原文，最多 3 条。
4. 如果证据不足，answerable=false，gold_evidence=[]，gold_answer 说明证据不足。
5. 对 unanswerable 问题必须保守。
6. 只输出合法 JSON，不要 Markdown。
"""

USER_PROMPT = """请为下面 QA 样本生成标注。

标题候选：{title}
问题类型：{question_type}
模板 answerable：{answerable}
问题：{question}

论文片段：
{context}

输出 JSON 格式：
{{
  "title": "论文标题",
  "answerable": true,
  "gold_answer": "中文标准答案",
  "gold_evidence": [{{"section": "章节名或片段编号", "text": "论文原文证据"}}],
  "confidence": 0.0,
  "notes": "简短说明"
}}
"""


@dataclass
class SimpleParsedPaper:
    title: str
    chunks: List[str]


def split_text(text: str, chunk_size: int = 1200, chunk_overlap: int = 150) -> List[str]:
    chunks: List[str] = []
    if not text:
        return chunks
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end >= text_len:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto annotate CE-RAG dataset with LLM.")
    p.add_argument("--template", default="experiments/data/qa_dataset.pilot.template.jsonl")
    p.add_argument("--output", default="experiments/data/qa_dataset.pilot.ai.jsonl")
    p.add_argument("--raw-output", default="experiments/outputs/ai_annotation_raw.jsonl")
    p.add_argument("--context-chars", type=int, default=10000)
    p.add_argument("--chunks-per-question", type=int, default=6)
    p.add_argument("--paper-limit", type=int, default=0)
    p.add_argument("--question-limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume", action="store_true", help="Skip question_ids already present in --output.")
    return p.parse_args()


def resolve(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists() or str(path).lower().startswith(("data", "outputs")):
        return cwd_candidate
    return PROJECT_ROOT / path


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def load_llm_service():
    module_path = PROJECT_ROOT / "services" / "llm_service.py"
    spec = importlib.util.spec_from_file_location("paperreader_llm_service", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load LLMService from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LLMService


def import_pymupdf():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        pass
    try:
        import fitz
        if not hasattr(fitz, "open"):
            raise ImportError("imported fitz is not PyMuPDF")
        return fitz
    except Exception as exc:
        raise RuntimeError(
            "无法导入 PyMuPDF。当前环境可能安装了错误的 fitz 包。"
            "请运行：pip uninstall -y fitz frontend && pip install -U pymupdf"
        ) from exc


def extract_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("---") and len(line) > 5:
            return line[:200]
    return "TODO"


def parse_pdf(path: Path) -> SimpleParsedPaper:
    pymupdf = import_pymupdf()
    doc = pymupdf.open(str(path))
    parts: List[str] = []
    metadata = doc.metadata or {}
    for idx, page in enumerate(doc):
        parts.append(f"\n--- Page {idx + 1} ---\n{page.get_text()}")
    doc.close()
    content = "".join(parts)
    title = metadata.get("title") or extract_title(content)
    return SimpleParsedPaper(title=title, chunks=split_text(content, chunk_size=1200, chunk_overlap=150))


def chunk_score(chunk: str, sample: QASample) -> int:
    text = clean(chunk).lower()
    score = 0
    for kw in KEYWORDS.get(sample.question_type, []) + KEYWORDS["general"]:
        if kw.lower() in text:
            score += 5
    for term in re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]+", sample.question):
        term = term.lower()
        if len(term) >= 2 and term in text:
            score += 2
    return score


def select_context(chunks: List[str], sample: QASample, max_chars: int, top_k: int) -> str:
    scored = sorted(((chunk_score(c, sample), i, c) for i, c in enumerate(chunks)), reverse=True)
    selected = scored[:top_k] if scored else []
    if selected and all(s == 0 for s, _, _ in selected):
        selected = [(0, i, c) for i, c in enumerate(chunks[:top_k])]
    parts: List[str] = []
    used = 0
    for score, idx, chunk in selected:
        part = f"[chunk_{idx + 1}, score={score}]\n{clean(chunk)}"
        if used + len(part) > max_chars:
            part = part[: max(0, max_chars - used)]
        if part:
            parts.append(part)
            used += len(part)
        if used >= max_chars:
            break
    return "\n\n---\n\n".join(parts)


def parse_json(text: str) -> Dict[str, Any]:
    raw = re.sub(r"^```(?:json)?\s*", "", (text or "").strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise
        return json.loads(m.group(0))


def normalize_annotation(data: Dict[str, Any], sample: QASample, title: str) -> Dict[str, Any]:
    answerable = data.get("answerable", sample.answerable)
    if not isinstance(answerable, bool):
        answerable = str(answerable).lower() in {"true", "1", "yes", "是"}
    evidence = []
    if answerable:
        for item in data.get("gold_evidence") or []:
            if isinstance(item, dict) and clean(str(item.get("text", ""))):
                evidence.append({"section": clean(str(item.get("section") or "AI-selected context")), "text": clean(str(item.get("text") or ""))})
    answer = clean(str(data.get("gold_answer") or sample.gold_answer or "TODO"))
    if not answerable and answer == "TODO":
        answer = "论文片段中没有提供足够证据回答该问题，无法根据本文判断。"
    return {"title": clean(str(data.get("title") or title or sample.title)), "answerable": answerable, "gold_answer": answer, "gold_evidence": evidence[:3], "confidence": data.get("confidence"), "notes": clean(str(data.get("notes") or ""))}


def output_row(sample: QASample, ann: Dict[str, Any], status: str) -> Dict[str, Any]:
    meta = dict(sample.metadata or {})
    meta.update({"status": "ai_generated", "needs_human_review": True, "ai_annotation_status": status, "ai_confidence": ann.get("confidence"), "ai_notes": ann.get("notes", "")})
    return {"paper_id": sample.paper_id, "paper_path": sample.paper_path, "title": ann.get("title") or sample.title, "question_id": sample.question_id, "question": sample.question, "question_type": sample.question_type, "answerable": ann.get("answerable", sample.answerable), "gold_answer": ann.get("gold_answer") or sample.gold_answer, "gold_evidence": ann.get("gold_evidence") or [], "gold_reasoning_chain": sample.gold_reasoning_chain or [], "metadata": meta}


def load_completed_ids(output_path: Path) -> Set[str]:
    """读取已有输出中的 question_id 集合，用于 resume。"""
    ids: Set[str] = set()
    if not output_path.exists():
        return ids
    try:
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    qid = row.get("question_id")
                    if qid:
                        ids.add(qid)
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        print(f"[warn] failed to read existing output for resume: {exc}", flush=True)
    return ids


def main() -> None:
    args = parse_args()
    samples = load_samples(resolve(args.template))
    if args.question_limit:
        samples = samples[: args.question_limit]
    grouped: Dict[str, List[QASample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.paper_id].append(sample)
    paper_ids = list(grouped.keys())[: args.paper_limit or None]

    output_path = resolve(args.output)
    raw_output_path = resolve(args.raw_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_output_path.parent.mkdir(parents=True, exist_ok=True)

    completed_ids: Set[str] = set()
    if args.resume:
        completed_ids = load_completed_ids(output_path)
        print(f"[annotate] resume mode: {len(completed_ids)} question_ids already done", flush=True)

    LLMService = None if args.dry_run else load_llm_service()
    llm = None if args.dry_run else LLMService(temperature=0.1)

    total_questions = sum(len(grouped[pid]) for pid in paper_ids)
    skipped = 0
    done = 0
    start_time = time.time()

    print(f"[annotate] papers={len(paper_ids)} questions={total_questions} output={output_path}", flush=True)

    for paper_index, paper_id in enumerate(paper_ids, start=1):
        pdf_path = resolve(grouped[paper_id][0].paper_path)
        paper_questions = grouped[paper_id]
        paper_total = len(paper_questions)

        # 跳过整篇已完成的 paper
        paper_qids = {s.question_id for s in paper_questions}
        if args.resume and paper_qids.issubset(completed_ids):
            skipped += paper_total
            done += paper_total
            print(f"[annotate] {paper_index}/{len(paper_ids)} {paper_id} skipped (all {paper_total} done)", flush=True)
            continue

        paper_start = time.time()
        try:
            parsed = parse_pdf(pdf_path)
        except Exception as exc:
            print(f"[annotate] {paper_index}/{len(paper_ids)} {paper_id} parse failed: {exc}", flush=True)
            rows = []
            raw_rows = []
            for sample in paper_questions:
                if args.resume and sample.question_id in completed_ids:
                    continue
                ann = {"title": sample.title, "answerable": sample.answerable, "gold_answer": sample.gold_answer, "gold_evidence": [], "notes": str(exc)}
                rows.append(output_row(sample, ann, "parse_failed"))
                raw_rows.append({"paper_id": sample.paper_id, "question_id": sample.question_id, "status": "parse_failed", "error": str(exc)})
            if rows:
                append_jsonl(output_path, rows)
                append_jsonl(raw_output_path, raw_rows)
            continue

        print(f"[annotate] {paper_index}/{len(paper_ids)} {paper_id} parsed ({len(parsed.chunks)} chunks) answering {paper_total} questions...", flush=True)

        rows = []
        raw_rows = []
        for q_index, sample in enumerate(paper_questions, start=1):
            if args.resume and sample.question_id in completed_ids:
                skipped += 1
                done += 1
                continue

            context = select_context(parsed.chunks, sample, args.context_chars, args.chunks_per_question)
            if args.dry_run:
                ann = {"title": parsed.title, "answerable": sample.answerable, "gold_answer": sample.gold_answer, "gold_evidence": sample.gold_evidence, "notes": "dry_run"}
                status = "dry_run"
                response = ""
            else:
                try:
                    prompt = USER_PROMPT.format(title=parsed.title, question_type=sample.question_type, answerable=sample.answerable, question=sample.question, context=context)
                    response = llm.chat_sync(prompt, system_prompt=SYSTEM_PROMPT, chat_history=[])
                    ann = normalize_annotation(parse_json(response), sample, parsed.title)
                    status = "ok"
                except Exception as exc:
                    response = ""
                    ann = {"title": parsed.title, "answerable": sample.answerable, "gold_answer": sample.gold_answer, "gold_evidence": sample.gold_evidence, "notes": str(exc)}
                    status = "failed"

            rows.append(output_row(sample, ann, status))
            raw_rows.append({"paper_id": sample.paper_id, "question_id": sample.question_id, "status": status, "raw_response": response, "context_preview": context[:2000]})
            done += 1
            elapsed = time.time() - start_time
            avg = elapsed / done if done else 0.0
            eta = avg * (total_questions - done) if done else 0.0
            print(
                f"[annotate] {paper_index}/{len(paper_ids)} {paper_id} q{q_index}/{paper_total} "
                f"done={done}/{total_questions} avg={avg:.1f}s ETA={int(eta)}s status={status}",
                flush=True,
            )

        if rows:
            append_jsonl(output_path, rows)
            append_jsonl(raw_output_path, raw_rows)
        print(f"[annotate] {paper_index}/{len(paper_ids)} {paper_id} finished in {time.time() - paper_start:.1f}s", flush=True)

    print(f"[annotate] complete. total={done}/{total_questions} skipped={skipped} output={output_path}", flush=True)


if __name__ == "__main__":
    main()

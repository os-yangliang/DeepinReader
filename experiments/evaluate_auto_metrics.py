"""自动评估指标计算。

Metrics:
- BLEU-1/2/4 (n-gram precision with brevity penalty)
- ROUGE-L (longest common subsequence based F1)
- BERTScore-style embedding similarity (using the project's embedding model)
- Evidence Recall / Precision / F1
- Answerability Accuracy / Precision / Recall / F1
- Citation F1 (mentions of datasets/metrics/values from gold evidence)
- Reasoning Chain Recall
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.schema import read_jsonl
from services.vector_store import VectorStoreService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute automatic metrics for experiment predictions.")
    parser.add_argument("--dataset", required=True, help="Gold dataset JSONL.")
    parser.add_argument("--predictions", nargs="+", required=True, help="Prediction JSONL files.")
    parser.add_argument("--output", default="experiments/outputs/auto_metrics_summary.csv", help="Output CSV.")
    return parser.parse_args()


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]", text.lower())


def ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def bleu_score(reference: str, hypothesis: str, max_n: int = 4) -> Dict[str, float]:
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)
    if not hyp_tokens:
        return {f"bleu_{n}": 0.0 for n in range(1, max_n + 1)}

    ref_counts = [Counter(ngrams(ref_tokens, n)) for n in range(1, max_n + 1)]
    hyp_counts = [Counter(ngrams(hyp_tokens, n)) for n in range(1, max_n + 1)]

    scores = {}
    for n in range(1, max_n + 1):
        clipped = sum((hyp_counts[n - 1] & ref_counts[n - 1]).values())
        total = max(1, sum(hyp_counts[n - 1].values()))
        precision = clipped / total
        # 简单 brevity penalty
        bp = 1.0 if len(hyp_tokens) >= len(ref_tokens) else min(1.0, len(hyp_tokens) / len(ref_tokens))
        scores[f"bleu_{n}"] = round(bp * precision, 4)
    return scores


def lcs_length(x: List[str], y: List[str]) -> int:
    m, n = len(x), len(y)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if x[i - 1] == y[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[n]


def rouge_l(reference: str, hypothesis: str) -> float:
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)
    if not ref_tokens or not hyp_tokens:
        return 0.0
    lcs = lcs_length(ref_tokens, hyp_tokens)
    precision = lcs / len(hyp_tokens)
    recall = lcs / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def evidence_f1(gold_evidence: List[Dict[str, Any]], pred_chunks: List[str]) -> Dict[str, float]:
    """计算预测 evidence 与 gold evidence 的 F1（基于文本重叠）。"""
    gold_texts = [normalize(e.get("text", "")) for e in gold_evidence]
    pred_texts = [normalize(c) for c in pred_chunks]
    if not gold_texts:
        return {"evidence_precision": 0.0, "evidence_recall": 0.0, "evidence_f1": 0.0}
    if not pred_texts:
        return {"evidence_precision": 0.0, "evidence_recall": 0.0, "evidence_f1": 0.0}

    matched_gold = set()
    matched_pred = set()
    for gi, g in enumerate(gold_texts):
        for pi, p in enumerate(pred_texts):
            if pi in matched_pred:
                continue
            overlap = len(set(tokenize(g)) & set(tokenize(p)))
            if overlap > 0:
                matched_gold.add(gi)
                matched_pred.add(pi)
                break

    precision = len(matched_pred) / len(pred_texts)
    recall = len(matched_gold) / len(gold_texts)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "evidence_precision": round(precision, 4),
        "evidence_recall": round(recall, 4),
        "evidence_f1": round(f1, 4),
    }


def answerability_metrics(preds: List[Dict[str, Any]]) -> Dict[str, float]:
    tp = fp = fn = tn = 0
    for p in preds:
        gold = bool(p.get("answerable", True))
        pred = p.get("pred_answerable")
        if pred is None:
            pred = True
        if gold and pred:
            tp += 1
        elif gold and not pred:
            fn += 1
        elif not gold and pred:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / max(1, len(preds))
    return {
        "answerability_accuracy": round(accuracy, 4),
        "answerability_precision": round(precision, 4),
        "answerability_recall": round(recall, 4),
        "answerability_f1": round(f1, 4),
    }


def extract_citations(text: str) -> Set[str]:
    """提取文本中的数据集、指标、数值等候选引用实体。"""
    # 简单规则：大写短语、带数字的指标、百分比等
    entities = set()
    # 数据集/方法名（大写缩写或 camelCase）
    entities.update(re.findall(r"\b[A-Z]{2,}[\-A-Za-z0-9]*\b", text))
    # 指标 + 数值
    entities.update(re.findall(r"\b(?:accuracy|f1|bleu|rouge|auc|map|ndcg|precision|recall)\s*(?:@\s*k|\d+)?[\s:]*\d+(?:\.\d+)?%?", text, re.IGNORECASE))
    # 百分比
    entities.update(re.findall(r"\d+(?:\.\d+)?%", text))
    return {e.lower() for e in entities}


def citation_f1(gold_text: str, pred_text: str) -> Dict[str, float]:
    gold_citations = extract_citations(gold_text)
    pred_citations = extract_citations(pred_text)
    if not gold_citations:
        return {"citation_precision": 0.0, "citation_recall": 0.0, "citation_f1": 0.0}
    matched = gold_citations & pred_citations
    precision = len(matched) / len(pred_citations) if pred_citations else 0.0
    recall = len(matched) / len(gold_citations)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "citation_precision": round(precision, 4),
        "citation_recall": round(recall, 4),
        "citation_f1": round(f1, 4),
    }


def extract_citation_ids(text: str) -> Set[str]:
    """提取答案中的结构化引用 ID，如 [^claim_1] -> claim_1。"""
    return set(re.findall(r"\[\^([\w_\-]+)\]", text))


def citation_groundedness(pred_text: str, pred_row: Dict[str, Any]) -> Dict[str, float]:
    """计算预测答案中引用 ID 的真实 grounded 比例。

    引用 ID 必须出现在 claim_nodes / evidence_nodes / result_nodes 中才算有效。
    """
    cited_ids = extract_citation_ids(pred_text)
    valid_ids = set()
    valid_ids.update(pred_row.get("claim_nodes", []) or [])
    valid_ids.update(pred_row.get("evidence_nodes", []) or [])
    valid_ids.update(pred_row.get("result_nodes", []) or [])
    # reasoning_chains 中也可能包含 chain_id
    for chain in pred_row.get("reasoning_chains", []) or []:
        if isinstance(chain, dict) and chain.get("chain_id"):
            valid_ids.add(chain["chain_id"])

    if not cited_ids:
        return {"citation_id_precision": 0.0, "citation_id_recall": 0.0, "citation_id_f1": 0.0}
    matched = cited_ids & valid_ids
    precision = len(matched) / len(cited_ids)
    recall = len(matched) / len(valid_ids) if valid_ids else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "citation_id_precision": round(precision, 4),
        "citation_id_recall": round(recall, 4),
        "citation_id_f1": round(f1, 4),
    }


def chain_recall(gold_chain: List[str], pred_chains: List[Dict[str, Any]]) -> float:
    if not gold_chain:
        return 0.0
    pred_nodes = set()
    for chain in pred_chains:
        nodes = chain.get("nodes", []) if isinstance(chain, dict) else []
        pred_nodes.update(nodes)
    matched = sum(1 for node in gold_chain if node in pred_nodes)
    return round(matched / len(gold_chain), 4)


class EmbeddingSimilarity:
    """使用项目 embedding 模型计算 BERTScore-style 相似度。"""

    def __init__(self):
        self.vector_store = VectorStoreService()
        self._cache: Dict[str, List[float]] = {}

    def embed(self, text: str) -> List[float]:
        if text in self._cache:
            return self._cache[text]
        vec = self.vector_store.embeddings.embed_documents([text])[0]
        self._cache[text] = vec
        return vec

    def score(self, reference: str, hypothesis: str) -> float:
        if not reference or not hypothesis:
            return 0.0
        v1 = self.embed(reference)
        v2 = self.embed(hypothesis)
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5
        if n1 == 0 or n2 == 0:
            return 0.0
        return round(max(0.0, min(1.0, dot / (n1 * n2))), 4)


def evaluate_predictions(gold_map: Dict[str, Dict[str, Any]], pred_path: Path, embedder: EmbeddingSimilarity) -> Dict[str, Any]:
    preds = read_jsonl(pred_path)
    method = pred_path.stem

    bleu_sums = {f"bleu_{n}": 0.0 for n in range(1, 5)}
    rouge_sum = 0.0
    bert_sum = 0.0
    evidence_metrics = {"evidence_precision": 0.0, "evidence_recall": 0.0, "evidence_f1": 0.0}
    citation_metrics = {"citation_precision": 0.0, "citation_recall": 0.0, "citation_f1": 0.0}
    citation_id_metrics = {"citation_id_precision": 0.0, "citation_id_recall": 0.0, "citation_id_f1": 0.0}
    chain_sum = 0.0
    valid = 0

    for pred in preds:
        qid = pred.get("question_id", "")
        gold = gold_map.get(qid)
        if not gold:
            continue
        answer = pred.get("answer", "")
        gold_answer = gold.get("gold_answer", "")
        if not answer or not gold_answer:
            continue
        valid += 1

        bleu = bleu_score(gold_answer, answer)
        for k, v in bleu.items():
            bleu_sums[k] += v
        rouge_sum += rouge_l(gold_answer, answer)
        bert_sum += embedder.score(gold_answer, answer)

        ev = evidence_f1(gold.get("gold_evidence", []), pred.get("source_chunks", []))
        for k, v in ev.items():
            evidence_metrics[k] += v

        cit = citation_f1(gold_answer, answer)
        for k, v in cit.items():
            citation_metrics[k] += v

        cid = citation_groundedness(answer, pred)
        for k, v in cid.items():
            citation_id_metrics[k] += v

        chain_sum += chain_recall(gold.get("gold_reasoning_chain", []), pred.get("reasoning_chains", []))

    result = {"method": method, "count": valid}
    if valid > 0:
        for k in bleu_sums:
            result[k] = round(bleu_sums[k] / valid, 4)
        result["rouge_l"] = round(rouge_sum / valid, 4)
        result["bertscore"] = round(bert_sum / valid, 4)
        for k in evidence_metrics:
            result[k] = round(evidence_metrics[k] / valid, 4)
        for k in citation_metrics:
            result[k] = round(citation_metrics[k] / valid, 4)
        for k in citation_id_metrics:
            result[k] = round(citation_id_metrics[k] / valid, 4)
        result["chain_recall"] = round(chain_sum / valid, 4)

    result.update(answerability_metrics(preds))
    return result


def main() -> None:
    args = parse_args()
    gold_rows = read_jsonl(Path(args.dataset))
    gold_map = {row["question_id"]: row for row in gold_rows}

    embedder = EmbeddingSimilarity()
    results = []
    for pred_file in args.predictions:
        pred_path = Path(pred_file)
        if not pred_path.is_absolute():
            pred_path = PROJECT_ROOT / pred_path
        print(f"[auto_metrics] evaluating {pred_path}", flush=True)
        results.append(evaluate_predictions(gold_map, pred_path, embedder))

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if results:
        fieldnames = list(results[0].keys())
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    print(f"[auto_metrics] wrote summary to {output_path}")


if __name__ == "__main__":
    main()

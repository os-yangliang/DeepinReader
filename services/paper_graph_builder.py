import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from services.paper_schema import (
    Claim,
    Evidence,
    Experiment,
    GraphEdge,
    GraphEdgeType,
    PaperProfile,
    PaperSection,
    ProvenanceSpan,
    ResultItem,
)


class PaperGraphBuilder:
    """构建论文的主张-证据图，支持基于语义/共现/位置的多信号边关联。"""

    def __init__(self, embedding_model: Optional[Any] = None):
        """
        Args:
            embedding_model: 可选的 embedding 模型（需实现 embed_documents 方法）。
                             若提供，则使用语义余弦相似度；否则退化为轻量词法相似度。
        """
        self.embedding_model = embedding_model
        self._embedding_cache: Dict[str, List[float]] = {}
        self.similarity_fn = self._semantic_similarity if embedding_model else self._lexical_similarity

    def build(
        self,
        document_id: str,
        title: str,
        sections: List[PaperSection],
        extracted: dict,
    ) -> PaperProfile:
        claims: List[Claim] = extracted.get("claims", [])
        evidences: List[Evidence] = extracted.get("evidences", [])
        results: List[ResultItem] = extracted.get("results", [])
        experiments: List[Experiment] = extracted.get("experiments", [])
        limitations: List[str] = extracted.get("limitations", [])

        graph: Dict[str, List[str]] = {}
        graph_edges: List[GraphEdge] = []

        # 1. 章节包含关系
        section_edges, section_contains = self._build_section_edges(sections, claims, evidences, experiments, results)
        graph_edges.extend(section_edges)
        graph.update(section_contains)

        # 2. claim -> evidence (SUPPORTED_BY)
        claim_evidence_edges = self._build_claim_evidence_edges(claims, evidences, sections)
        graph_edges.extend(claim_evidence_edges)
        self._update_adjacency(graph, claim_evidence_edges)

        # 3. evidence -> result (DERIVED_FROM)
        evidence_result_edges = self._build_evidence_result_edges(evidences, results)
        graph_edges.extend(evidence_result_edges)
        self._update_adjacency(graph, evidence_result_edges)

        # 4. result -> claim (SUPPORTS)
        result_claim_edges = self._build_result_claim_edges(results, claims)
        graph_edges.extend(result_claim_edges)
        self._update_adjacency(graph, result_claim_edges)

        # 5. result -> experiment (DERIVED_FROM)
        result_experiment_edges = self._build_result_experiment_edges(results, experiments)
        graph_edges.extend(result_experiment_edges)
        self._update_adjacency(graph, result_experiment_edges)

        # 6. claim -> limitation (LIMITED_BY)
        limitation_edges = self._build_limitation_edges(claims, limitations)
        graph_edges.extend(limitation_edges)
        self._update_adjacency(graph, limitation_edges)

        # 7. 一致性校验：记录孤立节点与异常
        diagnostics = self._diagnostics(claims, evidences, results, experiments, graph)

        abstract = ""
        for section in sections:
            if section.section_type.value == "abstract":
                abstract = section.content[:2000]
                break

        profile = PaperProfile(
            document_id=document_id,
            title=title,
            abstract=abstract,
            sections=sections,
            claims=claims,
            evidences=evidences,
            experiments=experiments,
            results=results,
            contributions=extracted.get("contributions", []),
            limitations=limitations,
            keywords=extracted.get("keywords", []),
            graph=graph,
            graph_edges=graph_edges,
        )
        # 将诊断信息附加到 profile 的 metadata 区域（Pydantic 允许 extra fields）
        profile.__dict__["graph_diagnostics"] = diagnostics
        return profile

    # ------------------------------------------------------------------
    # 边构建子方法
    # ------------------------------------------------------------------

    def _build_section_edges(
        self,
        sections: List[PaperSection],
        claims: List[Claim],
        evidences: List[Evidence],
        experiments: List[Experiment],
        results: List[ResultItem],
    ) -> Tuple[List[GraphEdge], Dict[str, List[str]]]:
        edges = []
        adjacency: Dict[str, List[str]] = {}
        for section in sections:
            targets: List[str] = []
            for claim in claims:
                if claim.section_id == section.section_id:
                    targets.append(claim.claim_id)
                    edges.append(self._make_edge(section.section_id, claim.claim_id, GraphEdgeType.CONTAINS, section, 0.9))
            for evidence in evidences:
                if evidence.section_id == section.section_id:
                    targets.append(evidence.evidence_id)
                    edges.append(self._make_edge(section.section_id, evidence.evidence_id, GraphEdgeType.CONTAINS, section, 0.9))
            for experiment in experiments:
                if experiment.section_id == section.section_id:
                    targets.append(experiment.experiment_id)
                    edges.append(self._make_edge(section.section_id, experiment.experiment_id, GraphEdgeType.CONTAINS, section, 0.9))
            for result in results:
                if result.section_id == section.section_id:
                    targets.append(result.result_id)
                    edges.append(self._make_edge(section.section_id, result.result_id, GraphEdgeType.CONTAINS, section, 0.9))
            if targets:
                adjacency[section.section_id] = targets
        return edges, adjacency

    def _build_claim_evidence_edges(self, claims: List[Claim], evidences: List[Evidence], sections: List[PaperSection]) -> List[GraphEdge]:
        """claim -> evidence：基于同 section、相邻位置、语义相似度综合选择 top-k 证据。"""
        edges = []
        section_map = {s.section_id: s for s in sections}
        for claim in claims:
            scored: List[Tuple[float, Evidence]] = []
            for evidence in evidences:
                score = self._claim_evidence_support_score(claim, evidence, section_map)
                if score > 0.15:
                    scored.append((score, evidence))
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = scored[:3]
            claim.evidence_ids = [e.evidence_id for _, e in selected]
            for score, evidence in selected:
                edges.append(self._make_edge(claim.claim_id, evidence.evidence_id, GraphEdgeType.SUPPORTED_BY, claim, score))
        return edges

    def _build_evidence_result_edges(self, evidences: List[Evidence], results: List[ResultItem]) -> List[GraphEdge]:
        """evidence -> result：基于 dataset/metric/value 及语义相似度匹配。"""
        edges = []
        for evidence in evidences:
            best_score, best_result = 0.0, None
            for result in results:
                score = self._evidence_result_match_score(evidence, result)
                if score > best_score:
                    best_score, best_result = score, result
            if best_result and best_score > 0.25:
                edges.append(self._make_edge(evidence.evidence_id, best_result.result_id, GraphEdgeType.DERIVED_FROM, evidence, best_score))
        return edges

    def _build_result_claim_edges(self, results: List[ResultItem], claims: List[Claim]) -> List[GraphEdge]:
        """result -> claim：基于语义相似度选择最相关的主张。"""
        edges = []
        for result in results:
            scored = [(self.similarity_fn(result.text, claim.text), claim) for claim in claims]
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = [(s, c) for s, c in scored[:2] if s > 0.15]
            result.supports_claim_ids = [c.claim_id for _, c in selected]
            for score, claim in selected:
                edges.append(self._make_edge(result.result_id, claim.claim_id, GraphEdgeType.SUPPORTS, result, score))
        return edges

    def _build_result_experiment_edges(self, results: List[ResultItem], experiments: List[Experiment]) -> List[GraphEdge]:
        """result -> experiment：基于 dataset/metric 匹配。"""
        edges = []
        for result in results:
            best_score, best_experiment = 0.0, None
            for experiment in experiments:
                score = self._result_experiment_match_score(result, experiment)
                if score > best_score:
                    best_score, best_experiment = score, experiment
            if best_experiment and best_score > 0.25:
                edges.append(self._make_edge(result.result_id, best_experiment.experiment_id, GraphEdgeType.DERIVED_FROM, result, best_score))
        return edges

    def _build_limitation_edges(self, claims: List[Claim], limitations: List[str]) -> List[GraphEdge]:
        """claim -> limitation：将 limitation 文本作为虚拟节点，关联最相关的主张。"""
        edges = []
        for idx, limitation_text in enumerate(limitations):
            limitation_id = f"limitation_{idx + 1}"
            scored = [(self.similarity_fn(limitation_text, claim.text), claim) for claim in claims]
            scored.sort(key=lambda x: x[0], reverse=True)
            selected = [(s, c) for s, c in scored[:2] if s > 0.12]
            for score, claim in selected:
                edges.append(self._make_edge(claim.claim_id, limitation_id, GraphEdgeType.LIMITED_BY, claim, score))
        return edges

    # ------------------------------------------------------------------
    # 评分函数
    # ------------------------------------------------------------------

    def _claim_evidence_support_score(self, claim: Claim, evidence: Evidence, section_map: Dict[str, PaperSection]) -> float:
        """综合同 section、位置邻近、语义相似度判断 claim 与 evidence 的支持关系。"""
        score = 0.0
        # 同 section
        if claim.section_id and evidence.section_id and claim.section_id == evidence.section_id:
            score += 0.35
        # 相邻 section（如 method 与 experiment）
        elif self._adjacent_sections(claim.section_id, evidence.section_id, section_map):
            score += 0.15

        # 语义相似度
        semantic = self.similarity_fn(claim.text, evidence.text)
        score += 0.45 * semantic

        # 共享关键词/指标
        overlap = self._term_overlap_ratio(claim.text, evidence.text)
        score += 0.20 * overlap

        return min(1.0, score)

    def _evidence_result_match_score(self, evidence: Evidence, result: ResultItem) -> float:
        score = 0.0
        # dataset 匹配
        if evidence.text and result.dataset:
            if result.dataset.lower() in evidence.text.lower():
                score += 0.35
        # metric 匹配
        if evidence.text and result.metric:
            if result.metric.lower() in evidence.text.lower():
                score += 0.30
        # value 匹配
        if result.value and result.value.lower() in evidence.text.lower():
            score += 0.20
        # 语义相似度
        score += 0.25 * self.similarity_fn(evidence.text, result.text)
        # 同 section
        if evidence.section_id and result.section_id and evidence.section_id == result.section_id:
            score += 0.10
        return min(1.0, score)

    def _result_experiment_match_score(self, result: ResultItem, experiment: Experiment) -> float:
        score = 0.0
        if result.dataset and experiment.dataset and result.dataset.lower() == experiment.dataset.lower():
            score += 0.45
        if result.metric and experiment.metrics:
            if any(result.metric.lower() == m.lower() for m in experiment.metrics):
                score += 0.35
        score += 0.25 * self.similarity_fn(result.text, " ".join([experiment.name, experiment.dataset, ", ".join(experiment.metrics)]))
        if result.section_id and experiment.section_id and result.section_id == experiment.section_id:
            score += 0.15
        return min(1.0, score)

    # ------------------------------------------------------------------
    # 工具函数
    # ------------------------------------------------------------------

    def _make_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: GraphEdgeType,
        provenance_source,
        confidence: float,
    ) -> GraphEdge:
        provenance = provenance_source if isinstance(provenance_source, ProvenanceSpan) else None
        # 置信度平滑：避免过低或过高
        confidence = max(0.1, min(0.95, confidence))
        return GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            provenance=provenance,
            confidence=round(confidence, 4),
        )

    def _update_adjacency(self, graph: Dict[str, List[str]], edges: List[GraphEdge]) -> None:
        for edge in edges:
            graph.setdefault(edge.source_id, []).append(edge.target_id)

    def _adjacent_sections(self, sid1: str, sid2: str, section_map: Dict[str, PaperSection]) -> bool:
        s1 = section_map.get(sid1)
        s2 = section_map.get(sid2)
        if not s1 or not s2:
            return False
        # 简单按 section_type 判断相邻语义：method <-> experiment <-> result <-> ablation
        adjacent_pairs = {
            ("method", "experiment"), ("experiment", "method"),
            ("experiment", "result"), ("result", "experiment"),
            ("result", "ablation"), ("ablation", "result"),
            ("method", "result"), ("result", "method"),
        }
        return (s1.section_type.value, s2.section_type.value) in adjacent_pairs

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """基于 embedding 的余弦相似度。缓存已编码文本以避免重复计算。"""
        if not text1 or not text2:
            return 0.0
        for text in (text1, text2):
            if text not in self._embedding_cache:
                try:
                    vec = self.embedding_model.embed_documents([text])[0]
                    self._embedding_cache[text] = vec
                except Exception:
                    return self._lexical_similarity(text1, text2)
        v1 = self._embedding_cache[text1]
        v2 = self._embedding_cache[text2]
        return self._cosine_similarity(v1, v2)

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    def _lexical_similarity(self, text1: str, text2: str) -> float:
        terms1 = self._terms(text1)
        terms2 = self._terms(text2)
        if not terms1 or not terms2:
            return 0.0
        return len(terms1 & terms2) / max(len(terms1), len(terms2))

    def _term_overlap_ratio(self, text1: str, text2: str) -> float:
        terms1 = self._terms(text1)
        terms2 = self._terms(text2)
        if not terms1 or not terms2:
            return 0.0
        return len(terms1 & terms2) / len(terms1 | terms2)

    def _terms(self, text: str) -> Set[str]:
        if not text:
            return set()
        # 中英文 term 提取，过滤过短词和纯数字
        tokens = re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}", text.lower())
        return {t for t in tokens if len(t.strip()) >= 2 and not re.fullmatch(r"\d+", t)}

    def _diagnostics(
        self,
        claims: List[Claim],
        evidences: List[Evidence],
        results: List[ResultItem],
        experiments: List[Experiment],
        graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        all_ids = {c.claim_id for c in claims} | {e.evidence_id for e in evidences} | {r.result_id for r in results} | {x.experiment_id for x in experiments}
        connected = set(graph.keys())
        for targets in graph.values():
            connected.update(targets)
        isolated = sorted(all_ids - connected)
        return {
            "node_count": len(all_ids),
            "edge_source_count": len(graph),
            "isolated_nodes": isolated,
            "isolated_count": len(isolated),
        }

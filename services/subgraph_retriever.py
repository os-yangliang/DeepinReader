from collections import deque
import re
from typing import Dict, List, Tuple

from services.paper_schema import EvidenceBundle, PaperProfile, QuestionRoute, ReasoningChain


class SubgraphRetriever:
    def retrieve(self, profile: PaperProfile, route_type: QuestionRoute, question: str = "", max_hops: int = 3, top_k: int = 8) -> Dict[str, List]:
        if not profile:
            return {"anchor_ids": [], "paths": [], "visited_ids": [], "chains": []}
        node_text = self._node_text_map(profile)
        node_type = self._node_type_map(profile)
        adjacency = {}
        edge_conf = {}
        for edge in profile.graph_edges:
            adjacency.setdefault(edge.source_id, []).append((edge.target_id, edge.edge_type.value))
            edge_conf[(edge.source_id, edge.target_id, edge.edge_type.value)] = edge.confidence
        anchor_ids = self._select_anchors(profile, route_type, question, node_text)
        if not anchor_ids:
            return {"anchor_ids": [], "paths": [], "visited_ids": [], "chains": []}
        raw_paths = self._enumerate_paths(anchor_ids, adjacency, max_hops) or [([anchor_id], []) for anchor_id in anchor_ids]
        chains = []
        visited = set(anchor_ids)
        for idx, (nodes, edge_types) in enumerate(raw_paths):
            visited.update(nodes)
            chains.append(self._build_chain(idx, nodes, edge_types, node_text, node_type, edge_conf, route_type, question))
        chains.sort(key=lambda item: item.score, reverse=True)
        selected = chains[:top_k]
        for chain in selected:
            visited.update(chain.nodes)
        return {
            "anchor_ids": anchor_ids,
            "paths": [self._typed_path(chain.nodes, chain.edge_types) for chain in selected],
            "visited_ids": list(visited),
            "chains": selected,
        }

    def enrich_bundle(self, bundle: EvidenceBundle, profile: PaperProfile, subgraph: Dict[str, List]):
        visited_ids = set(subgraph.get("visited_ids", []))
        if not visited_ids:
            return bundle
        section_ids = {s.section_id for s in bundle.sections}
        claim_ids = {c.claim_id for c in bundle.target_claims}
        evidence_ids = {e.evidence_id for e in bundle.evidences}
        result_ids = {r.result_id for r in bundle.results}
        for section in profile.sections:
            if section.section_id in visited_ids and section.section_id not in section_ids:
                bundle.sections.append(section)
        for claim in profile.claims:
            if claim.claim_id in visited_ids and claim.claim_id not in claim_ids:
                bundle.target_claims.append(claim)
        for evidence in profile.evidences:
            if evidence.evidence_id in visited_ids and evidence.evidence_id not in evidence_ids:
                bundle.evidences.append(evidence)
        for result in profile.results:
            if result.result_id in visited_ids and result.result_id not in result_ids:
                bundle.results.append(result)
        bundle.reasoning_chains = subgraph.get("chains", [])[:8]
        return bundle

    def _enumerate_paths(self, anchor_ids: List[str], adjacency: Dict[str, List[Tuple[str, str]]], max_hops: int):
        paths = []
        queue = deque((anchor_id, [anchor_id], [], 0) for anchor_id in anchor_ids)
        seen = set()
        while queue:
            node_id, nodes, edge_types, depth = queue.popleft()
            state = (node_id, tuple(nodes), tuple(edge_types))
            if state in seen:
                continue
            seen.add(state)
            if depth > 0:
                paths.append((nodes, edge_types))
            if depth >= max_hops:
                continue
            for target_id, edge_type in adjacency.get(node_id, []):
                if target_id not in nodes:
                    queue.append((target_id, nodes + [target_id], edge_types + [edge_type], depth + 1))
        return paths

    def _build_chain(self, idx, nodes, edge_types, node_text, node_type, edge_conf, route_type, question) -> ReasoningChain:
        chain_text = "\n".join(f"[{node_type.get(node, 'node')}] {node_text.get(node, '')[:280]}" for node in nodes)
        similarity = self._lexical_similarity(question, chain_text)
        type_match = self._type_match_score([node_type.get(node, "") for node in nodes], edge_types, route_type)
        confidence = self._edge_confidence(nodes, edge_types, edge_conf)
        strength = self._evidence_strength(nodes, node_type, node_text)
        completeness = self._chain_completeness([node_type.get(node, "") for node in nodes], route_type)
        score = 0.35 * similarity + 0.25 * type_match + 0.15 * confidence + 0.15 * strength + 0.10 * completeness
        return ReasoningChain(
            chain_id=f"chain_{idx + 1}", nodes=nodes, edge_types=edge_types, text=chain_text,
            chain_type="-".join(node_type.get(node, "node") for node in nodes), score=round(score, 4),
            similarity_score=round(similarity, 4), type_match_score=round(type_match, 4),
            edge_confidence=round(confidence, 4), evidence_strength=round(strength, 4), completeness=round(completeness, 4),
        )

    def _select_anchors(self, profile: PaperProfile, route_type: QuestionRoute, question: str, node_text: Dict[str, str]) -> List[str]:
        if route_type == QuestionRoute.STRUCTURE:
            candidates = [s.section_id for s in profile.sections[:8]]
        elif route_type == QuestionRoute.METHOD:
            candidates = [s.section_id for s in profile.sections if s.section_type.value in {"method", "introduction"}] + [c.claim_id for c in profile.claims if c.claim_type.value in {"causal", "general", "contribution"}]
        elif route_type == QuestionRoute.EVIDENCE:
            candidates = [c.claim_id for c in profile.claims] + [e.evidence_id for e in profile.evidences]
        elif route_type == QuestionRoute.RESULT:
            candidates = [r.result_id for r in profile.results] + [s.section_id for s in profile.sections if s.section_type.value in {"experiment", "result", "ablation"}]
        elif route_type == QuestionRoute.CRITICAL:
            candidates = (
                [c.claim_id for c in profile.claims if c.claim_type.value == "limitation"]
                + [s.section_id for s in profile.sections if s.section_type.value in {"limitation", "conclusion", "experiment", "result", "ablation"}]
                + [r.result_id for r in profile.results]
                + [e.evidence_id for e in profile.evidences]
                + [c.claim_id for c in profile.claims[:6]]
            )
        else:
            candidates = [c.claim_id for c in profile.claims[:6]] + [s.section_id for s in profile.sections[:4]]
        scored = sorted(((self._lexical_similarity(question, node_text.get(node_id, "")), node_id) for node_id in dict.fromkeys(candidates)), reverse=True)
        return [node_id for _, node_id in scored[:4] if node_id] or [s.section_id for s in profile.sections[:1]] + [c.claim_id for c in profile.claims[:1]]

    def _node_text_map(self, profile: PaperProfile) -> Dict[str, str]:
        data = {s.section_id: f"{s.title}. {s.content[:900]}" for s in profile.sections}
        data.update({c.claim_id: c.text for c in profile.claims})
        data.update({e.evidence_id: e.text for e in profile.evidences})
        data.update({x.experiment_id: " ".join([x.name, x.dataset, ", ".join(x.metrics)]).strip() for x in profile.experiments})
        data.update({r.result_id: " ".join([r.text, r.dataset, r.metric, r.value]).strip() for r in profile.results})
        return data

    def _node_type_map(self, profile: PaperProfile) -> Dict[str, str]:
        data = {s.section_id: "section" for s in profile.sections}
        data.update({c.claim_id: "claim" for c in profile.claims})
        data.update({e.evidence_id: "evidence" for e in profile.evidences})
        data.update({x.experiment_id: "experiment" for x in profile.experiments})
        data.update({r.result_id: "result" for r in profile.results})
        return data
    def _typed_path(self, nodes: List[str], edge_types: List[str]) -> List[str]:
        path = []
        for idx, node in enumerate(nodes):
            path.append(node)
            if idx < len(edge_types):
                path.append(f"--{edge_types[idx]}-->")
        return path

    def _lexical_similarity(self, question: str, text: str) -> float:
        q_terms = self._terms(question)
        t_terms = self._terms(text)
        if not q_terms or not t_terms:
            return 0.0
        return min(1.0, len(q_terms & t_terms) / max(1, len(q_terms)))

    def _terms(self, text: str):
        return {term.lower() for term in re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]{2,}", text or "") if len(term.strip()) >= 2}

    def _type_match_score(self, types: List[str], edge_types: List[str], route_type: QuestionRoute) -> float:
        type_set = set(types)
        edge_set = set(edge_types)
        if route_type == QuestionRoute.STRUCTURE:
            return 1.0 if "section" in type_set else 0.4
        if route_type == QuestionRoute.METHOD:
            return self._coverage(type_set, {"section", "claim"})
        if route_type == QuestionRoute.EVIDENCE:
            return min(1.0, self._coverage(type_set, {"claim", "evidence"}) + (0.2 if {"supported_by", "supports"} & edge_set else 0.0))
        if route_type == QuestionRoute.RESULT:
            return self._coverage(type_set, {"result", "experiment"})
        if route_type == QuestionRoute.CRITICAL:
            return min(1.0, self._coverage(type_set, {"claim", "evidence", "result", "section"}) + (0.2 if "limited_by" in edge_set else 0.0))
        return self._coverage(type_set, {"section", "claim", "evidence"})

    def _coverage(self, observed, expected) -> float:
        return len(observed & expected) / len(expected) if expected else 0.0

    def _edge_confidence(self, nodes: List[str], edge_types: List[str], edge_conf: Dict[Tuple[str, str, str], float]) -> float:
        if not edge_types:
            return 0.5
        scores = [edge_conf.get((nodes[idx], nodes[idx + 1], edge_type), 0.5) for idx, edge_type in enumerate(edge_types)]
        return sum(scores) / len(scores)

    def _evidence_strength(self, nodes: List[str], node_type: Dict[str, str], node_text: Dict[str, str]) -> float:
        score = 0.0
        if any(node_type.get(node) == "evidence" for node in nodes):
            score += 0.35
        if any(node_type.get(node) == "result" for node in nodes):
            score += 0.3
        if any(node_type.get(node) == "experiment" for node in nodes):
            score += 0.2
        joined = " ".join(node_text.get(node, "") for node in nodes).lower()
        if re.search(r"\d+(\.\d+)?\s*%?|accuracy|f1|bleu|rouge|auc|score|improve|outperform", joined):
            score += 0.15
        return min(1.0, score)

    def _chain_completeness(self, types: List[str], route_type: QuestionRoute) -> float:
        type_set = set(types)
        if route_type == QuestionRoute.EVIDENCE:
            return self._coverage(type_set, {"claim", "evidence", "result"})
        if route_type == QuestionRoute.RESULT:
            return self._coverage(type_set, {"experiment", "result", "claim"})
        if route_type == QuestionRoute.METHOD:
            return self._coverage(type_set, {"section", "claim"})
        if route_type == QuestionRoute.CRITICAL:
            return self._coverage(type_set, {"claim", "evidence", "result", "section"})
        return min(1.0, len(type_set) / 3)

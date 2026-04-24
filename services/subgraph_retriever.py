from collections import deque
from typing import Dict, List

from services.paper_schema import EvidenceBundle, GraphEdgeType, PaperProfile, QuestionRoute


class SubgraphRetriever:
    def retrieve(self, profile: PaperProfile, route_type: QuestionRoute, max_hops: int = 2) -> Dict[str, List[str]]:
        if not profile:
            return {"anchor_ids": [], "paths": [], "visited_ids": []}

        anchor_ids = self._select_anchors(profile, route_type)
        if not anchor_ids:
            return {"anchor_ids": [], "paths": [], "visited_ids": []}

        adjacency = {}
        for edge in profile.graph_edges:
            adjacency.setdefault(edge.source_id, []).append((edge.target_id, edge.edge_type.value))

        visited = set(anchor_ids)
        paths = []
        queue = deque((anchor_id, [anchor_id], 0) for anchor_id in anchor_ids)

        while queue:
            node_id, path, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for target_id, edge_type in adjacency.get(node_id, []):
                typed_path = path + [f"--{edge_type}-->", target_id]
                paths.append(typed_path)
                if target_id not in visited:
                    visited.add(target_id)
                    queue.append((target_id, path + [target_id], depth + 1))

        return {
            "anchor_ids": anchor_ids,
            "paths": paths[:8],
            "visited_ids": list(visited),
        }

    def enrich_bundle(self, bundle: EvidenceBundle, profile: PaperProfile, subgraph: Dict[str, List[str]]):
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

        return bundle

    def _select_anchors(self, profile: PaperProfile, route_type: QuestionRoute) -> List[str]:
        if route_type == QuestionRoute.STRUCTURE:
            return [section.section_id for section in profile.sections[:2]]
        if route_type == QuestionRoute.METHOD:
            claims = [claim.claim_id for claim in profile.claims[:2]]
            sections = [section.section_id for section in profile.sections if section.section_type.value == "method"][:1]
            return claims + sections
        if route_type == QuestionRoute.EVIDENCE:
            return [claim.claim_id for claim in profile.claims[:2]] or [e.evidence_id for e in profile.evidences[:2]]
        if route_type == QuestionRoute.RESULT:
            return [result.result_id for result in profile.results[:2]] or [section.section_id for section in profile.sections if section.section_type.value in {"experiment", "result"}][:1]
        if route_type == QuestionRoute.CRITICAL:
            return [claim.claim_id for claim in profile.claims[:1]] + [section.section_id for section in profile.sections if section.section_type.value == "limitation"][:1]
        return [claim.claim_id for claim in profile.claims[:1]] + [section.section_id for section in profile.sections[:1]]

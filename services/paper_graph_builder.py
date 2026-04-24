from services.paper_schema import GraphEdge, GraphEdgeType, PaperProfile, ProvenanceSpan


class PaperGraphBuilder:
    def build(self, document_id: str, title: str, sections, extracted: dict) -> PaperProfile:
        claims = extracted.get("claims", [])
        evidences = extracted.get("evidences", [])
        results = extracted.get("results", [])
        experiments = extracted.get("experiments", [])

        graph = {}
        graph_edges = []
        evidence_ids = [e.evidence_id for e in evidences]
        result_ids = [r.result_id for r in results]

        for section in sections:
            section_targets = []
            for claim in claims:
                if claim.section_id == section.section_id:
                    section_targets.append(claim.claim_id)
                    graph_edges.append(self._make_edge(section.section_id, claim.claim_id, GraphEdgeType.CONTAINS, section))
            for evidence in evidences:
                if evidence.section_id == section.section_id:
                    section_targets.append(evidence.evidence_id)
                    graph_edges.append(self._make_edge(section.section_id, evidence.evidence_id, GraphEdgeType.CONTAINS, section))
            for experiment in experiments:
                if experiment.section_id == section.section_id:
                    section_targets.append(experiment.experiment_id)
                    graph_edges.append(self._make_edge(section.section_id, experiment.experiment_id, GraphEdgeType.CONTAINS, section))
            for result in results:
                if result.section_id == section.section_id:
                    section_targets.append(result.result_id)
                    graph_edges.append(self._make_edge(section.section_id, result.result_id, GraphEdgeType.CONTAINS, section))
            if section_targets:
                graph[section.section_id] = section_targets

        for claim in claims:
            claim.evidence_ids = evidence_ids[:2]
            graph[claim.claim_id] = claim.evidence_ids.copy()
            for evidence_id in claim.evidence_ids:
                evidence = next((item for item in evidences if item.evidence_id == evidence_id), None)
                if evidence:
                    graph_edges.append(self._make_edge(claim.claim_id, evidence_id, GraphEdgeType.SUPPORTED_BY, claim.provenance or evidence.provenance))

        for idx, evidence in enumerate(evidences):
            related_claims = [c.claim_id for c in claims[:2]]
            evidence.related_claim_ids = related_claims
            graph[evidence.evidence_id] = result_ids[idx:idx + 1]
            for result_id in graph[evidence.evidence_id]:
                result = next((item for item in results if item.result_id == result_id), None)
                if result:
                    graph_edges.append(self._make_edge(evidence.evidence_id, result_id, GraphEdgeType.DERIVED_FROM, evidence.provenance or result.provenance))

        for result in results:
            result.supports_claim_ids = [c.claim_id for c in claims[:1]]
            graph[result.result_id] = [e.experiment_id for e in experiments[:1]]
            for claim_id in result.supports_claim_ids:
                graph_edges.append(self._make_edge(result.result_id, claim_id, GraphEdgeType.SUPPORTS, result.provenance))
            for experiment_id in graph[result.result_id]:
                experiment = next((item for item in experiments if item.experiment_id == experiment_id), None)
                if experiment:
                    graph_edges.append(self._make_edge(result.result_id, experiment_id, GraphEdgeType.DERIVED_FROM, result.provenance or experiment.provenance))

        abstract = ""
        for section in sections:
            if section.section_type.value == "abstract":
                abstract = section.content[:2000]
                break

        return PaperProfile(
            document_id=document_id,
            title=title,
            abstract=abstract,
            sections=sections,
            claims=claims,
            evidences=evidences,
            experiments=experiments,
            results=results,
            contributions=extracted.get("contributions", []),
            limitations=extracted.get("limitations", []),
            graph=graph,
            graph_edges=graph_edges,
        )


    def _make_edge(self, source_id: str, target_id: str, edge_type: GraphEdgeType, provenance_source) -> GraphEdge:
        provenance = provenance_source if isinstance(provenance_source, ProvenanceSpan) else None
        return GraphEdge(source_id=source_id, target_id=target_id, edge_type=edge_type, provenance=provenance, confidence=0.7)

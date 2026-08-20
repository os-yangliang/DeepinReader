from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SectionType(str, Enum):
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    RELATED_WORK = "related_work"
    METHOD = "method"
    EXPERIMENT = "experiment"
    RESULT = "result"
    ABLATION = "ablation"
    CONCLUSION = "conclusion"
    LIMITATION = "limitation"
    APPENDIX = "appendix"
    OTHER = "other"


class ClaimType(str, Enum):
    CONTRIBUTION = "contribution"
    PERFORMANCE = "performance"
    COMPARISON = "comparison"
    CAUSAL = "causal"
    LIMITATION = "limitation"
    GENERAL = "general"


class QuestionRoute(str, Enum):
    STRUCTURE = "structure"
    METHOD = "method"
    EVIDENCE = "evidence"
    RESULT = "result"
    CRITICAL = "critical"
    GENERAL = "general"


class GraphNodeType(str, Enum):
    SECTION = "section"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    EXPERIMENT = "experiment"
    RESULT = "result"
    CONTRIBUTION = "contribution"
    LIMITATION = "limitation"


class GraphEdgeType(str, Enum):
    CONTAINS = "contains"
    SUPPORTED_BY = "supported_by"
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    LIMITED_BY = "limited_by"
    RELATED_TO = "related_to"


class ProvenanceSpan(BaseModel):
    section_id: str = ""
    page: int = 0
    start_line: int = 0
    end_line: int = 0
    snippet: str = ""


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: GraphEdgeType = GraphEdgeType.RELATED_TO
    provenance: Optional[ProvenanceSpan] = None
    confidence: float = 0.5


class PaperSection(BaseModel):
    section_id: str
    title: str
    level: int = 1
    section_type: SectionType = SectionType.OTHER
    content: str = ""
    start_line: int = 0
    end_line: int = 0


class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: ClaimType = ClaimType.GENERAL
    section_id: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    provenance: Optional[ProvenanceSpan] = None


class Evidence(BaseModel):
    evidence_id: str
    text: str
    section_id: str = ""
    related_claim_ids: List[str] = Field(default_factory=list)
    strength: str = "medium"
    provenance: Optional[ProvenanceSpan] = None


class Experiment(BaseModel):
    experiment_id: str
    name: str = ""
    dataset: str = ""
    metrics: List[str] = Field(default_factory=list)
    section_id: str = ""
    provenance: Optional[ProvenanceSpan] = None


class ResultItem(BaseModel):
    result_id: str
    text: str
    dataset: str = ""
    metric: str = ""
    value: str = ""
    section_id: str = ""
    supports_claim_ids: List[str] = Field(default_factory=list)
    provenance: Optional[ProvenanceSpan] = None


class PaperProfile(BaseModel):
    document_id: str
    title: str = ""
    abstract: str = ""
    sections: List[PaperSection] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    evidences: List[Evidence] = Field(default_factory=list)
    experiments: List[Experiment] = Field(default_factory=list)
    results: List[ResultItem] = Field(default_factory=list)
    contributions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    graph: Dict[str, List[str]] = Field(default_factory=dict)
    graph_edges: List[GraphEdge] = Field(default_factory=list)


class ReasoningChain(BaseModel):
    chain_id: str = ""
    nodes: List[str] = Field(default_factory=list)
    edge_types: List[str] = Field(default_factory=list)
    text: str = ""
    chain_type: str = "general"
    score: float = 0.0
    similarity_score: float = 0.0
    type_match_score: float = 0.0
    edge_confidence: float = 0.0
    evidence_strength: float = 0.0
    completeness: float = 0.0


class SufficiencyReport(BaseModel):
    score: float = 0.0
    label: str = "insufficient"
    coverage: float = 0.0
    support: float = 0.0
    consistency: float = 0.0
    missing_penalty: float = 0.0
    route_match: float = 0.0
    missing_factors: List[str] = Field(default_factory=list)
    should_abstain: bool = False


class EvidenceBundle(BaseModel):
    route: QuestionRoute = QuestionRoute.GENERAL
    target_claims: List[Claim] = Field(default_factory=list)
    evidences: List[Evidence] = Field(default_factory=list)
    results: List[ResultItem] = Field(default_factory=list)
    sections: List[PaperSection] = Field(default_factory=list)
    source_chunks: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    reasoning_chains: List[ReasoningChain] = Field(default_factory=list)
    sufficiency: Optional[SufficiencyReport] = None


class VerificationReport(BaseModel):
    confidence: float = 0.5
    supported_points: List[str] = Field(default_factory=list)
    unsupported_points: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    consistency_score: float = 0.0
    unsupported_claims: List[str] = Field(default_factory=list)
    evidence_coverage: float = 0.0


class CriticReport(BaseModel):
    unsupported_claims: List[str] = Field(default_factory=list)
    omissions_with_evidence: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    misalignment: List[str] = Field(default_factory=list)
    citation_issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    overall_verdict: str = "acceptable"
    reasoning: str = ""


class ArbiterDecision(BaseModel):
    chosen_answer: str = ""
    chosen_label: str = "A"
    reasoning: str = ""
    confidence: float = 0.5

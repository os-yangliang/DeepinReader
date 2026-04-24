import json
import os
from typing import List, Optional

from services.paper_schema import PaperProfile


class ObjectIndexer:
    def __init__(self, vector_store, persist_directory: str = "paper_profiles"):
        self.vector_store = vector_store
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)

    def get_profile_path(self, document_id: str) -> str:
        return os.path.join(self.persist_directory, f"{document_id}.json")

    def has_profile(self, document_id: str) -> bool:
        return os.path.exists(self.get_profile_path(document_id))

    def list_profiles(self) -> List[str]:
        return sorted(
            [filename[:-5] for filename in os.listdir(self.persist_directory) if filename.endswith(".json")]
        )

    def persist_profile(self, profile: PaperProfile):
        path = self.get_profile_path(profile.document_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))

    def load_profile(self, document_id: str) -> Optional[PaperProfile]:
        path = self.get_profile_path(document_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PaperProfile.model_validate(data)

    def index_profile(self, profile: PaperProfile):
        texts: List[str] = []
        metadatas = []

        for section in profile.sections:
            texts.append(f"[SECTION] {section.title}\n{section.content[:3000]}")
            metadatas.append({
                "object_type": "section",
                "section_id": section.section_id,
                "title": section.title,
                "section_type": section.section_type.value,
            })

        for claim in profile.claims:
            texts.append(f"[CLAIM] {claim.text}")
            metadatas.append({
                "object_type": "claim",
                "claim_id": claim.claim_id,
                "section_id": claim.section_id,
                "claim_type": claim.claim_type.value,
            })

        for evidence in profile.evidences:
            texts.append(f"[EVIDENCE] {evidence.text}")
            metadatas.append({
                "object_type": "evidence",
                "evidence_id": evidence.evidence_id,
                "section_id": evidence.section_id,
                "strength": evidence.strength,
            })

        for result in profile.results:
            texts.append(f"[RESULT] {result.text}")
            metadatas.append({
                "object_type": "result",
                "result_id": result.result_id,
                "section_id": result.section_id,
                "dataset": result.dataset,
                "metric": result.metric,
            })

        if texts:
            self.vector_store.add_documents(texts, metadatas)

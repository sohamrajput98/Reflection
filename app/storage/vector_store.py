from __future__ import annotations
import uuid
import hashlib
from threading import Lock
from typing import Any

import numpy as np

from app.core.config import Settings
from app.models.schemas import SemanticSearchResult

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class SemanticMemoryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = Lock()
        self._client = None

        if settings.openai_api_key and OpenAI is not None:
            self._client = OpenAI(api_key=settings.openai_api_key)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._client is not None:
            try:
                response = self._client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                print(f"Embedding failed, falling back: {e}")
                

        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str, dimensions: int = 384) -> list[float]:
        vector = np.zeros(dimensions, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % dimensions
            vector[index] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.astype(float).tolist()

    # ------------------------------------------------------------------
    # UPSERT INTO SUPABASE
    # ------------------------------------------------------------------

    def upsert_documents(self, supabase, documents: list[dict[str, Any]]) -> bool:
        """
        Each document dict must have:
            source_table, source_id, agent_id, summary
        Optional: metadata, created_at
        """
        if not documents:
            return True

        summaries = [doc["summary"] for doc in documents]
        embeddings = self._embed_texts(summaries)

        rows = [
            {
                "source_table": doc.get("source_table"),
                "source_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, str(doc.get("source_id")))),
                "agent_id": doc.get("agent_id"),
                "summary": doc.get("summary"),
                "embedding": embedding,
                "created_at": doc.get("created_at"),
            }
            for doc, embedding in zip(documents, embeddings)
        ]

        supabase.table("agent_embeddings").insert(rows).execute()
        return True

    # ------------------------------------------------------------------
    # QUERY SIMILAR FROM SUPABASE
    # ------------------------------------------------------------------

    def query_similar(
        self,
        supabase,
        query_text: str,
        *,
        n_results: int = 3,
    ) -> list[SemanticSearchResult]:
        query_embedding = self._embed_texts([query_text])[0]

        response = supabase.rpc(
            "match_agent_embeddings",
            {
                "query_embedding": query_embedding,
                "p_agent_id": self.settings.agent_id,
                "match_count": n_results,
            },
        ).execute()

        seen_campaigns = set()
        results = []
        
        for item in response.data or []:
            campaign_id = item.get("source_id")
            if campaign_id and campaign_id not in seen_campaigns:
                seen_campaigns.add(campaign_id)
                results.append(
                    SemanticSearchResult(
                        document_id=item["id"],
                        campaign_id=campaign_id,
                        score=item.get("similarity", 0.0),
                        summary=item.get("summary", ""),
                        metadata={},
                    )
                )
        
        return results
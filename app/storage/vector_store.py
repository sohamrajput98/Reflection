from __future__ import annotations

import hashlib
import uuid
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
        self._client = None

        if settings.openai_api_key and OpenAI is not None:
            self._client = OpenAI(api_key=settings.openai_api_key, base_url=settings.base_url)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._client is not None:
            try:
                request_kwargs = {
                    "model": self.settings.embedding_model,
                    "input": texts,
                }
                if self.settings.embedding_model == "text-embedding-3-small":
                    request_kwargs["dimensions"] = 384
                response = self._client.embeddings.create(**request_kwargs)
                return [item.embedding for item in response.data]
            except Exception:
                pass

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

    def upsert_documents(self, supabase, documents: list[dict[str, Any]]) -> bool:
        if not documents:
            return True

        summaries = [doc["summary"] for doc in documents]
        embeddings = self._embed_texts(summaries)

        rows = [
            {
                "source_table": doc.get("source_table"),
                "source_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, str(doc.get("source_id")))),
                "agent_id": doc.get("agent_id"),
                "summary": f"[CID:{doc.get('source_id')}] {doc.get('summary')}",
                "embedding": embedding,
                "created_at": doc.get("created_at"),
            }
            for doc, embedding in zip(documents, embeddings)
        ]
        supabase.table("agent_embeddings").insert(rows).execute()
        return True

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
            summary = item.get("summary", "")

            campaign_id = None
            if summary.startswith("[CID:"):
                try:
                    campaign_id = summary.split("[CID:")[1].split("]")[0]
                except Exception:
                    campaign_id = None

            if not campaign_id:
                campaign_id = item.get("source_id")

            if campaign_id and campaign_id not in seen_campaigns:
                seen_campaigns.add(campaign_id)
                results.append(
                    SemanticSearchResult(
                        document_id=item["id"],
                        campaign_id=campaign_id,
                        score=item.get("similarity", 0.0),
                        summary=summary,
                        metadata={},
                    )
                )

        return results

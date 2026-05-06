from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import time

from app.models.schemas import (
    AgentOutputIngestionRequest,
    AgentOutputListResponse,
    AgentOutputRecord,
    AgentOutputValidationResponse,
    ComparisonDeltas,
    ComparisonReport,
    InsightExtractionOutput,
    MetricDelta,
    MetricSnapshot,
    PatternReport,
    ReflectionTestResponse,
)
from app.orchestration.reflection_wrapper import ReflectionWrapper
from app.storage.supabase_repository import SupabaseRepository


@dataclass
class AgentIngestionService:
    repository: SupabaseRepository
    reflection_wrapper: ReflectionWrapper

    def _normalize_agent_id(self, agent_name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "_", agent_name.strip().lower())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or "unknown_agent"

    def ingest(
        self,
        payload: AgentOutputIngestionRequest,
        *,
        request_id: str,
    ) -> AgentOutputValidationResponse:
        started_at = time.monotonic()
        accepted_rows = []
        validation_errors = []
        parent_agent_name = payload.agent_name.strip()
        parent_agent_id = self._normalize_agent_id(parent_agent_name)
        parent_campaign_id = payload.campaign_id.strip() if payload.campaign_id else None

        for index, item in enumerate(payload.recommendations):
            try:
                normalized = {
                    "agent_name": parent_agent_name,
                    "agent_id": parent_agent_id,
                    "recommendation_id": item.source_recommendation_key.strip(),
                    "campaign_id": parent_campaign_id,
                    "recommendation_type": item.recommendation_type.strip().lower(),
                    "platform": item.platform.strip().lower(),
                    "action": item.action.strip(),
                    "confidence": float(item.confidence),
                    "priority": item.priority.strip().lower(),
                    "raw_payload": item.model_dump(mode="json"),
                }
                accepted_rows.append(normalized)
            except Exception as exc:
                validation_errors.append(
                    {
                        "index": index,
                        "agent_name": parent_agent_name,
                        "recommendation_id": getattr(item, "source_recommendation_key", None),
                        "error": str(exc),
                    }
                )

        stored_outputs = self.repository.save_agent_outputs(accepted_rows)
        latency_ms = round((time.monotonic() - started_at) * 1000)
        self.repository.log_ingestion(
            request_id=request_id,
            status="success" if not validation_errors else "partial_success",
            agent_name=parent_agent_name,
            recommendation_id=stored_outputs[0].recommendation_id if len(stored_outputs) == 1 else None,
            latency_ms=latency_ms,
            error_message=None if not validation_errors else str(validation_errors),
        )

        return AgentOutputValidationResponse(
            request_id=request_id,
            status="success" if not validation_errors else "partial_success",
            accepted_count=len(stored_outputs),
            dropped_count=len(validation_errors),
            validation_errors=validation_errors,
            stored_outputs=stored_outputs,
        )

    def list_recent_outputs(self, limit: int = 20) -> AgentOutputListResponse:
        return AgentOutputListResponse(outputs=self.repository.fetch_recent_agent_outputs(limit))

    def run_reflection_test(
        self,
        *,
        agent_name: str,
        request_id: str,
    ) -> ReflectionTestResponse:
        outputs = [item for item in self.repository.fetch_recent_agent_outputs(20) if item.agent_name == agent_name]
        recommendations = [item.action.strip() for item in outputs[:20] if item.action and item.action.strip()]

        comparison = ComparisonReport(
            campaign_id=f"debug-{agent_name}",
            generated_at=datetime.now(timezone.utc),
            expected_rates=MetricSnapshot(),
            actual_rates=MetricSnapshot(),
            deltas=ComparisonDeltas(
                ctr_diff=MetricDelta(),
                cvr_diff=MetricDelta(),
                cpa_diff=MetricDelta(),
                roas_diff=MetricDelta(),
            ),
            performance_score=0.0,
            summary=["Debug ingestion reflection run."],
        )
        pattern_report = PatternReport(
            campaign_id=f"debug-{agent_name}",
            generated_at=datetime.now(timezone.utc),
            pattern_report=[],
            auto_tags=[],
        )
        insights = InsightExtractionOutput(
            narrative_summary="Debug reflection run from ingested agent outputs.",
            recommendations=recommendations,
            key_learnings=[],
            anomalies=[],
            source="deterministic",
        )

        reflection = self.reflection_wrapper.safe_evaluate(
            comparison,
            pattern_report,
            insights,
            recommendations=recommendations,
            force_fallback=not recommendations,
        )

        return ReflectionTestResponse(
            request_id=request_id,
            validation_status="success" if recommendations else "empty",
            reflection_score=reflection.evaluation_score,
            dropped_recommendations=[],
        )

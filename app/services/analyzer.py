from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import BackgroundTasks

from app.core.config import Settings
from app.models.schemas import (
    AnalyzeCampaignResponse,
    CampaignPerformanceInput,
    RecommendationResponse,
    StorageConfirmation,
)
from app.services.comparator import PerformanceComparator
from app.services.feedback import FeedbackLoopEngine
from app.services.insight_service import InsightService
from app.services.pattern_detector import PatternDetectionEngine
from app.services.scoring import ScoringService
from app.storage.supabase_repository import SupabaseRepository  # ✅ was SQLiteRepository
from app.storage.vector_store import SemanticMemoryStore
from app.utils.io import write_json
from app.utils.normalization import normalize_signal_value


@dataclass
class ReflectionLearningEngine:
    settings: Settings
    repository: SupabaseRepository  # ✅ was SQLiteRepository
    vector_store: SemanticMemoryStore
    comparator: PerformanceComparator
    pattern_detector: PatternDetectionEngine
    insight_service: InsightService
    feedback_engine: FeedbackLoopEngine
    scoring_service: ScoringService
    supabase: Any

    def analyze_campaign(
        self,
        payload: CampaignPerformanceInput,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> AnalyzeCampaignResponse:
        history = self.repository.fetch_campaign_history()
        comparison = self.comparator.compare_performance(payload)
        pattern_report = self.pattern_detector.detect_patterns(
            history + [payload],
            focus_campaign_id=payload.campaign_id,
        )

        summary_text = self._build_campaign_summary(payload, comparison, pattern_report)
        similar_campaigns = []
        if background_tasks is None:
            similar_campaigns = self.vector_store.query_similar(
                self.supabase,
                summary_text,
                n_results=3,
            )
        insights = self.insight_service.generate_insights(pattern_report, comparison, similar_campaigns)

        self.repository.save_campaign(
            payload,
            summary_text=summary_text,
            auto_tags=pattern_report.auto_tags,
        )
        self.repository.save_performance_log(payload.campaign_id, comparison)
        self.repository.save_pattern_report(payload.campaign_id, pattern_report)
        self.repository.save_insights(payload.campaign_id, insights)

        # Defer vector writes for API requests when background tasks are available.
        vector_payload = [self._build_vector_document(payload, summary_text, pattern_report.auto_tags)]
        vector_saved = False
        if background_tasks is None:
            vector_saved = self.vector_store.upsert_documents(
                self.supabase,
                vector_payload,
            )
        else:
            background_tasks.add_task(
                self.vector_store.upsert_documents,
                self.supabase,
                vector_payload,
            )

        weights = self.feedback_engine.update_system_learnings(payload, comparison, pattern_report)
        output_path = (
            self._persist_outputs(payload.campaign_id, comparison, pattern_report, insights, weights)
            if self.settings.enable_local_output
            else None
        )

        return AnalyzeCampaignResponse(
            comparison_report=comparison,
            pattern_report=pattern_report,
            insights=insights,
            weights=weights,
            similar_campaigns=similar_campaigns,
            stored_memory=StorageConfirmation(
                sqlite_saved=False,
                vector_saved=vector_saved,
                output_path=str(output_path) if output_path else "",
            ),
        )

    def get_top_insights(self, limit: int | None = None):
        return self.repository.fetch_top_insights(limit or self.settings.insights_limit)

    def get_patterns(self, limit: int = 20):
        return self.repository.fetch_patterns(limit)

    def get_recommendations(
        self,
        *,
        platform: str | None = None,
        objective: str | None = None,
        include_similar_campaigns: bool = True,
    ) -> RecommendationResponse:
        top_insights = self.repository.fetch_top_insights(self.settings.insights_limit)
        top_patterns = self.repository.fetch_patterns(10)
        weight_snapshot = self.feedback_engine.get_current_snapshot()
        query_text = self.repository.fetch_latest_campaign_summary() or "campaign planning baseline"
        if platform or objective:
            query_text = f"{query_text} platform={platform or 'any'} objective={objective or 'any'}"

        similar_campaigns = []
        if include_similar_campaigns:
            similar_campaigns = self.vector_store.query_similar(
                self.supabase,
                query_text,
                n_results=3,
            )
        return self.insight_service.generate_recommendations(
            top_insights,
            top_patterns,
            weight_snapshot.signal_weights,
            similar_campaigns,
            platform=platform,
            objective=objective,
        )

    def _build_campaign_summary(
        self,
        payload: CampaignPerformanceInput,
        comparison,
        pattern_report,
    ) -> str:
        valid_audiences = []
        for audience in payload.audiences:
            audience_key = (
                audience.attributes.get("age_range")
                or audience.attributes.get("age_band")
                or audience.name
            )
            cleaned = normalize_signal_value(audience_key)
            if cleaned:
                valid_audiences.append(cleaned)

        audience_names = ", ".join(valid_audiences)
        if not audience_names:
            audience_names = ""

        valid_creatives = []
        for creative in payload.creatives:
            cleaned = normalize_signal_value(creative.type)
            if cleaned:
                valid_creatives.append(cleaned)

        creative_types = ", ".join(valid_creatives)
        if not creative_types:
            creative_types = ""

        comparison_summary = " ".join(comparison.summary[:3]) or "No metric deltas available."
        tags = ", ".join(pattern_report.auto_tags) or "no tags"

        return (
            f"Campaign {payload.campaign_id} on {payload.platform} for {payload.objective}. "
            f"Audiences: {audience_names}. Creatives: {creative_types}. "
            f"Actual CTR {comparison.actual_rates.ctr or 0:.2%}, CVR {comparison.actual_rates.cvr or 0:.2%}, "
            f"CPA {comparison.actual_rates.cpa or 0:.2f}. "
            f"Forecast delta summary: {comparison_summary} "
            f"Campaign tags: {tags}."
        )

    def _persist_outputs(
        self,
        campaign_id: str,
        comparison,
        pattern_report,
        insights,
        weights,
    ):
        campaign_output_dir = self.settings.output_dir / campaign_id
        write_json(campaign_output_dir / "comparison.json", comparison)
        write_json(campaign_output_dir / "patterns.json", pattern_report)
        write_json(campaign_output_dir / "insights.json", insights)
        write_json(campaign_output_dir / "updated_weights.json", weights)
        return campaign_output_dir

    def _build_vector_document(
        self,
        payload: CampaignPerformanceInput,
        summary_text: str,
        auto_tags: list[str],
    ) -> dict[str, Any]:
        return {
            "source_table": "campaigns",
            "source_id": payload.campaign_id,
            "agent_id": self.settings.agent_id,
            "summary": summary_text,
            "metadata": {
                "campaign_id": payload.campaign_id,
                "platform": payload.platform,
                "objective": payload.objective,
                "timestamp": payload.timestamp.isoformat(),
                "auto_tags": auto_tags,
            },
        }

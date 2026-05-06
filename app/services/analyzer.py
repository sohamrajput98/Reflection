from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import BackgroundTasks

from app.agents.supervisor_agent import SupervisorAgent
from app.core.config import Settings
from app.models.schemas import (
    AgentChatResponse,
    AgentOutputIngestionRequest,
    AgentOutputListResponse,
    AgentOutputValidationResponse,
    AnalyzeCampaignResponse,
    CampaignPerformanceInput,
    FeedbackActionResponse,
    ReflectionTestResponse,
    RecommendationResponse,
    RecommendationFeedbackRequest,
    RecommendationShownRequest,
)
from app.services.agent_ingestion import AgentIngestionService
from app.services.comparator import PerformanceComparator
from app.services.feedback import FeedbackLoopEngine
from app.services.insight_service import InsightService
from app.services.pattern_detector import PatternDetectionEngine
from app.services.scoring import ScoringService
from app.storage.supabase_repository import SupabaseRepository
from app.storage.vector_store import SemanticMemoryStore


@dataclass
class ReflectionLearningEngine:
    settings: Settings
    repository: SupabaseRepository
    vector_store: SemanticMemoryStore
    comparator: PerformanceComparator
    pattern_detector: PatternDetectionEngine
    insight_service: InsightService
    feedback_engine: FeedbackLoopEngine
    scoring_service: ScoringService
    supabase: Any
    supervisor_agent: SupervisorAgent
    agent_ingestion_service: AgentIngestionService

    def analyze_campaign(
        self,
        payload: CampaignPerformanceInput,
        *,
        background_tasks: BackgroundTasks | None = None,
        request_id: str | None = None,
    ) -> AnalyzeCampaignResponse:
        return self.supervisor_agent.analyze_campaign(
            payload,
            background_tasks=background_tasks,
            request_id=request_id,
        )

    def get_top_insights(self, limit: int | None = None):
        return self.repository.fetch_top_insights(limit or self.settings.insights_limit)

    def chat_with_agent(self, *, message: str, context: dict | None = None) -> AgentChatResponse:
        reply, model = self.insight_service.generate_chat_reply(
            message=message,
            context=context or {},
        )
        return AgentChatResponse(reply=reply, model=model)

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

    def mark_recommendation_shown(
        self,
        payload: RecommendationShownRequest,
        *,
        request_id: str | None = None,
    ) -> FeedbackActionResponse:
        self.repository.record_recommendation_shown(
            recommendation_id=payload.recommendation_id,
            campaign_id=payload.campaign_id,
            recommendation_type=payload.recommendation_type,
            platform=payload.platform,
            request_id=request_id,
        )
        return FeedbackActionResponse(status="shown_recorded", recommendation_id=payload.recommendation_id)

    def submit_recommendation_feedback(
        self,
        payload: RecommendationFeedbackRequest,
        *,
        request_id: str | None = None,
    ) -> FeedbackActionResponse:
        recorded = self.repository.record_recommendation_feedback(
            recommendation_id=payload.recommendation_id,
            accepted=payload.accepted,
            request_id=request_id,
        )
        if not recorded:
            raise ValueError("recommendation must be shown before feedback")
        return FeedbackActionResponse(status="feedback_recorded", recommendation_id=payload.recommendation_id)

    def ingest_agent_outputs(
        self,
        payload: AgentOutputIngestionRequest,
        *,
        request_id: str,
    ) -> AgentOutputValidationResponse:
        return self.agent_ingestion_service.ingest(payload, request_id=request_id)

    def get_recent_agent_outputs(self, limit: int = 20) -> AgentOutputListResponse:
        return self.agent_ingestion_service.list_recent_outputs(limit)

    def run_agent_ingestion_reflection_test(
        self,
        *,
        agent_name: str,
        request_id: str,
    ) -> ReflectionTestResponse:
        return self.agent_ingestion_service.run_reflection_test(
            agent_name=agent_name,
            request_id=request_id,
        )

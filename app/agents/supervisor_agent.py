from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Callable

from fastapi import BackgroundTasks
from pydantic import ValidationError

from app.agents.analysis_agent import AnalysisAgent
from app.agents.insight_agent import InsightAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.pattern_agent import PatternAgent
from app.core.config import Settings
from app.models.schemas import (
    AnalyzeCampaignResponse,
    CampaignPerformanceInput,
    ComparisonDeltas,
    ComparisonReport,
    InsightExtractionOutput,
    MetricDelta,
    MetricSnapshot,
    PatternReport,
    ReflectionEvaluation,
    SemanticSearchResult,
    StorageConfirmation,
    WeightSnapshot,
)
from app.orchestration.async_orchestrator import AsyncOrchestrator
from app.orchestration.recommendation_validation import validate_recommendation_output
from app.orchestration.reflection_wrapper import ReflectionWrapper
from app.services.feedback import FeedbackLoopEngine
from app.utils.io import write_json


logger = logging.getLogger(__name__)


@dataclass
class SupervisorAgent:
    settings: Settings
    analysis_agent: AnalysisAgent
    pattern_agent: PatternAgent
    insight_agent: InsightAgent
    memory_agent: MemoryAgent
    feedback_engine: FeedbackLoopEngine
    reflection_wrapper: ReflectionWrapper

    def analyze_campaign(
        self,
        payload: CampaignPerformanceInput,
        *,
        background_tasks: BackgroundTasks | None = None,
        request_id: str | None = None,
    ) -> AnalyzeCampaignResponse:
        if request_id:
            logger.info("analyze_campaign_started request_id=%s campaign_id=%s", request_id, payload.campaign_id)
        (
            comparison,
            pattern_report,
            summary_text,
            similar_campaigns,
            insights,
            validated_recommendations,
            vector_saved,
            weights,
            reflection_fallback_required,
        ) = asyncio.run(
            self._run_pipeline(
                payload,
                background_tasks=background_tasks,
                request_id=request_id,
            )
        )
        output_path = self._expected_output_path(payload.campaign_id)
        reflection = self._evaluate_reflection(
            comparison,
            pattern_report,
            insights,
            validated_recommendations,
            force_fallback=reflection_fallback_required,
            request_id=request_id,
        )
        if request_id:
            logger.info("analyze_campaign_completed request_id=%s campaign_id=%s", request_id, payload.campaign_id)

        return AnalyzeCampaignResponse(
            comparison_report=comparison,
            pattern_report=pattern_report,
            insights=insights,
            weights=weights,
            reflection=reflection,
            top_signals=[
                signal
                for signal, _ in sorted(weights.signal_weights.items(), key=lambda item: item[1], reverse=True)[:5]
            ],
            similar_campaigns=similar_campaigns,
            stored_memory=StorageConfirmation(
                sqlite_saved=False,
                vector_saved=vector_saved,
                output_path=str(output_path) if output_path else "",
            ),
        )

    async def _run_pipeline(
        self,
        payload: CampaignPerformanceInput,
        *,
        background_tasks: BackgroundTasks | None,
        request_id: str | None,
    ):
        orchestrator = AsyncOrchestrator(request_id=request_id)

        initial_results = await orchestrator.run_many(
            {
                "analysis_agent": lambda: self.analysis_agent.compare(payload),
                "pattern_agent": lambda: self.pattern_agent.detect(payload),
            }
        )
        analysis_failed = initial_results["analysis_agent"].status != "success"
        pattern_failed = initial_results["pattern_agent"].status != "success"
        comparison = self._validated_result_or_default(
            initial_results,
            "analysis_agent",
            lambda value: ComparisonReport.model_validate(value),
            self._fallback_comparison(payload),
        )
        pattern_report = self._validated_result_or_default(
            initial_results,
            "pattern_agent",
            lambda value: PatternReport.model_validate(value),
            self._fallback_pattern_report(payload),
        )

        insight_results = await orchestrator.run_many(
            {
                "insight_agent": lambda: self.insight_agent.generate(
                    payload,
                    comparison,
                    pattern_report,
                    include_similar_campaigns=True,
                ),
            }
        )
        insight_failed = insight_results["insight_agent"].status != "success"
        raw_insight_result = self._validated_result_or_default(
            insight_results,
            "insight_agent",
            self._validate_insight_result,
            self._fallback_insight_result(payload, comparison, pattern_report),
        )
        summary_text, similar_campaigns, insights = raw_insight_result
        validated_recommendations = self._collect_valid_recommendations(
            raw_insight_result,
            agent_name="insight_agent",
            request_id=request_id,
        )
        validated_recommendations = self._apply_recommendation_caps(
            validated_recommendations,
            agent_name="insight_agent",
            request_id=request_id,
        )
        reflection_fallback_required = analysis_failed and pattern_failed and insight_failed

        vector_saved = False
        weights = WeightSnapshot.model_validate(self.feedback_engine.get_current_snapshot())
        await self._schedule_background_followups(
            payload,
            comparison,
            pattern_report,
            insights,
            weights,
            summary_text=summary_text,
            background_tasks=background_tasks,
            request_id=request_id,
        )

        return (
            comparison,
            pattern_report,
            summary_text,
            similar_campaigns,
            insights,
            validated_recommendations,
            vector_saved,
            weights,
            reflection_fallback_required,
        )

    def _validated_result_or_default(
        self,
        results,
        job_name: str,
        validator: Callable[[Any], Any],
        default,
    ):
        result = results[job_name]
        if result.status != "success" or result.data is None:
            logger.warning(
                "supervisor_optional_agent_failed agent=%s request_id=%s latency_ms=%s failure_reason=%s",
                job_name,
                result.request_id,
                result.latency_ms,
                result.failure_reason or "unknown",
            )
            return default
        raw_value = result.data["result"]
        try:
            return validator(raw_value)
        except ValidationError as exc:
            logger.warning(
                "supervisor_invalid_agent_schema agent=%s request_id=%s latency_ms=%s error=%s",
                job_name,
                result.request_id,
                result.latency_ms,
                exc,
            )
            return default
        except Exception as exc:
            logger.warning(
                "supervisor_invalid_agent_result agent=%s request_id=%s latency_ms=%s error=%s",
                job_name,
                result.request_id,
                result.latency_ms,
                exc,
            )
            return default

    def _validate_insight_result(self, value: Any):
        if not isinstance(value, tuple) or len(value) != 3:
            raise ValueError("insight result must be a 3-item tuple")

        summary_text, similar_campaigns, insights = value
        if not isinstance(summary_text, str):
            raise ValueError("summary_text must be a string")

        validated_similar_campaigns = [
            SemanticSearchResult.model_validate(item) for item in similar_campaigns
        ]
        validated_insights = InsightExtractionOutput.model_validate(insights)
        return summary_text, validated_similar_campaigns, validated_insights

    def _collect_valid_recommendations(
        self,
        insight_result: tuple[str, list[SemanticSearchResult], InsightExtractionOutput],
        *,
        agent_name: str,
        request_id: str | None,
    ) -> list[str]:
        _, _, insights = insight_result
        return validate_recommendation_output(
            list(insights.recommendations),
            agent_name=agent_name,
            request_id=request_id,
        )

    def _apply_recommendation_caps(
        self,
        recommendations: list[str],
        *,
        agent_name: str,
        request_id: str | None,
    ) -> list[str]:
        capped = recommendations[: min(20, 100)]
        if len(capped) != len(recommendations):
            logger.info(
                "recommendation_caps_applied request_id=%s agent=%s original_count=%s capped_count=%s",
                request_id,
                agent_name,
                len(recommendations),
                len(capped),
            )
        return capped

    def _fallback_comparison(self, payload: CampaignPerformanceInput) -> ComparisonReport:
        return ComparisonReport(
            campaign_id=payload.campaign_id,
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
            summary=["Analysis temporarily unavailable."],
        )

    def _fallback_pattern_report(self, payload: CampaignPerformanceInput) -> PatternReport:
        return PatternReport(
            campaign_id=payload.campaign_id,
            generated_at=datetime.now(timezone.utc),
            pattern_report=["Pattern detection temporarily unavailable."],
        )

    def _fallback_insight_result(
        self,
        payload: CampaignPerformanceInput,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
    ):
        summary_text = (
            f"Campaign {payload.campaign_id} on {payload.platform} for {payload.objective}. "
            "Insight generation temporarily unavailable."
        )
        insights = InsightExtractionOutput(
            narrative_summary=(
                "Insight generation is temporarily unavailable. Review available comparison and pattern data."
            ),
            key_learnings=[*(comparison.summary[:1] or ["Comparison data unavailable."])],
            recommendations=[*(pattern_report.pattern_report[:1] or ["No recommendations available right now."])],
            anomalies=[],
            source="deterministic",
        )
        return summary_text, [], insights

    def _fallback_weights(self) -> WeightSnapshot:
        return WeightSnapshot(
            generated_at=datetime.now(timezone.utc),
            scoring_weights={},
            signal_weights={},
            updated_signals=[],
        )

    def _evaluate_reflection(
        self,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        recommendations: list[str],
        *,
        force_fallback: bool,
        request_id: str | None,
    ) -> ReflectionEvaluation:
        reflection = self.reflection_wrapper.safe_evaluate(
            comparison,
            pattern_report,
            insights,
            recommendations=recommendations,
            force_fallback=force_fallback,
        )
        logger.info(
            "reflection_evaluated request_id=%s evaluation_score=%s scoring_version=%s validated_recommendations=%s",
            request_id,
            reflection.evaluation_score,
            reflection.scoring_version,
            len(recommendations),
        )
        return reflection

    async def _schedule_background_followups(
        self,
        payload: CampaignPerformanceInput,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        weights: WeightSnapshot,
        *,
        summary_text: str,
        background_tasks: BackgroundTasks | None,
        request_id: str | None,
    ) -> None:
        if background_tasks is None:
            asyncio.create_task(
                asyncio.to_thread(
                    self._run_background_memory,
                    payload,
                    comparison,
                    pattern_report,
                    insights,
                    summary_text,
                    request_id,
                )
            )
            asyncio.create_task(
                asyncio.to_thread(
                    self._run_background_feedback,
                    payload,
                    comparison,
                    pattern_report,
                    request_id,
                )
            )
            if self.settings.enable_local_output:
                asyncio.create_task(
                    asyncio.to_thread(
                        self._run_background_output_persistence,
                        payload.campaign_id,
                        comparison,
                        pattern_report,
                        insights,
                        weights,
                        request_id,
                    )
                )
            await asyncio.sleep(0)
            return

        background_tasks.add_task(
            self._run_background_memory,
            payload,
            comparison,
            pattern_report,
            insights,
            summary_text,
            request_id,
        )
        background_tasks.add_task(
            self._run_background_feedback,
            payload,
            comparison,
            pattern_report,
            request_id,
        )
        if self.settings.enable_local_output:
            background_tasks.add_task(
                self._run_background_output_persistence,
                payload.campaign_id,
                comparison,
                pattern_report,
                insights,
                weights,
                request_id,
            )
        return

    def _expected_output_path(self, campaign_id: str):
        if not self.settings.enable_local_output:
            return None
        return self.settings.output_dir / campaign_id

    def _run_background_memory(
        self,
        payload: CampaignPerformanceInput,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        summary_text: str,
        request_id: str | None,
    ) -> None:
        try:
            self.memory_agent.persist(
                payload,
                comparison,
                pattern_report,
                insights,
                summary_text=summary_text,
                background_tasks=None,
            )
        except Exception as exc:
            logger.warning(
                "background_memory_failed request_id=%s campaign_id=%s error=%s",
                request_id,
                payload.campaign_id,
                exc,
            )

    def _run_background_feedback(
        self,
        payload: CampaignPerformanceInput,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        request_id: str | None,
    ) -> None:
        try:
            self.feedback_engine.update_system_learnings(payload, comparison, pattern_report)
        except Exception as exc:
            logger.warning(
                "background_feedback_failed request_id=%s campaign_id=%s error=%s",
                request_id,
                payload.campaign_id,
                exc,
            )

    def _run_background_output_persistence(
        self,
        campaign_id: str,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        weights: WeightSnapshot,
        request_id: str | None,
    ) -> None:
        try:
            self._persist_outputs(campaign_id, comparison, pattern_report, insights, weights)
        except Exception as exc:
            logger.warning(
                "background_output_persistence_failed request_id=%s campaign_id=%s error=%s",
                request_id,
                campaign_id,
                exc,
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

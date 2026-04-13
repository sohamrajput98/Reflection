from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from supabase import Client

from app.core.config import Settings
from app.models.schemas import (
    CampaignPerformanceInput,
    ComparisonReport,
    FeedbackSignal,
    InsightExtractionOutput,
    InsightRecord,
    PatternRecord,
    PatternReport,
)


class SupabaseRepository:
    def __init__(self, settings: Settings, supabase: Client) -> None:
        self.settings = settings
        self._db = supabase

    # ------------------------------------------------------------------
    # CAMPAIGNS
    # ------------------------------------------------------------------

    def save_campaign(
        self,
        payload: CampaignPerformanceInput,
        *,
        summary_text: str,
        auto_tags: list[str],
    ) -> None:
        self._db.table("campaigns").upsert(
            {
                "campaign_id": payload.campaign_id,
                "agent_id": self.settings.agent_id,
                "platform": payload.platform,
                "objective": payload.objective,
                "timestamp": payload.timestamp.isoformat(),
                "expected_metrics": payload.expected_metrics.model_dump(mode="json"),
                "actual_metrics": payload.actual_metrics.model_dump(mode="json"),
                "audiences": [a.model_dump(mode="json") for a in payload.audiences],
                "creatives": [c.model_dump(mode="json") for c in payload.creatives],
                "summary_text": summary_text,
                "auto_tags": auto_tags,
            },
            on_conflict="campaign_id",
        ).execute()

    def fetch_campaign_history(self, limit: int = 50) -> list[CampaignPerformanceInput]:
        response = (
            self._db.table("campaigns")
            .select("*")
            .eq("agent_id", self.settings.agent_id)
            .order("timestamp", desc=False)
            .limit(limit)
            .execute()
        )
        history: list[CampaignPerformanceInput] = []
        for row in response.data or []:
            history.append(
                CampaignPerformanceInput(
                    campaign_id=row["campaign_id"],
                    platform=row["platform"],
                    objective=row["objective"],
                    expected_metrics=row["expected_metrics"],
                    actual_metrics=row["actual_metrics"],
                    audiences=row["audiences"],
                    creatives=row["creatives"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
            )
        return history

    def fetch_latest_campaign_summary(self) -> str | None:
        response = (
            self._db.table("campaigns")
            .select("summary_text")
            .eq("agent_id", self.settings.agent_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0].get("summary_text")

    def insert_campaign_performance(self, agent_id: str, score: float) -> None:
        self._db.table("campaign_performance").insert({
            "agent_id": agent_id,
            "performance_score": score
        }).execute()
        
    # ------------------------------------------------------------------
    # PERFORMANCE LOGS
    # ------------------------------------------------------------------

    def save_performance_log(
        self,
        campaign_id: str,
        comparison: ComparisonReport,
    ) -> None:
        self._db.table("performance_logs").insert(
            {
                "campaign_id": campaign_id,
                "agent_id": self.settings.agent_id,
                "comparison": comparison.model_dump(mode="json"),
                "performance_score": comparison.performance_score,
            }
        ).execute()

    def fetch_performance_scores(self, limit: int = 25) -> list[float]:
        response = (
            self._db.table("performance_logs")
            .select("performance_score")
            .eq("agent_id", self.settings.agent_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [row["performance_score"] for row in response.data or []]

    # ------------------------------------------------------------------
    # PATTERNS
    # ------------------------------------------------------------------

    def save_pattern_report(
        self,
        campaign_id: str,
        pattern_report: PatternReport,
    ) -> None:
        findings = (
            pattern_report.winning_audiences
            + pattern_report.high_performing_creatives
            + pattern_report.budget_inefficiencies
            + pattern_report.platform_trends
            + pattern_report.clusters
        )
        if not findings:
            return

        rows = [
            {
                "campaign_id": campaign_id,
                "agent_id": self.settings.agent_id,
                "category": finding.category,
                "signal_key": finding.signal_key,
                "summary": finding.description,
                "impact_score": finding.impact_score,
                "metadata": finding.metadata,
            }
            for finding in findings
        ]
        self._db.table("patterns").insert(rows).execute()

    def fetch_patterns(self, limit: int = 20) -> list[PatternRecord]:
        response = (
            self._db.table("patterns")
            .select("id, campaign_id, category, signal_key, summary, impact_score, created_at")
            .eq("agent_id", self.settings.agent_id)
            .order("impact_score", desc=True)
            .limit(limit)
            .execute()
        )
        return [
            PatternRecord(
                id=row["id"],
                campaign_id=row["campaign_id"],
                category=row["category"],
                signal_key=row["signal_key"],
                summary=row["summary"],
                impact_score=row["impact_score"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in response.data or []
        ]

    # ------------------------------------------------------------------
    # INSIGHTS
    # ------------------------------------------------------------------

    def save_insights(
        self,
        campaign_id: str,
        insights: InsightExtractionOutput,
    ) -> None:
        rows: list[dict[str, Any]] = []
        for index, learning in enumerate(insights.key_learnings):
            rows.append({
                "campaign_id": campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "key_learning",
                "content": learning,
                "priority": max(1.0 - index * 0.1, 0.1),
            })
        for index, recommendation in enumerate(insights.recommendations):
            rows.append({
                "campaign_id": campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "recommendation",
                "content": recommendation,
                "priority": max(0.95 - index * 0.1, 0.1),
            })
        for anomaly in insights.anomalies:
            rows.append({
                "campaign_id": campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "anomaly",
                "content": anomaly,
                "priority": 1.0,
            })

        if rows:
            self._db.table("insights").insert(rows).execute()

    def fetch_top_insights(self, limit: int) -> list[InsightRecord]:
        response = (
            self._db.table("insights")
            .select("id, campaign_id, kind, content, priority, created_at")
            .eq("agent_id", self.settings.agent_id)
            .order("priority", desc=True)
            .limit(limit)
            .execute()
        )
        return [
            InsightRecord(
                id=row["id"],
                campaign_id=row["campaign_id"],
                kind=row["kind"],
                content=row["content"],
                priority=row["priority"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in response.data or []
        ]

    # ------------------------------------------------------------------
    # SIGNAL WEIGHTS
    # ------------------------------------------------------------------

    def fetch_signal_weights(self) -> dict[str, FeedbackSignal]:
        response = (
            self._db.table("signal_weights")
            .select("signal_key, weight, successes, failures, last_updated")
            .eq("agent_id", self.settings.agent_id)
            .execute()
        )
        return {
            row["signal_key"]: FeedbackSignal(
                signal_key=row["signal_key"],
                weight=row["weight"],
                successes=row["successes"],
                failures=row["failures"],
                last_updated=datetime.fromisoformat(row["last_updated"]),
            )
            for row in response.data or []
        }

    def upsert_signal_weights(self, signals: list[FeedbackSignal]) -> None:
        if not signals:
            return
        rows = [
            {
                "agent_id": self.settings.agent_id,
                "signal_key": s.signal_key,
                "weight": s.weight,
                "successes": s.successes,
                "failures": s.failures,
                "last_updated": s.last_updated.isoformat(),
            }
            for s in signals
        ]
        self._db.table("signal_weights").upsert(
            rows, on_conflict="agent_id,signal_key"
        ).execute()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def current_timestamp(self) -> datetime:
        return datetime.now(timezone.utc)
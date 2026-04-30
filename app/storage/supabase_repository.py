from __future__ import annotations

from datetime import datetime, timezone
import logging
from threading import Lock
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

logger = logging.getLogger(__name__)


class SupabaseRepository:
    def __init__(self, settings: Settings, supabase: Client) -> None:
        self.settings = settings
        self._db = supabase
        self._feedback_lock = Lock()

    def _storage_campaign_id(self, campaign_id: str) -> str:
        return f"{self.settings.agent_id}::{campaign_id}"

    def _public_campaign_id(self, campaign_id: str) -> str:
        prefix = f"{self.settings.agent_id}::"
        if campaign_id.startswith(prefix):
            return campaign_id[len(prefix):]
        return campaign_id

    def _supports_conflict_target(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "42p10" not in message and "no unique or exclusion constraint" not in message

    def _is_unique_violation(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "23505" in message or "duplicate key" in message or "unique constraint" in message

    def save_campaign(
        self,
        payload: CampaignPerformanceInput,
        *,
        summary_text: str,
        auto_tags: list[str],
    ) -> None:
        row = {
            "campaign_id": self._storage_campaign_id(payload.campaign_id),
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
        }
        try:
            self._db.table("campaigns").upsert(row, on_conflict="campaign_id").execute()
        except Exception as exc:
            if self._supports_conflict_target(exc):
                raise
            self._db.table("campaigns").insert(row).execute()

    def fetch_campaign_history(self, limit: int = 50) -> list[CampaignPerformanceInput]:
        if limit <= 0:
            return []

        response = (
            self._db.table("campaigns")
            .select(
                "campaign_id, platform, objective, expected_metrics, "
                "actual_metrics, audiences, creatives, timestamp"
            )
            .eq("agent_id", self.settings.agent_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        history: list[CampaignPerformanceInput] = []
        for row in reversed(response.data or []):
            history.append(
                CampaignPerformanceInput(
                    campaign_id=self._public_campaign_id(row["campaign_id"]),
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

    def save_performance_log(
        self,
        campaign_id: str,
        comparison: ComparisonReport,
    ) -> None:
        self._db.table("performance_logs").insert(
            {
                "campaign_id": self._storage_campaign_id(campaign_id),
                "agent_id": self.settings.agent_id,
                "comparison": comparison.model_dump(mode="json"),
                "performance_score": comparison.performance_score,
            }
        ).execute()

    def fetch_performance_scores(self, limit: int = 25) -> list[float]:
        query = (
            self._db.table("campaign_performance")
            .select("performance_score")
            .eq("agent_id", self.settings.agent_id)
            .limit(limit)
        )
        try:
            response = query.order("created_at", desc=True).execute()
        except Exception:
            response = query.execute()
        return [row["performance_score"] for row in response.data or []]

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

        storage_campaign_id = self._storage_campaign_id(campaign_id)
        seen: set[tuple[str, str, str]] = set()
        rows: list[dict[str, Any]] = []

        for finding in findings:
            key = (storage_campaign_id, finding.category, finding.signal_key)
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                {
                    "campaign_id": storage_campaign_id,
                    "agent_id": self.settings.agent_id,
                    "category": finding.category,
                    "signal_key": finding.signal_key,
                    "summary": finding.description,
                    "impact_score": finding.impact_score,
                    "metadata": finding.metadata,
                }
            )

        if rows:
            try:
                self._db.table("patterns").upsert(
                    rows,
                    on_conflict="campaign_id,category,signal_key",
                ).execute()
            except Exception as exc:
                if self._supports_conflict_target(exc):
                    raise
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
                campaign_id=self._public_campaign_id(row["campaign_id"]),
                category=row["category"],
                signal_key=row["signal_key"],
                summary=row["summary"],
                impact_score=row["impact_score"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in response.data or []
        ]

    def save_insights(
        self,
        campaign_id: str,
        insights: InsightExtractionOutput,
    ) -> None:
        storage_campaign_id = self._storage_campaign_id(campaign_id)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for index, learning in enumerate(insights.key_learnings):
            content = (learning or "").strip()
            if content.lower() in ("string", "unknown", "none", ""):
                continue

            key = (storage_campaign_id, "key_learning", content)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "campaign_id": storage_campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "key_learning",
                "content": content,
                "priority": max(1.0 - index * 0.1, 0.1),
            })

        for index, recommendation in enumerate(insights.recommendations):
            content = (recommendation or "").strip()
            if content.lower() in ("string", "unknown", "none", ""):
                continue

            key = (storage_campaign_id, "recommendation", content)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "campaign_id": storage_campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "recommendation",
                "content": content,
                "priority": max(0.95 - index * 0.1, 0.1),
            })

        for anomaly in insights.anomalies:
            content = (anomaly or "").strip()
            if content.lower() in ("string", "unknown", "none", ""):
                continue

            key = (storage_campaign_id, "anomaly", content)
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "campaign_id": storage_campaign_id,
                "agent_id": self.settings.agent_id,
                "kind": "anomaly",
                "content": content,
                "priority": 1.0,
            })

        if rows:
            try:
                self._db.table("insights").upsert(
                    rows,
                    on_conflict="campaign_id,kind,content",
                ).execute()
            except Exception as exc:
                if self._supports_conflict_target(exc):
                    raise
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
                campaign_id=self._public_campaign_id(row["campaign_id"]),
                kind=row["kind"],
                content=row["content"],
                priority=row["priority"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in response.data or []
        ]

    def _is_valid_signal(self, signal: str | None) -> bool:
        if not signal:
            return False

        s = signal.strip().lower()

        if s in ("string", "unknown", "none", ""):
            return False

        return True

    def fetch_signal_weights(self) -> dict[str, FeedbackSignal]:
        response = (
            self._db.table("signal_weights")
            .select("signal_key, weight, successes, failures, last_updated")
            .eq("agent_id", self.settings.agent_id)
            .execute()
        )

        cleaned = {}

        for row in response.data or []:
            signal = row["signal_key"]

            if not self._is_valid_signal(signal):
                continue

            cleaned[signal] = FeedbackSignal(
                signal_key=signal,
                weight=row["weight"],
                successes=row["successes"],
                failures=row["failures"],
                last_updated=datetime.fromisoformat(row["last_updated"]),
            )

        return cleaned

    def upsert_signal_weights(self, signals: list[FeedbackSignal]) -> None:
        if not signals:
            return
        rows = []

        for s in signals:
            if not self._is_valid_signal(s.signal_key):
                continue

            rows.append({
                "agent_id": self.settings.agent_id,
                "signal_key": s.signal_key,
                "weight": s.weight,
                "successes": s.successes,
                "failures": s.failures,
                "last_updated": s.last_updated.isoformat(),
            })

        if not rows:
            return
        self._db.table("signal_weights").upsert(
            rows, on_conflict="agent_id,signal_key"
        ).execute()

    def current_timestamp(self) -> datetime:
        return datetime.now(timezone.utc)

    def record_recommendation_shown(
        self,
        *,
        recommendation_id: str,
        campaign_id: str,
        recommendation_type: str,
        platform: str,
        request_id: str | None,
    ) -> None:
        row = {
            "recommendation_id": recommendation_id,
            "campaign_id": self._storage_campaign_id(campaign_id),
            "agent_id": self.settings.agent_id,
            "recommendation_type": recommendation_type,
            "platform": platform,
            "shown_at": self.current_timestamp().isoformat(),
            "request_id": request_id,
        }
        with self._feedback_lock:
            try:
                self._db.table("recommendation_feedback").upsert(
                    row,
                    on_conflict="recommendation_id",
                    ignore_duplicates=True,
                ).execute()
            except TypeError:
                try:
                    self._db.table("recommendation_feedback").insert(row).execute()
                except Exception as exc:
                    if not self._is_unique_violation(exc):
                        raise
            except Exception as exc:
                if not self._is_unique_violation(exc):
                    raise

            self._sync_recommendation_stats(
                recommendation_type=recommendation_type,
                platform=platform,
                request_id=request_id,
            )

    def fetch_recommendation_feedback_record(self, recommendation_id: str) -> dict[str, Any] | None:
        response = (
            self._db.table("recommendation_feedback")
            .select("recommendation_id, recommendation_type, platform, accepted, feedback_at")
            .eq("recommendation_id", recommendation_id)
            .eq("agent_id", self.settings.agent_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    def record_recommendation_feedback(
        self,
        *,
        recommendation_id: str,
        accepted: bool,
        request_id: str | None,
    ) -> bool:
        existing = self.fetch_recommendation_feedback_record(recommendation_id)
        if existing is None:
            return False

        with self._feedback_lock:
            row = {
                "recommendation_id": recommendation_id,
                "agent_id": self.settings.agent_id,
                "accepted": accepted,
                "feedback_at": self.current_timestamp().isoformat(),
                "feedback_request_id": request_id,
            }
            self._db.table("recommendation_feedback").upsert(
                row,
                on_conflict="recommendation_id",
            ).execute()

            self._sync_recommendation_stats(
                recommendation_type=existing["recommendation_type"],
                platform=existing["platform"],
                request_id=request_id,
            )
        return True

    def _sync_recommendation_stats(
        self,
        *,
        recommendation_type: str,
        platform: str,
        request_id: str | None,
    ) -> None:
        base_query = (
            self._db.table("recommendation_feedback")
            .eq("agent_id", self.settings.agent_id)
            .eq("recommendation_type", recommendation_type)
            .eq("platform", platform)
        )

        shown = base_query.select("recommendation_id", count="exact", head=True).execute().count or 0
        accepted = (
            self._db.table("recommendation_feedback")
            .select("recommendation_id", count="exact", head=True)
            .eq("agent_id", self.settings.agent_id)
            .eq("recommendation_type", recommendation_type)
            .eq("platform", platform)
            .eq("accepted", True)
            .execute()
            .count
            or 0
        )
        rejected = (
            self._db.table("recommendation_feedback")
            .select("recommendation_id", count="exact", head=True)
            .eq("agent_id", self.settings.agent_id)
            .eq("recommendation_type", recommendation_type)
            .eq("platform", platform)
            .eq("accepted", False)
            .execute()
            .count
            or 0
        )

        acceptance_rate = round((accepted / shown), 4) if shown else 0.0
        row = {
            "agent_id": self.settings.agent_id,
            "recommendation_type": recommendation_type,
            "platform": platform,
            "total_shown": shown,
            "total_accepted": accepted,
            "total_rejected": rejected,
            "acceptance_rate": acceptance_rate,
            "last_request_id": request_id,
            "updated_at": self.current_timestamp().isoformat(),
        }
        try:
            self._db.table("recommendation_stats").upsert(
                row,
                on_conflict="agent_id,recommendation_type,platform",
            ).execute()
        except Exception as exc:
            logger.warning(
                "recommendation_stats_sync_failed request_id=%s type=%s platform=%s error=%s",
                request_id,
                recommendation_type,
                platform,
                exc,
            )

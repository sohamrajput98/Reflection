from __future__ import annotations
from datetime import datetime, timezone
import numpy as np

from app.core.config import Settings
from app.models.schemas import (
    CampaignPerformanceInput,
    ComparisonReport,
    FeedbackSignal,
    PatternReport,
    WeightSnapshot,
)
from app.services.scoring import DEFAULT_SCORING_WEIGHTS
from app.storage.supabase_repository import SupabaseRepository
from app.utils.io import read_json, write_json


class FeedbackLoopEngine:
    def __init__(self, settings: Settings, repository: SupabaseRepository) -> None:
        self.settings = settings
        self.repository = repository
        self._ensure_weights_file()

    def update_system_learnings(
        self,
        payload: CampaignPerformanceInput,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
    ) -> WeightSnapshot:

        self.repository.insert_campaign_performance(
            self.settings.agent_id,
            comparison.performance_score,
        )

        baseline_scores = self.repository.fetch_performance_scores(limit=25)
        baseline = float(np.mean(baseline_scores)) if baseline_scores else comparison.performance_score

        relative_delta = 0.0
        if baseline != 0:
            relative_delta = (comparison.performance_score - baseline) / abs(baseline)

        signal_state = self.repository.fetch_signal_weights()
        tracked_signal_keys = self._collect_signal_keys(payload, pattern_report)
        updated_signals: list[FeedbackSignal] = []
        timestamp = datetime.now(timezone.utc)

        positive_signals = {
            finding.signal_key
            for finding in pattern_report.winning_audiences + pattern_report.high_performing_creatives
        }
        negative_signals = {
            finding.signal_key for finding in pattern_report.budget_inefficiencies
        }

        for signal_key in tracked_signal_keys:
            existing = signal_state.get(
                signal_key,
                FeedbackSignal(
                    signal_key=signal_key,
                    weight=1.0,
                    successes=0,
                    failures=0,
                    last_updated=timestamp,
                ),
            )

            adjustment = float(np.clip(relative_delta * 0.15, -0.12, 0.12))

            if signal_key in negative_signals:
                adjustment = min(adjustment, -0.05)

            if signal_key in positive_signals:
                adjustment = max(
                    adjustment,
                    0.05 if comparison.performance_score >= baseline else adjustment,
                )

            weight = float(np.clip(existing.weight * (1.0 + adjustment), 0.25, 5.0))

            updated_signals.append(
                FeedbackSignal(
                    signal_key=signal_key,
                    weight=round(weight, 4),
                    successes=existing.successes + (
                        1 if comparison.performance_score >= baseline else 0
                    ),
                    failures=existing.failures + (
                        0 if comparison.performance_score >= baseline else 1
                    ),
                    last_updated=timestamp,
                )
            )

        self.repository.upsert_signal_weights(updated_signals)
        merged_weights = self.repository.fetch_signal_weights()

        snapshot = WeightSnapshot(
            generated_at=timestamp,
            scoring_weights=dict(DEFAULT_SCORING_WEIGHTS),
            signal_weights={
                key: signal.weight for key, signal in sorted(merged_weights.items())
            },
            updated_signals=updated_signals,
        )

        write_json(self.settings.weights_path, snapshot)
        return snapshot

    def get_current_snapshot(self) -> WeightSnapshot:
        snapshot = read_json(self.settings.weights_path, None)
        if snapshot is None:
            self._ensure_weights_file()
            snapshot = read_json(self.settings.weights_path, {})
        return WeightSnapshot.model_validate(snapshot)

    def _ensure_weights_file(self) -> None:
        if self.settings.weights_path.exists():
            return

        snapshot = WeightSnapshot(
            generated_at=datetime.now(timezone.utc),
            scoring_weights=dict(DEFAULT_SCORING_WEIGHTS),
            signal_weights={},
            updated_signals=[],
        )

        write_json(self.settings.weights_path, snapshot)

    def _collect_signal_keys(
        self,
        payload: CampaignPerformanceInput,
        pattern_report: PatternReport,
    ) -> list[str]:

        platform = (payload.platform or "").strip().lower().replace(" ", "_")
        objective = (payload.objective or "").strip().lower().replace(" ", "_")

        signal_keys = {
            f"platform:{platform}",
            f"objective:{objective}",
        }

        # Audience loop
        for audience in payload.audiences:
            attrs = audience.attributes or {}
            audience_key = (
                attrs.get("age_range")
                or attrs.get("age_band")
                or audience.name
            )

            if (
                audience_key
                and str(audience_key).strip()
                and str(audience_key).lower() not in ("string", "unknown", "none", "")
            ):
                signal_keys.add(
                    f"audience:{str(audience_key).strip().lower().replace(' ', '_')}"
                )

        for creative in payload.creatives:
            raw_type = creative.type or ""
            cleaned = raw_type.strip().lower()

            creative_type = (
                cleaned := cleaned.strip().lower().replace("&", "and").replace(" ", "_")
                if cleaned and cleaned not in ("string", "unknown", "none")
                else "unknown_creative"
            )

        signal_keys.add(f"creative_type:{creative_type}")
        
        # Pattern report findings
        signal_keys.update(finding.signal_key for finding in pattern_report.winning_audiences)
        signal_keys.update(finding.signal_key for finding in pattern_report.high_performing_creatives)
        signal_keys.update(finding.signal_key for finding in pattern_report.budget_inefficiencies)
        signal_keys.update(finding.signal_key for finding in pattern_report.platform_trends)

        return sorted(signal_keys)
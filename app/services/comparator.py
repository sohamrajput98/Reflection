from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import (
    CampaignPerformanceInput,
    ComparisonDeltas,
    ComparisonReport,
)
from app.services.scoring import ScoringService
from app.utils.metrics import build_delta, compute_metric_snapshot


class PerformanceComparator:
    def __init__(self, scoring_service: ScoringService) -> None:
        self.scoring_service = scoring_service

    def compare_performance(self, payload: CampaignPerformanceInput) -> ComparisonReport:
        expected = compute_metric_snapshot(payload.expected_metrics)
        actual = compute_metric_snapshot(payload.actual_metrics)

        deltas = ComparisonDeltas(
            ctr_diff=build_delta(expected.ctr, actual.ctr),
            cvr_diff=build_delta(expected.cvr, actual.cvr),
            cpa_diff=build_delta(expected.cpa, actual.cpa, lower_is_better=True),
            roas_diff=build_delta(expected.roas, actual.roas),
        )
        score = self.scoring_service.compute_performance_score(payload.actual_metrics)

        summary = []
        if deltas.ctr_diff.pct_diff is not None:
            summary.append(f"CTR moved {deltas.ctr_diff.pct_diff:.2f}% versus forecast.")
        if deltas.cvr_diff.pct_diff is not None:
            summary.append(f"CVR moved {deltas.cvr_diff.pct_diff:.2f}% versus forecast.")
        if deltas.cpa_diff.pct_diff is not None:
            direction = "improved" if deltas.cpa_diff.favorable else "worsened"
            summary.append(f"CPA {direction} by {abs(deltas.cpa_diff.pct_diff):.2f}% versus forecast.")
        if deltas.roas_diff.pct_diff is None:
            summary.append("ROAS unavailable because revenue was not provided.")

        return ComparisonReport(
            campaign_id=payload.campaign_id,
            generated_at=datetime.now(timezone.utc),
            expected_rates=expected,
            actual_rates=actual,
            deltas=deltas,
            performance_score=score,
            summary=summary,
        )

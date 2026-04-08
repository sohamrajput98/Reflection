from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.core.config import Settings
from app.models.schemas import (
    ComparisonReport,
    InsightExtractionOutput,
    InsightRecord,
    PatternRecord,
    PatternReport,
    RecommendationResponse,
    SemanticSearchResult,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None


class InsightService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None
        if settings.openai_api_key and OpenAI is not None:
            self._client = OpenAI(api_key=settings.openai_api_key)

    def generate_insights(
        self,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput:
        if self._client is not None:
            generated = self._generate_with_openai(
                pattern_report=pattern_report,
                comparison_data=comparison_data,
                similar_campaigns=similar_campaigns,
            )
            if generated is not None:
                return generated

        return self._fallback_generate(
            pattern_report=pattern_report,
            comparison_data=comparison_data,
            similar_campaigns=similar_campaigns,
        )

    def generate_recommendations(
        self,
        top_insights: Sequence[InsightRecord],
        top_patterns: Sequence[PatternRecord],
        signal_weights: dict[str, float],
        similar_campaigns: Sequence[SemanticSearchResult],
        *,
        platform: str | None = None,
        objective: str | None = None,
    ) -> RecommendationResponse:
        recommendations: list[str] = []

        for pattern in top_patterns[:3]:
            if pattern.impact_score >= 0:
                recommendations.append(f"Lean into `{pattern.signal_key}` because {pattern.summary}")
            else:
                recommendations.append(f"De-risk `{pattern.signal_key}` because {pattern.summary}")

        for insight in top_insights[:2]:
            recommendations.append(insight.content)

        if similar_campaigns:
            match = similar_campaigns[0]
            recommendations.append(
                f"Reference campaign `{match.campaign_id}` as the closest historical analogue when planning the next test."
            )

        if platform:
            recommendations.append(f"Bias media planning toward {platform} only when it aligns with the strongest stored signals.")
        if objective:
            recommendations.append(f"Keep the optimization target centered on {objective} and prune creatives that do not support it.")

        top_signals = [
            signal for signal, _ in sorted(signal_weights.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        deduped: list[str] = []
        seen: set[str] = set()
        for recommendation in recommendations:
            if recommendation not in seen:
                deduped.append(recommendation)
                seen.add(recommendation)

        return RecommendationResponse(
            generated_at=datetime.now(timezone.utc),
            recommendations=deduped[:6],
            top_signals=top_signals,
            similar_campaigns=list(similar_campaigns[:3]),
        )

    def _generate_with_openai(
        self,
        *,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput | None:
        if self._client is None or not hasattr(self._client.responses, "parse"):
            return None

        prompt = (
            "You are a growth retrospective lead. Analyze the raw comparison data and detected patterns, "
            "then return concise JSON with why performance changed, what to repeat, and what to stop.\n\n"
            f"Comparison report:\n{comparison_data.model_dump_json(indent=2)}\n\n"
            f"Pattern report:\n{pattern_report.model_dump_json(indent=2)}\n\n"
            f"Similar campaigns:\n{[item.model_dump(mode='json') for item in similar_campaigns]}"
        )

        try:
            response = self._client.responses.parse(
                model=self.settings.insights_model,
                store=False,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Return a structured retrospective. Focus on causal hypotheses, reusable learnings, "
                            "recommendations, and anomalies. Keep recommendations executable."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                text_format=InsightExtractionOutput,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                return None
            parsed.source = "openai"
            return parsed
        except Exception:
            return None

    def _fallback_generate(
        self,
        *,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput:
        deltas = comparison_data.deltas
        key_learnings: list[str] = []
        recommendations: list[str] = []
        anomalies: list[str] = []

        if deltas.ctr_diff.pct_diff is not None and deltas.ctr_diff.pct_diff > 0:
            key_learnings.append(
                f"CTR beat forecast by {deltas.ctr_diff.pct_diff:.1f}%, indicating stronger message-market fit than planned."
            )
        if deltas.cvr_diff.pct_diff is not None and deltas.cvr_diff.pct_diff > 0:
            key_learnings.append(
                f"CVR improved by {deltas.cvr_diff.pct_diff:.1f}%, suggesting the landing journey and offer matched traffic quality."
            )
        if deltas.cpa_diff.pct_diff is not None and not deltas.cpa_diff.favorable:
            anomalies.append(
                f"CPA worsened by {abs(deltas.cpa_diff.pct_diff):.1f}%, which indicates spend efficiency drift."
            )
        if deltas.roas_diff.pct_diff is None:
            anomalies.append("ROAS could not be evaluated because revenue was missing from the payload.")

        for finding in pattern_report.winning_audiences[:2]:
            key_learnings.append(finding.description)
            recommendations.append(f"Expand tests around `{finding.signal_key}` and preserve the audience framing.")
        for finding in pattern_report.high_performing_creatives[:2]:
            key_learnings.append(finding.description)
            recommendations.append(f"Increase creative production for `{finding.signal_key}` variants.")
        for finding in pattern_report.budget_inefficiencies[:2]:
            anomalies.append(finding.description)
            recommendations.append("Tighten budget guardrails and require evidence before scaling this pattern.")

        if similar_campaigns:
            recommendations.append(
                f"Reuse the playbook from `{similar_campaigns[0].campaign_id}` because it is the nearest semantic match in memory."
            )

        if not key_learnings:
            key_learnings.append("Campaign history is still sparse, so the system is relying on first-order metric comparisons.")
        if not recommendations:
            recommendations.append("Run a controlled follow-up test with one audience variable and one creative variable changed.")

        key_learnings = self._dedupe(key_learnings)
        recommendations = self._dedupe(recommendations)
        anomalies = self._dedupe(anomalies)

        narrative = " ".join(
            [
                "The engine compared expected and actual outcomes, then mapped the biggest deltas to recurring audience, creative, and platform signals.",
                "Positive metric movement is treated as a repeatable pattern candidate, while cost inflation or missing revenue is flagged for follow-up.",
            ]
        )

        return InsightExtractionOutput(
            narrative_summary=narrative,
            key_learnings=key_learnings[:6],
            recommendations=recommendations[:6],
            anomalies=anomalies[:6],
            source="deterministic",
        )

    def _dedupe(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped

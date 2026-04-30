from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import ComparisonReport, InsightExtractionOutput, PatternReport, ReflectionEvaluation


@dataclass
class ReflectionWrapper:
    def evaluate(
        self,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        recommendations: list[str] | None = None,
    ) -> ReflectionEvaluation:
        score = 0.0
        reasons: list[str] = []

        if comparison.summary:
            score += 0.2
            reasons.append("comparison summary available")

        if pattern_report.pattern_report or pattern_report.auto_tags:
            score += 0.15
            reasons.append("pattern evidence available")

        if insights.key_learnings:
            score += 0.15
            reasons.append("key learnings generated")

        if insights.recommendations:
            score += 0.2
            reasons.append("recommendations generated")

        if recommendations:
            score += 0.1
            reasons.append("validated recommendation payload available")

        if insights.anomalies:
            score += 0.1
            reasons.append("anomalies detected")

        if comparison.performance_score != 0:
            score += 0.2
            reasons.append("performance score available")

        clamped_score = max(0.0, min(round(score, 4), 1.0))
        if not reasons:
            reasons.append("limited runtime data available")

        return ReflectionEvaluation(
            evaluation_score=clamped_score,
            reason=", ".join(reasons),
            scoring_version=1,
        )

    def safe_evaluate(
        self,
        comparison: ComparisonReport,
        pattern_report: PatternReport,
        insights: InsightExtractionOutput,
        recommendations: list[str] | None = None,
        *,
        force_fallback: bool = False,
    ) -> ReflectionEvaluation:
        if force_fallback:
            return ReflectionEvaluation(
                evaluation_score=0.5,
                reason="evaluation unavailable",
                scoring_version=1,
            )
        try:
            return self.evaluate(comparison, pattern_report, insights, recommendations=recommendations)
        except Exception:
            return ReflectionEvaluation(
                evaluation_score=0.5,
                reason="evaluation unavailable",
                scoring_version=1,
            )

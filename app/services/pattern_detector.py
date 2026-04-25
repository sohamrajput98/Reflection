from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import numpy as np
import pandas as pd

from app.models.schemas import CampaignPerformanceInput, PatternFinding, PatternReport
from app.services.scoring import ScoringService
from app.utils.metrics import compute_metric_snapshot, finite_or_default
from app.utils.normalization import is_valid_signal_key, normalize_signal_value


class PatternDetectionEngine:
    def __init__(self, scoring_service: ScoringService) -> None:
        self.scoring_service = scoring_service

    def detect_patterns(
        self,
        history_data: list[CampaignPerformanceInput],
        *,
        focus_campaign_id: str,
    ) -> PatternReport:
        campaign_df, audience_df, creative_df = self._build_frames(history_data)

        winning_audiences = self._detect_winning_audiences(campaign_df, audience_df)
        high_performing_creatives = self._detect_creative_patterns(campaign_df, creative_df)
        budget_inefficiencies = self._detect_budget_inefficiencies(campaign_df)
        platform_trends = self._detect_platform_trends(campaign_df)
        clusters = self._detect_clusters(campaign_df)
        auto_tags = self._build_auto_tags(
            campaign_df,
            audience_df,
            creative_df,
            focus_campaign_id,
        )

        pattern_report = [
            finding.description
            for finding in (
                winning_audiences
                + high_performing_creatives
                + budget_inefficiencies
                + platform_trends
                + clusters
            )
            if finding.description and is_valid_signal_key(finding.signal_key)
        ]

        return PatternReport(
            campaign_id=focus_campaign_id,
            generated_at=datetime.now(timezone.utc),
            pattern_report=pattern_report,
            winning_audiences=winning_audiences,
            high_performing_creatives=high_performing_creatives,
            budget_inefficiencies=budget_inefficiencies,
            platform_trends=platform_trends,
            clusters=clusters,
            auto_tags=auto_tags,
        )

    def _build_frames(
        self,
        campaigns: Iterable[CampaignPerformanceInput],
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        campaign_rows: list[dict[str, object]] = []
        audience_rows: list[dict[str, object]] = []
        creative_rows: list[dict[str, object]] = []

        for campaign in campaigns:
            actual = compute_metric_snapshot(campaign.actual_metrics)
            score = self.scoring_service.compute_performance_score(campaign.actual_metrics)
            campaign_row = {
                "campaign_id": campaign.campaign_id,
                "platform": campaign.platform,
                "objective": campaign.objective,
                "timestamp": campaign.timestamp,
                "spend": campaign.actual_metrics.spend,
                "impressions": campaign.actual_metrics.impressions,
                "clicks": campaign.actual_metrics.clicks,
                "conversions": campaign.actual_metrics.conversions,
                "ctr": finite_or_default(actual.ctr),
                "cvr": finite_or_default(actual.cvr),
                "cpa": finite_or_default(actual.cpa, default=campaign.actual_metrics.spend),
                "roas": finite_or_default(actual.roas),
                "score": score,
            }
            campaign_rows.append(campaign_row)

            for audience in campaign.audiences:
                raw_signal = (
                    audience.attributes.get("age_range")
                    or audience.attributes.get("age_band")
                    or audience.name
                )
                signal_name = normalize_signal_value(raw_signal)
                if not signal_name:
                    continue

                audience_rows.append(
                    {
                        **campaign_row,
                        "audience_name": audience.name,
                        "signal_name": signal_name,
                        "segment": audience.attributes.get("segment", "general"),
                        "city_tier": audience.attributes.get("city_tier", "unknown"),
                    }
                )

            for creative in campaign.creatives:
                creative_type = normalize_signal_value(creative.type)
                if not creative_type:
                    continue

                creative_rows.append(
                    {
                        **campaign_row,
                        "creative_id": creative.id,
                        "creative_type": creative_type,
                        "headline": creative.headline,
                    }
                )

        return (
            pd.DataFrame(campaign_rows),
            pd.DataFrame(audience_rows),
            pd.DataFrame(creative_rows),
        )

    def _detect_winning_audiences(
        self,
        campaign_df: pd.DataFrame,
        audience_df: pd.DataFrame,
    ) -> list[PatternFinding]:
        if audience_df.empty:
            return []

        audience_df = audience_df[
            ~audience_df["signal_name"].astype(str).str.strip().str.lower().isin(
                ["string", "unknown", "none", "", "unknown_audience"]
            )
        ]

        baseline_cvr = campaign_df["cvr"].mean()
        baseline_score = campaign_df["score"].mean()
        baseline_cpa = campaign_df["cpa"].mean()
        grouped = (
            audience_df.groupby("signal_name")
            .agg(
                campaigns=("campaign_id", "nunique"),
                avg_ctr=("ctr", "mean"),
                avg_cvr=("cvr", "mean"),
                avg_cpa=("cpa", "mean"),
                avg_score=("score", "mean"),
            )
            .reset_index()
        )
        grouped["cvr_lift"] = grouped["avg_cvr"].apply(lambda value: self._percent_lift(float(value), float(baseline_cvr)))
        grouped["score_lift"] = grouped["avg_score"].apply(lambda value: self._percent_lift(float(value), float(baseline_score)))
        grouped["cpa_gain"] = grouped["avg_cpa"].apply(lambda value: self._improvement_when_lower(float(value), float(baseline_cpa)))
        grouped["composite_rank"] = (
            grouped["score_lift"] * 0.5
            + grouped["cvr_lift"] * 0.3
            + grouped["cpa_gain"] * 0.2
        )
        grouped = grouped.sort_values(["composite_rank", "avg_score"], ascending=False)

        findings: list[PatternFinding] = []
        for _, row in grouped.head(3).iterrows():
            cvr_lift = float(row["cvr_lift"])
            score_lift = float(row["score_lift"])
            cpa_gain = float(row["cpa_gain"])
            signal_name = normalize_signal_value(row["signal_name"])

            if not signal_name:
                continue
            findings.append(
                PatternFinding(
                    finding_id=f"audience:{signal_name}",
                    category="winning_audiences",
                    title=f"{signal_name} audiences outperform baseline",
                    description=(
                        f"{signal_name} audiences drive a {self._format_delta(score_lift, 'stronger', 'weaker')} "
                        f"performance score versus baseline, with {self._format_delta(cvr_lift, 'higher', 'lower')} CVR "
                        f"and {self._format_delta(cpa_gain, 'lower', 'higher')} CPA across {int(row['campaigns'])} campaigns."
                    ),
                    signal_key=f"audience:{signal_name}",
                    impact_score=round(float(row["composite_rank"]), 2),
                    evidence_count=int(row["campaigns"]),
                    metadata={
                        "avg_ctr": round(float(row["avg_ctr"]), 4),
                        "avg_cvr": round(float(row["avg_cvr"]), 4),
                        "avg_cpa": round(float(row["avg_cpa"]), 2),
                        "attribution_mode": "campaign_level_heuristic",
                    },
                )
            )
        return findings

    def _detect_creative_patterns(
        self,
        campaign_df: pd.DataFrame,
        creative_df: pd.DataFrame,
    ) -> list[PatternFinding]:
        if creative_df.empty:
            return []

        creative_df = creative_df[
            ~creative_df["creative_type"].astype(str).str.strip().str.lower().isin(
                ["string", "unknown", "none", ""]
            )
        ]

        baseline_cvr = campaign_df["cvr"].mean()
        baseline_score = campaign_df["score"].mean()
        baseline_cpa = campaign_df["cpa"].mean()
        grouped = (
            creative_df.groupby("creative_type")
            .agg(
                campaigns=("campaign_id", "nunique"),
                avg_ctr=("ctr", "mean"),
                avg_cvr=("cvr", "mean"),
                avg_cpa=("cpa", "mean"),
                avg_score=("score", "mean"),
            )
            .reset_index()
        )
        grouped["cvr_lift"] = grouped["avg_cvr"].apply(lambda value: self._percent_lift(float(value), float(baseline_cvr)))
        grouped["score_lift"] = grouped["avg_score"].apply(lambda value: self._percent_lift(float(value), float(baseline_score)))
        grouped["cpa_gain"] = grouped["avg_cpa"].apply(lambda value: self._improvement_when_lower(float(value), float(baseline_cpa)))
        grouped["composite_rank"] = (
            grouped["score_lift"] * 0.5
            + grouped["cvr_lift"] * 0.3
            + grouped["cpa_gain"] * 0.2
        )
        grouped = grouped.sort_values(["composite_rank", "avg_score"], ascending=False)

        findings: list[PatternFinding] = []
        for _, row in grouped.head(3).iterrows():
            creative_type = normalize_signal_value(row["creative_type"])
            cvr_lift = float(row["cvr_lift"])
            score_lift = float(row["score_lift"])
            cpa_gain = float(row["cpa_gain"])
            if not creative_type:
                continue
            findings.append(
                PatternFinding(
                    finding_id=f"creative:{creative_type}",
                    category="high_performing_creatives",
                    title=f"{creative_type.title()} creatives lead on conversion efficiency",
                    description=(
                        f"{creative_type.title()} creatives deliver a {self._format_delta(score_lift, 'stronger', 'weaker')} "
                        f"performance score, {self._format_delta(cvr_lift, 'higher', 'lower')} CVR, and "
                        f"{self._format_delta(cpa_gain, 'lower', 'higher')} CPA while sustaining {float(row['avg_ctr']):.1%} CTR "
                        f"across {int(row['campaigns'])} campaigns."
                    ),
                    signal_key=f"creative_type:{creative_type}",
                    impact_score=round(float(row["composite_rank"]), 2),
                    evidence_count=int(row["campaigns"]),
                    metadata={
                        "avg_ctr": round(float(row["avg_ctr"]), 4),
                        "avg_cvr": round(float(row["avg_cvr"]), 4),
                        "avg_cpa": round(float(row["avg_cpa"]), 2),
                        "attribution_mode": "campaign_level_heuristic",
                    },
                )
            )
        return findings

    def _detect_budget_inefficiencies(self, campaign_df: pd.DataFrame) -> list[PatternFinding]:
        if campaign_df.empty:
            return []

        cpa_threshold = float(campaign_df["cpa"].quantile(0.75))
        spend_threshold = float(campaign_df["spend"].quantile(0.60))
        inefficient = campaign_df[
            (campaign_df["cpa"] >= cpa_threshold) & (campaign_df["spend"] >= spend_threshold)
        ].sort_values(["cpa", "spend"], ascending=[False, False])

        findings: list[PatternFinding] = []
        for _, row in inefficient.head(3).iterrows():
            findings.append(
                PatternFinding(
                    finding_id=f"budget:{row['campaign_id']}",
                    category="budget_inefficiencies",
                    title=f"{row['campaign_id']} shows budget inefficiency",
                    description=(
                        f"{row['campaign_id']} is overspending relative to history, with CPA at {float(row['cpa']):.2f} "
                        f"on {float(row['spend']):.2f} spend while only converting at {float(row['cvr']):.1%}."
                    ),
                    signal_key=f"campaign:{row['campaign_id']}",
                    impact_score=round(-float(row["cpa"]), 2),
                    evidence_count=1,
                    metadata={
                        "platform": row["platform"],
                        "objective": row["objective"],
                        "spend": round(float(row["spend"]), 2),
                        "cpa": round(float(row["cpa"]), 2),
                    },
                )
            )
        return findings

    def _detect_platform_trends(self, campaign_df: pd.DataFrame) -> list[PatternFinding]:
        if campaign_df.empty:
            return []

        baseline_score = campaign_df["score"].mean()
        grouped = (
            campaign_df.groupby("platform")
            .agg(
                campaigns=("campaign_id", "nunique"),
                avg_ctr=("ctr", "mean"),
                avg_cvr=("cvr", "mean"),
                avg_cpa=("cpa", "mean"),
                avg_score=("score", "mean"),
            )
            .reset_index()
            .sort_values("avg_score", ascending=False)
        )

        findings: list[PatternFinding] = []
        for _, row in grouped.head(3).iterrows():
            score_lift = self._percent_lift(float(row["avg_score"]), float(baseline_score))
            platform = str(row["platform"]).strip()
            platform_key = normalize_signal_value(platform)

            if not platform_key:
                continue
            findings.append(
                PatternFinding(
                    finding_id=f"platform:{platform_key}",
                    category="platform_trends",
                    title=f"{platform} trend snapshot",
                    description=(
                        f"{platform} campaigns average {float(row['avg_ctr']):.1%} CTR and {float(row['avg_cvr']):.1%} CVR, "
                        f"driving a {self._format_delta(score_lift, 'stronger', 'weaker')} score than the portfolio average."
                    ),
                    signal_key=f"platform:{platform_key}",
                    impact_score=round(score_lift, 2),
                    evidence_count=int(row["campaigns"]),
                    metadata={
                        "avg_ctr": round(float(row["avg_ctr"]), 4),
                        "avg_cvr": round(float(row["avg_cvr"]), 4),
                        "avg_cpa": round(float(row["avg_cpa"]), 2),
                    },
                )
            )

        for platform, group in campaign_df.sort_values("timestamp").groupby("platform"):
            platform = str(platform).strip()
            platform_key = normalize_signal_value(platform)

            if not platform_key:
                continue
            if len(group) < 3:
                continue
            trend = np.polyfit(np.arange(len(group)), group["ctr"], 1)[0]
            findings.append(
                PatternFinding(
                    finding_id=f"platform_trend:{platform_key}",
                    category="platform_trends",
                    title=f"{platform} CTR trend",
                    description=(
                        f"{platform} CTR is trending {'up' if trend >= 0 else 'down'} by {abs(trend):.2%} "
                        f"per campaign over the last {len(group)} runs."
                    ),
                    signal_key=f"platform_trend:{platform_key}",
                    impact_score=round(float(trend) * 100, 2),
                    evidence_count=len(group),
                    metadata={"metric": "ctr_slope"},
                )
            )
        return findings[:5]

    def _detect_clusters(self, campaign_df: pd.DataFrame) -> list[PatternFinding]:
        if campaign_df.empty:
            return []

        score_q75 = float(campaign_df["score"].quantile(0.75))
        score_q25 = float(campaign_df["score"].quantile(0.25))
        cvr_median = float(campaign_df["cvr"].median())
        cpa_median = float(campaign_df["cpa"].median())

        labeled = campaign_df.copy()
        labeled["cluster_label"] = np.select(
            [
                labeled["score"] >= score_q75,
                (labeled["cvr"] >= cvr_median) & (labeled["cpa"] <= cpa_median),
                labeled["score"] <= score_q25,
            ],
            ["scale_winners", "efficient_converters", "at_risk"],
            default="mixed",
        )

        findings: list[PatternFinding] = []
        grouped = (
            labeled.groupby("cluster_label")
            .agg(
                campaigns=("campaign_id", "nunique"),
                avg_score=("score", "mean"),
                avg_cvr=("cvr", "mean"),
                avg_cpa=("cpa", "mean"),
            )
            .reset_index()
            .sort_values("avg_score", ascending=False)
        )
        for _, row in grouped.iterrows():
            label = str(row["cluster_label"]).strip()
            if label.lower() in ("string", "unknown", "none", ""):
                continue
            if float(row["avg_cvr"]) == 0:
                continue
            if float(row["avg_cpa"]) == 0:
                continue
            findings.append(
                PatternFinding(
                    finding_id=f"cluster:{label}",
                    category="clusters",
                    title=f"{label.replace('_', ' ').title()} cluster",
                    description=(
                        f"The {label.replace('_', ' ')} cluster contains {int(row['campaigns'])} campaigns with "
                        f"{float(row['avg_cvr']):.1%} average CVR and {float(row['avg_cpa']):.2f} CPA."
                    ),
                    signal_key=f"cluster:{label}",
                    impact_score=round(float(row["avg_score"]), 2),
                    evidence_count=int(row["campaigns"]),
                    metadata={"cluster_method": "heuristic_quantile_segmentation"},
                )
            )
        return findings[:3]

    def _build_auto_tags(
        self,
        campaign_df: pd.DataFrame,
        audience_df: pd.DataFrame,
        creative_df: pd.DataFrame,
        focus_campaign_id: str,
    ) -> list[str]:
        focus_rows = campaign_df[campaign_df["campaign_id"] == focus_campaign_id]
        if focus_rows.empty:
            return []

        row = focus_rows.iloc[0]
        score_q75 = float(campaign_df["score"].quantile(0.75))
        score_q25 = float(campaign_df["score"].quantile(0.25))
        if float(row["score"]) >= score_q75:
            band = "high_performer"
        elif float(row["score"]) <= score_q25:
            band = "at_risk"
        else:
            band = "mid_band"

        tags = []

        platform = normalize_signal_value(row["platform"])
        if platform:
            tags.append(f"platform:{platform}")

        objective = normalize_signal_value(row["objective"])
        if objective:
            tags.append(f"objective:{objective}")

        tags.append(f"performance_band:{band}")

        if not audience_df.empty:
            audience_rows = audience_df[audience_df["campaign_id"] == focus_campaign_id]
            for signal_name in audience_rows["signal_name"].dropna().unique().tolist():
                cleaned = normalize_signal_value(signal_name)
                if cleaned:
                    tags.append(f"audience:{cleaned}")

        if not creative_df.empty:
            creative_rows = creative_df[creative_df["campaign_id"] == focus_campaign_id]
            for creative_type in creative_rows["creative_type"].dropna().unique().tolist():
                cleaned = normalize_signal_value(creative_type)
                if cleaned:
                    tags.append(f"creative_type:{cleaned}")

        return sorted(set(tags))

    def _percent_lift(self, value: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return ((value - baseline) / baseline) * 100.0

    def _improvement_when_lower(self, value: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return ((baseline - value) / baseline) * 100.0

    def _format_delta(self, value: float, positive_word: str, negative_word: str) -> str:
        direction = positive_word if value >= 0 else negative_word
        return f"{abs(value):.0f}% {direction}"

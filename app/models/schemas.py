from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from uuid import UUID

class Metrics(BaseModel):
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    conversions: int = Field(ge=0)
    spend: float = Field(ge=0.0)
    revenue: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_funnel(self) -> "Metrics":
        if self.clicks > self.impressions:
            raise ValueError("clicks cannot exceed impressions")
        if self.conversions > self.clicks:
            raise ValueError("conversions cannot exceed clicks")
        return self


class Audience(BaseModel):
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class Creative(BaseModel):
    id: str
    type: str
    headline: str
    primary_text: str


class CampaignPerformanceInput(BaseModel):
    campaign_id: str
    platform: str
    objective: str
    expected_metrics: Metrics
    actual_metrics: Metrics
    audiences: list[Audience] = Field(default_factory=list)
    creatives: list[Creative] = Field(default_factory=list)
    timestamp: datetime


class MetricSnapshot(BaseModel):
    ctr: float | None = None
    cvr: float | None = None
    cpa: float | None = None
    roas: float | None = None


class MetricDelta(BaseModel):
    expected: float | None = None
    actual: float | None = None
    pct_diff: float | None = None
    favorable: bool | None = None


class ComparisonDeltas(BaseModel):
    ctr_diff: MetricDelta
    cvr_diff: MetricDelta
    cpa_diff: MetricDelta
    roas_diff: MetricDelta


class ComparisonReport(BaseModel):
    campaign_id: str
    generated_at: datetime
    expected_rates: MetricSnapshot
    actual_rates: MetricSnapshot
    deltas: ComparisonDeltas
    performance_score: float
    summary: list[str] = Field(default_factory=list)


class PatternFinding(BaseModel):
    finding_id: str
    category: str
    title: str
    description: str
    signal_key: str
    impact_score: float
    evidence_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatternReport(BaseModel):
    campaign_id: str
    generated_at: datetime
    pattern_report: list[str] = Field(default_factory=list)
    winning_audiences: list[PatternFinding] = Field(default_factory=list)
    high_performing_creatives: list[PatternFinding] = Field(default_factory=list)
    budget_inefficiencies: list[PatternFinding] = Field(default_factory=list)
    platform_trends: list[PatternFinding] = Field(default_factory=list)
    clusters: list[PatternFinding] = Field(default_factory=list)
    auto_tags: list[str] = Field(default_factory=list)


class InsightExtractionOutput(BaseModel):
    narrative_summary: str
    key_learnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    source: str = "deterministic"


class SemanticSearchResult(BaseModel):
    document_id: str
    campaign_id: str | None = None
    score: float
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackSignal(BaseModel):
    signal_key: str
    weight: float
    successes: int
    failures: int
    last_updated: datetime


class WeightSnapshot(BaseModel):
    generated_at: datetime
    scoring_weights: dict[str, float]
    signal_weights: dict[str, float]
    updated_signals: list[FeedbackSignal] = Field(default_factory=list)


class StorageConfirmation(BaseModel):
    sqlite_saved: bool
    vector_saved: bool
    output_path: str


class AnalyzeCampaignResponse(BaseModel):
    comparison_report: ComparisonReport
    pattern_report: PatternReport
    insights: InsightExtractionOutput
    weights: WeightSnapshot
    similar_campaigns: list[SemanticSearchResult] = Field(default_factory=list)
    stored_memory: StorageConfirmation


class InsightRecord(BaseModel):
    id: UUID
    campaign_id: str
    kind: str
    content: str
    priority: float
    created_at: datetime


class PatternRecord(BaseModel):
    id: int
    campaign_id: str
    category: str
    signal_key: str
    summary: str
    impact_score: float
    created_at: datetime


class RecommendationResponse(BaseModel):
    generated_at: datetime
    recommendations: list[str] = Field(default_factory=list)
    top_signals: list[str] = Field(default_factory=list)
    similar_campaigns: list[SemanticSearchResult] = Field(default_factory=list)

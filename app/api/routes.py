from __future__ import annotations
from unittest import result

from fastapi import APIRouter, Depends, Query

from app.core.bootstrap import get_engine
from app.models.schemas import (
    AnalyzeCampaignResponse,
    CampaignPerformanceInput,
    InsightRecord,
    PatternRecord,
    RecommendationResponse,
)
from app.services.analyzer import ReflectionLearningEngine

router = APIRouter()

def clean_text(obj):
    if isinstance(obj, dict):
        return {k: clean_text(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_text(i) for i in obj if i and i != "string"]
    elif isinstance(obj, str):
        return "" if obj.lower() == "string" else obj
    return obj

@router.post("/analyze-campaign", response_model=AnalyzeCampaignResponse)
def analyze_campaign(
    payload: CampaignPerformanceInput,
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> AnalyzeCampaignResponse:
    result = engine.analyze_campaign(payload)
    return clean_text(result)


@router.get("/insights", response_model=list[InsightRecord])
def get_insights(
    limit: int = Query(default=10, ge=1, le=100),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> list[InsightRecord]:
    return engine.get_top_insights(limit=limit)


@router.get("/patterns", response_model=list[PatternRecord])
def get_patterns(
    limit: int = Query(default=20, ge=1, le=100),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> list[PatternRecord]:
    return engine.get_patterns(limit=limit)


@router.get("/recommendations", response_model=RecommendationResponse)
def get_recommendations(
    platform: str | None = Query(default=None),
    objective: str | None = Query(default=None),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> RecommendationResponse:
    result = engine.get_recommendations(platform=platform, objective=objective)
    return clean_text(result)


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

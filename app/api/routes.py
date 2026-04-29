from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status

from app.core.bootstrap import get_engine, get_settings
from app.models.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AnalyzeCampaignResponse,
    CampaignPerformanceInput,
    FeedbackActionResponse,
    InsightRecord,
    PatternRecord,
    RecommendationResponse,
    RecommendationFeedbackRequest,
    RecommendationShownRequest,
)
from app.services.analyzer import ReflectionLearningEngine

router = APIRouter()


def clean_text(obj):
    if isinstance(obj, dict):
        return {k: clean_text(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_text(i) for i in obj if i and i != "string"]
    if isinstance(obj, str):
        return "" if obj.lower() == "string" else obj
    return obj


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_auth_key:
        return
    if x_api_key == settings.api_auth_key:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post(
    "/analyze-campaign",
    response_model=AnalyzeCampaignResponse,
    dependencies=[Depends(require_api_key)],
)
def analyze_campaign(
    payload: CampaignPerformanceInput,
    background_tasks: BackgroundTasks,
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> AnalyzeCampaignResponse:
    result = engine.analyze_campaign(
        payload,
        background_tasks=background_tasks,
        request_id=str(uuid4()),
    )
    return clean_text(result)


@router.post(
    "/agent-chat",
    response_model=AgentChatResponse,
    dependencies=[Depends(require_api_key)],
)
def agent_chat(
    payload: AgentChatRequest,
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> AgentChatResponse:
    return engine.chat_with_agent(message=payload.message, context=payload.context)


@router.get(
    "/insights",
    response_model=list[InsightRecord],
    dependencies=[Depends(require_api_key)],
)
def get_insights(
    limit: int = Query(default=10, ge=1, le=100),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> list[InsightRecord]:
    return engine.get_top_insights(limit=limit)


@router.get(
    "/patterns",
    response_model=list[PatternRecord],
    dependencies=[Depends(require_api_key)],
)
def get_patterns(
    limit: int = Query(default=20, ge=1, le=100),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> list[PatternRecord]:
    return engine.get_patterns(limit=limit)


@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    dependencies=[Depends(require_api_key)],
)
def get_recommendations(
    platform: str | None = Query(default=None),
    objective: str | None = Query(default=None),
    include_similar_campaigns: bool = Query(default=True),
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> RecommendationResponse:
    result = engine.get_recommendations(
        platform=platform,
        objective=objective,
        include_similar_campaigns=include_similar_campaigns,
    )
    return clean_text(result)


@router.post(
    "/shown",
    response_model=FeedbackActionResponse,
    dependencies=[Depends(require_api_key)],
)
def mark_recommendation_shown(
    payload: RecommendationShownRequest,
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> FeedbackActionResponse:
    return engine.mark_recommendation_shown(payload, request_id=str(uuid4()))


@router.post(
    "/feedback",
    response_model=FeedbackActionResponse,
    dependencies=[Depends(require_api_key)],
)
def submit_recommendation_feedback(
    payload: RecommendationFeedbackRequest,
    engine: ReflectionLearningEngine = Depends(get_engine),
) -> FeedbackActionResponse:
    try:
        return engine.submit_recommendation_feedback(payload, request_id=str(uuid4()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

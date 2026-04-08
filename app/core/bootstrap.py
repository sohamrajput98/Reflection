from __future__ import annotations

from functools import lru_cache

from supabase import create_client, Client

from app.core.config import Settings
from app.services.analyzer import ReflectionLearningEngine
from app.services.comparator import PerformanceComparator
from app.services.feedback import FeedbackLoopEngine
from app.services.insight_service import InsightService
from app.services.pattern_detector import PatternDetectionEngine
from app.services.scoring import ScoringService
from app.storage.vector_store import SemanticMemoryStore
from app.storage.supabase_repository import SupabaseRepository


@lru_cache
def get_settings() -> Settings:
    settings = Settings.load()
    settings.ensure_directories()
    return settings


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache
def get_engine() -> ReflectionLearningEngine:
    settings = get_settings()
    supabase = get_supabase_client()

    repository = SupabaseRepository(settings, supabase)
    scoring_service = ScoringService(settings)
    vector_store = SemanticMemoryStore(settings)
    comparator = PerformanceComparator(scoring_service)
    pattern_detector = PatternDetectionEngine(scoring_service)
    insight_service = InsightService(settings)
    feedback_engine = FeedbackLoopEngine(settings, repository)

    return ReflectionLearningEngine(
        settings=settings,
        repository=repository,
        vector_store=vector_store,
        comparator=comparator,
        pattern_detector=pattern_detector,
        insight_service=insight_service,
        feedback_engine=feedback_engine,
        scoring_service=scoring_service,
        supabase=supabase,
    )
from __future__ import annotations

from functools import lru_cache

from supabase import create_client, Client

from app.agents.analysis_agent import AnalysisAgent
from app.agents.insight_agent import InsightAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.pattern_agent import PatternAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.core.config import Settings
from app.orchestration.reflection_wrapper import ReflectionWrapper
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
    reflection_wrapper = ReflectionWrapper()

    analysis_agent = AnalysisAgent(comparator=comparator)
    pattern_agent = PatternAgent(repository=repository, pattern_detector=pattern_detector)
    insight_agent = InsightAgent(
        settings=settings,
        vector_store=vector_store,
        insight_service=insight_service,
        supabase=supabase,
    )
    memory_agent = MemoryAgent(
        settings=settings,
        repository=repository,
        vector_store=vector_store,
        supabase=supabase,
    )
    supervisor_agent = SupervisorAgent(
        settings=settings,
        analysis_agent=analysis_agent,
        pattern_agent=pattern_agent,
        insight_agent=insight_agent,
        memory_agent=memory_agent,
        feedback_engine=feedback_engine,
        reflection_wrapper=reflection_wrapper,
    )

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
        supervisor_agent=supervisor_agent,
    )

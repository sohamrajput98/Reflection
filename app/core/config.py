from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str
    base_dir: Path
    database_path: Path
    output_dir: Path
    vector_backend: str
    vector_path: Path
    vector_fallback_path: Path
    weights_path: Path
    insights_model: str
    embedding_model: str
    openai_api_key: str | None
    insights_limit: int
    agent_id: str
    supabase_url: str
    base_url: str | None
    supabase_key: str
    enable_local_output: bool
    cors_origins: tuple[str, ...]
    api_auth_key: str | None

    @classmethod
    def load(cls) -> "Settings":
        base_dir = Path(__file__).resolve().parents[2]
        database_path = base_dir / os.getenv("MARKO_DATABASE_PATH", "data/reflection.db")
        output_dir = base_dir / os.getenv("MARKO_OUTPUT_DIR", "output")
        vector_path = base_dir / os.getenv("MARKO_VECTOR_PATH", "data/chroma")
        vector_fallback_path = base_dir / os.getenv(
            "MARKO_VECTOR_FALLBACK_PATH",
            "data/vector_store.json",
        )
        weights_path = base_dir / os.getenv("MARKO_WEIGHTS_PATH", "data/weights.json")

        agent_id = os.getenv("agent_id", "default_agent")
        cors_origins = _split_csv(os.getenv("FRONTEND_ORIGINS")) or (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        )

        return cls(
            app_name="Reflection & Learning Engine",
            base_dir=base_dir,
            database_path=database_path,
            output_dir=output_dir,
            vector_backend=os.getenv("MARKO_VECTOR_BACKEND", "chroma").lower(),
            vector_path=vector_path,
            vector_fallback_path=vector_fallback_path,
            weights_path=weights_path,
            insights_model=os.getenv("MARKO_INSIGHTS_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"),
            embedding_model=os.getenv(
                "MARKO_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            insights_limit=int(os.getenv("MARKO_INSIGHTS_LIMIT", "10")),
            agent_id=agent_id,
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
            enable_local_output=os.getenv("ENABLE_LOCAL_OUTPUT", "false").lower() == "true",
            cors_origins=cors_origins,
            api_auth_key=os.getenv("API_AUTH_KEY"),
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vector_path.mkdir(parents=True, exist_ok=True)
        self.vector_fallback_path.parent.mkdir(parents=True, exist_ok=True)
        if self.enable_local_output:
            self.weights_path.parent.mkdir(parents=True, exist_ok=True)

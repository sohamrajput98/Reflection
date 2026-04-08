from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MARKO_DATABASE_PATH", "data/sample_reflection.db")
os.environ.setdefault("MARKO_WEIGHTS_PATH", "data/sample_weights.json")
os.environ.setdefault("MARKO_VECTOR_FALLBACK_PATH", "data/sample_vector_store.json")
os.environ.setdefault("MARKO_VECTOR_PATH", "data/chroma_sample")

from app.core.bootstrap import get_engine  # noqa: E402
from app.models.schemas import CampaignPerformanceInput  # noqa: E402


def load_payload(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def reset_sample_state() -> None:
    targets = [
        ROOT / os.environ["MARKO_DATABASE_PATH"],
        ROOT / os.environ["MARKO_WEIGHTS_PATH"],
        ROOT / os.environ["MARKO_VECTOR_FALLBACK_PATH"],
        ROOT / os.environ["MARKO_VECTOR_PATH"],
    ]
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


def main() -> None:
    reset_sample_state()
    engine = get_engine()
    history_path = ROOT / "data" / "samples" / "campaign_history.json"
    incoming_path = ROOT / "data" / "samples" / "incoming_campaign.json"

    for raw_campaign in load_payload(history_path):
        engine.analyze_campaign(CampaignPerformanceInput.model_validate(raw_campaign))

    response = engine.analyze_campaign(CampaignPerformanceInput.model_validate(load_payload(incoming_path)))
    print(json.dumps(response.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()

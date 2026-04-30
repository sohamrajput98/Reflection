from __future__ import annotations

import logging
from typing import Any

from app.models.schemas import InsightExtractionOutput


logger = logging.getLogger(__name__)


def validate_recommendation_output(
    recommendations: list[Any],
    *,
    agent_name: str,
    request_id: str | None,
) -> list[str]:
    valid: list[str] = []

    for rec in recommendations:
        try:
            validated = InsightExtractionOutput(
                narrative_summary="",
                recommendations=[rec],
            ).recommendations[0].strip()
            if not validated or validated.lower() in {"string", "unknown", "none"}:
                raise ValueError("invalid recommendation text")
            valid.append(validated)
        except Exception as exc:
            logger.warning(
                "recommendation_schema_invalid request_id=%s agent=%s error=%s",
                request_id,
                agent_name,
                exc,
            )

    return valid

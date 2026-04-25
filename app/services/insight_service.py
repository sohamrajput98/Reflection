from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Sequence

from app.core.config import Settings
from app.models.schemas import (
    ComparisonReport,
    InsightExtractionOutput,
    InsightRecord,
    PatternRecord,
    PatternReport,
    RecommendationResponse,
    SemanticSearchResult,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None


logger = logging.getLogger(__name__)

FREE_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen3-coder-480b-a35b:free",
    "stepfun/step-3.5-flash:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "minimax/minimax-m2.5:free",
    "arcee-ai/trinity-large-preview:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "google/gemma-3-27b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "openrouter/free",
]

DEPRECATED_FREE_MODELS = {
    "qwen/qwen3.6-plus:free",
}


class InsightService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None
        if settings.openai_api_key and OpenAI is not None:
            self._client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.base_url,
            )

    def generate_insights(
        self,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput:
        if self._client is not None:
            generated = self._generate_with_openai(
                pattern_report=pattern_report,
                comparison_data=comparison_data,
                similar_campaigns=similar_campaigns,
            )
            if generated is not None:
                return generated

        return self._fallback_generate(
            pattern_report=pattern_report,
            comparison_data=comparison_data,
            similar_campaigns=similar_campaigns,
        )

    def generate_chat_reply(
        self,
        *,
        message: str,
        context: dict | None = None,
    ) -> tuple[str, str]:
        context_block = self._build_chat_context_block(context or {})
        if self._client is not None:
            for model in self._candidate_models():
                try:
                    response = self._chat_completion_with_retry(
                        model=model,
                        system_prompt=(
                            "You are Marko AI, a Campaign Intelligence / Reflection Agent. "
                            "Help with campaign analysis, performance shifts, patterns, insights, "
                            "memory, and practical next actions. Stay concise and specific."
                        ),
                        user_prompt=message,
                        extra_system_prompt=f"Campaign context:\n{context_block}",
                    )
                    reply = self._extract_text_response(response)
                    if reply:
                        return reply, model
                except Exception:
                    logger.warning("Chat completion failed for free model %s; trying next fallback.", model)

        return self._fallback_chat_reply(message, context or {}), "local-fallback"

    def _candidate_models(self) -> list[str]:
        preferred = (self.settings.insights_model or "").strip()
        candidates: list[str] = []

        if preferred in DEPRECATED_FREE_MODELS:
            logger.warning("Configured model %s is deprecated; moving it to the end of the free fallback chain.", preferred)
        elif preferred.endswith(":free") or preferred == "openrouter/free":
            candidates.append(preferred)
        elif preferred:
            logger.warning("Ignoring non-free configured LLM model %s; free-only mode is enforced.", preferred)

        for model in FREE_OPENROUTER_MODELS:
            if model not in candidates:
                candidates.append(model)

        for model in DEPRECATED_FREE_MODELS:
            if model not in candidates:
                candidates.append(model)

        return candidates

    def _clean(self, val: str | None) -> str | None:
        if not val:
            return None
        v = str(val).strip().lower()
        if v in ("string", "unknown", "none", ""):
            return None
        return v

    def _build_chat_context_block(self, context: dict) -> str:
        parts: list[str] = []
        if context.get("agentTitle"):
            parts.append(f"Active agent: {context['agentTitle']}")
        if context.get("narrative"):
            parts.append(f"Narrative summary: {context['narrative']}")
        if context.get("keyLearnings"):
            parts.append(f"Key learnings: {' | '.join(context['keyLearnings'])}")
        if context.get("recommendations"):
            parts.append(f"Recommendations: {' | '.join(context['recommendations'])}")
        if context.get("patterns"):
            parts.append(f"Patterns: {' | '.join(context['patterns'])}")
        if context.get("comparison"):
            parts.append(f"Performance deltas: {' | '.join(context['comparison'])}")
        if context.get("memory"):
            parts.append(f"Memory: {' | '.join(context['memory'])}")
        return "\n".join(parts) or "No campaign context available."

    def _fallback_chat_reply(self, message: str, context: dict) -> str:
        prompt = message.lower()
        recommendations = context.get("recommendations") or []
        patterns = context.get("patterns") or []
        memory = context.get("memory") or []
        narrative = context.get("narrative") or ""

        if "biggest" in prompt or "issue" in prompt or "problem" in prompt:
            return (
                f"Biggest issue in focus: {recommendations[0]}"
                if recommendations
                else "I need an analyzed campaign to isolate the biggest issue clearly."
            )
        if "pattern" in prompt:
            return (
                f"Top pattern signals: {', '.join(patterns[:3])}."
                if patterns
                else "No strong pattern signals are available yet."
            )
        if "recommend" in prompt or "optimize" in prompt:
            return (
                f"Recommended next move: {recommendations[0]}"
                if recommendations
                else "No recommendation is available yet. Run an analysis first."
            )
        if "memory" in prompt or "similar" in prompt:
            return (
                f"Closest recalled campaigns: {', '.join(memory[:2])}."
                if memory
                else "No similar campaign memory is available yet."
            )
        return narrative or "Share a campaign result or ask about analysis, patterns, insights, memory, or next actions."

    def generate_recommendations(
        self,
        top_insights: Sequence[InsightRecord],
        top_patterns: Sequence[PatternRecord],
        signal_weights: dict[str, float],
        similar_campaigns: Sequence[SemanticSearchResult],
        *,
        platform: str | None = None,
        objective: str | None = None,
    ) -> RecommendationResponse:
        recommendations: list[str] = []

        for pattern in top_patterns[:3]:
            content = pattern.summary.strip().lower()

            if not any(x in content for x in ["increase", "scale", "test", "reduce", "improve", "optimize", "boost", "drive", "gain", "drop"]):
                continue
            signal = self._clean(pattern.signal_key)
            summary = (pattern.summary or "").strip()
            if not signal or not summary:
                continue
            signal = signal.replace("_", " ").replace(":", " → ")

            if pattern.impact_score >= 0:
                parts = signal.split(":", 1)

                if len(parts) == 2:
                    pretty_signal = f"{parts[0]} - {parts[1].replace('_', ' ')}"
                else:
                    pretty_signal = signal
                recommendations.append(f"Lean into {pretty_signal} because {summary}")
            else:
                recommendations.append(f"De-risk `{signal}` because {summary}")

        for insight in top_insights[:2]:
            content = (insight.content or "").strip()

            if not content:
                continue

            if not any(x in content for x in ["increase", "scale", "test", "reduce", "improve", "optimize", "boost", "drive", "gain", "drop"]):
                continue

            recommendations.append(content)

        if similar_campaigns:
            match = similar_campaigns[0]
            recommendations.append(
                f"Reference campaign `{match.campaign_id}` as the closest historical analogue when planning the next test."
            )

        platform_clean = self._clean(platform)
        objective_clean = self._clean(objective)

        if platform_clean:
            recommendations.append(
                f"Bias media planning toward {platform_clean} only when it aligns with the strongest stored signals."
            )

        if objective_clean:
            recommendations.append(
                f"Keep the optimization target centered on {objective_clean} and prune creatives that do not support it."
            )

        top_signals = [
            signal for signal, _ in sorted(signal_weights.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        deduped: list[str] = []
        seen: set[str] = set()

        for recommendation in recommendations:
            cleaned = recommendation.strip()
            key = cleaned.lower()

            if "duplicate" in key or not cleaned or key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)

        return RecommendationResponse(
            generated_at=datetime.now(timezone.utc),
            recommendations=deduped[:6],
            top_signals=top_signals,
            similar_campaigns=list(similar_campaigns[:3]),
        )

    def _sanitize_payload(self, data):
        if isinstance(data, dict):
            return {
                k: self._sanitize_payload(v)
                for k, v in data.items()
                if self._sanitize_payload(v) is not None
            }
        if isinstance(data, list):
            return [
                self._sanitize_payload(v)
                for v in data
                if self._sanitize_payload(v) is not None
            ]
        if isinstance(data, str):
            cleaned = data.strip()
            if cleaned.lower() in ("string", "unknown", "none", ""):
                return None
            return cleaned
        return data

    def _chat_completion_with_retry(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        extra_system_prompt: str | None = None,
    ):
        last_error: Exception | None = None
        messages = [{"role": "system", "content": system_prompt}]
        if extra_system_prompt:
            messages.append({"role": "system", "content": extra_system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        for attempt in range(2):
            try:
                return self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                )
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                logger.warning(
                    "LLM request failed on attempt %s for model %s: %s",
                    attempt + 1,
                    model,
                    exc,
                )
                if "404" in message or "deprecated" in message or "not found" in message:
                    break
                if attempt == 0:
                    time.sleep(0.75)

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM request failed without an exception")

    def _extract_text_response(self, response) -> str | None:
        if response is None or not getattr(response, "choices", None):
            return None
        message = response.choices[0].message
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        return None

    def _extract_json_blob(self, text: str) -> dict | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None

    def _generate_with_openai(
        self,
        *,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput | None:
        if self._client is None:
            return None

        comparison_clean = self._sanitize_payload(comparison_data.model_dump())
        pattern_clean = self._sanitize_payload(pattern_report.model_dump())
        similar_clean = [self._sanitize_payload(item.model_dump(mode="json")) for item in similar_campaigns]

        prompt = (
            "You are a growth retrospective lead. Analyze the raw comparison data and detected patterns. "
            "Return strict JSON with keys: narrative_summary (string), key_learnings (string[]), "
            "recommendations (string[]), anomalies (string[]), source (string).\n\n"
            f"Comparison report:\n{comparison_clean}\n\n"
            f"Pattern report:\n{pattern_clean}\n\n"
            f"Similar campaigns:\n{similar_clean}"
        )

        try:
            for model in self._candidate_models():
                try:
                    response = self._chat_completion_with_retry(
                        model=model,
                        system_prompt=(
                            "Return only valid JSON. Focus on causal hypotheses, reusable learnings, "
                            "recommendations, and anomalies. Keep recommendations executable."
                        ),
                        user_prompt=prompt,
                    )
                    response_text = self._extract_text_response(response)
                    if not response_text:
                        continue

                    parsed = self._extract_json_blob(response_text)
                    if parsed is None:
                        logger.warning("LLM insight response was not valid JSON for free model %s.", model)
                        continue

                    output = InsightExtractionOutput.model_validate(parsed)
                    output.source = "openai"
                    return output
                except Exception:
                    logger.warning("Insight generation failed for free model %s; trying next fallback.", model)
            return None
        except Exception:
            logger.exception("Insight generation failed; falling back to deterministic output.")
            return None

    def _fallback_generate(
        self,
        *,
        pattern_report: PatternReport,
        comparison_data: ComparisonReport,
        similar_campaigns: Sequence[SemanticSearchResult],
    ) -> InsightExtractionOutput:
        deltas = comparison_data.deltas
        key_learnings: list[str] = []
        recommendations: list[str] = []
        anomalies: list[str] = []

        if deltas.ctr_diff.pct_diff is not None and deltas.ctr_diff.pct_diff > 0:
            key_learnings.append(
                f"CTR beat forecast by {deltas.ctr_diff.pct_diff:.1f}%, indicating stronger message-market fit than planned."
            )
        if deltas.cvr_diff.pct_diff is not None and deltas.cvr_diff.pct_diff > 0:
            key_learnings.append(
                f"CVR improved by {deltas.cvr_diff.pct_diff:.1f}%, suggesting the landing journey and offer matched traffic quality."
            )
        if deltas.cpa_diff.pct_diff is not None and not deltas.cpa_diff.favorable:
            anomalies.append(
                f"CPA worsened by {abs(deltas.cpa_diff.pct_diff):.1f}%, which indicates spend efficiency drift."
            )
        if deltas.roas_diff.pct_diff is None:
            anomalies.append("ROAS could not be evaluated because revenue was missing from the payload.")

        for finding in pattern_report.winning_audiences[:2]:
            if self._is_valid_text(finding.description):
                key_learnings.append(finding.description)
                recommendations.append(f"Expand tests around {finding.signal_key.replace('_', ' ')} and preserve the audience framing.")
        for finding in pattern_report.high_performing_creatives[:2]:
            if self._is_valid_text(finding.description):
                key_learnings.append(finding.description)
                recommendations.append(f"Increase creative production for {finding.signal_key.replace('_', ' ')} variants.")
        for finding in pattern_report.budget_inefficiencies[:2]:
            if self._is_valid_text(finding.description):
                anomalies.append(finding.description)
                recommendations.append(f"Tighten budget guardrails for {finding.signal_key.replace('_', ' ')} before scaling.")

        if similar_campaigns:
            recommendations.append(
                f"Reuse the playbook from `{similar_campaigns[0].campaign_id}` because it is the nearest semantic match in memory."
            )

        if not key_learnings:
            key_learnings.append("Campaign history is still sparse, so the system is relying on first-order metric comparisons.")
        if not recommendations:
            recommendations.append("Run a controlled follow-up test with one audience variable and one creative variable changed.")

        key_learnings = self._dedupe(key_learnings)
        recommendations = self._dedupe(recommendations)
        anomalies = self._dedupe(anomalies)

        narrative = " ".join(
            [
                "The engine compared expected and actual outcomes, then mapped the biggest deltas to recurring audience, creative, and platform signals.",
                "Positive metric movement is treated as a repeatable pattern candidate, while cost inflation or missing revenue is flagged for follow-up.",
            ]
        )

        return InsightExtractionOutput(
            narrative_summary=narrative,
            key_learnings=key_learnings[:6],
            recommendations=recommendations[:6],
            anomalies=anomalies[:6],
            source="deterministic",
        )

    def _is_valid_text(self, text: str) -> bool:
        if not text:
            return False

        t = text.strip().lower()

        if any(x in t for x in ("string", "unknown", "none")):
            return False
        if "0.0%" in t and "cvr" in t:
            return False
        if "data ingestion" in t or "duplicate" in t:
            return False
        if "high impact score" in t:
            return False
        if "lack performance data" in t:
            return False

        return True

    def _dedupe(self, items: list[str]) -> list[str]:
        if not items:
            return []

        deduped: list[str] = []
        seen: set[str] = set()

        for item in items:
            if not item:
                continue

            if not self._is_valid_text(item):
                continue

            key = item.strip().lower()

            if key in seen:
                continue

            seen.add(key)
            deduped.append(item.strip())

        return deduped

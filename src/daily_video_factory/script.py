from __future__ import annotations

import re
from typing import Any, cast

from .config import Settings
from .models import ResearchReport, ScriptDocument
from .providers.base import ProviderChain
from .providers.text import (
    GeminiTextProvider,
    OllamaTextProvider,
    OpenRouterTextProvider,
    TextProvider,
)

SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "hook", "body", "cta", "facts_to_verify", "disclosures"],
    "properties": {
        "title": {"type": "string", "minLength": 20, "maxLength": 100},
        "hook": {"type": "string", "minLength": 80},
        "body": {
            "type": "array",
            "minItems": 5,
            "maxItems": 10,
            "items": {"type": "string", "minLength": 120},
        },
        "cta": {"type": "string", "minLength": 50},
        "facts_to_verify": {"type": "array", "items": {"type": "string"}},
        "disclosures": {"type": "array", "items": {"type": "string"}},
    },
}


SYSTEM_PROMPT = """You are an experienced educational YouTube writer and compliance editor.
Write natural, specific narration for skeptical adults. Every paragraph must teach, demonstrate,
compare, or qualify something. Avoid filler, hype, fake urgency, clichés, and robotic signposting.
Never promise income, passive earnings, health outcomes, cures, guaranteed results, or financial
freedom. Never invent prices, ingredients, certifications, compensation-plan details, research
findings, or testimonials. Separate opinions from facts. Return only JSON matching the requested
schema."""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _trim_to_words(text: str, limit: int) -> str:
    text = text.strip()
    if _word_count(text) <= limit:
        return text.strip()
    kept: list[str] = []
    used = 0
    for token in re.findall(r"\S+", text):
        token_words = _word_count(token)
        if used + token_words > limit:
            break
        kept.append(token)
        used += token_words
    if not kept:
        kept = re.findall(r"\b[\w'-]+\b", text)[:limit]
    trimmed = " ".join(kept).rstrip(" ,;:-")
    return trimmed if trimmed.endswith((".", "!", "?")) else trimmed + "."


def _fit_segments_to_budget(segments: list[str], max_words: int) -> list[str]:
    """Proportionally compact LLM output while preserving every structured section."""
    counts = [_word_count(segment) for segment in segments]
    if sum(counts) <= max_words:
        return segments

    # Preserve a usable hook, every teaching section, and a low-pressure CTA even for
    # the one-minute Studio setting. Remaining words are distributed proportionally.
    floors = [min(counts[0], 18)]
    floors.extend(min(count, 8) for count in counts[1:-1])
    floors.append(min(counts[-1], 12))
    if sum(floors) > max_words:
        floors = [max(1, round(max_words * count / max(1, sum(counts)))) for count in counts]

    allocations = floors[:]
    remaining = max(0, max_words - sum(allocations))
    capacities = [count - allocation for count, allocation in zip(counts, allocations, strict=True)]
    capacity_total = sum(capacities)
    if remaining and capacity_total:
        additions = [min(capacity, remaining * capacity // capacity_total) for capacity in capacities]
        allocations = [
            allocation + addition
            for allocation, addition in zip(allocations, additions, strict=True)
        ]
        remaining -= sum(additions)
        for index in sorted(range(len(capacities)), key=capacities.__getitem__, reverse=True):
            if remaining <= 0:
                break
            available = counts[index] - allocations[index]
            extra = min(available, remaining)
            allocations[index] += extra
            remaining -= extra
    return [
        _trim_to_words(segment, allocation)
        for segment, allocation in zip(segments, allocations, strict=True)
    ]


class ScriptGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        providers: dict[str, TextProvider] = {
            "openrouter": OpenRouterTextProvider(settings.script.openrouter_model),
            "gemini": GeminiTextProvider(settings.script.gemini_model),
            "ollama": OllamaTextProvider(settings.script.ollama_model),
        }
        self.chain = ProviderChain(
            providers[name] for name in settings.script.text_providers if name in providers
        )

    def _prompt(self, report: ResearchReport) -> str:
        candidate_context = "\n".join(
            f"- {item.title} ({item.source}; signal score {item.score:.1f})"
            for item in report.candidates[:12]
        )
        source_context = (
            "\n".join(
                f"- {source.title} (checked {source.checked_on.isoformat()}): {source.summary}\n"
                f"  URL: {source.url}"
                for source in report.evidence
            )
            or "- No pinned official evidence is available. Avoid all specific brand claims."
        )
        brand = self.settings.channel.brand_name.strip()
        if report.brand_focused and brand:
            brand_instruction = (
                f"This is a brand-focused topic: name {brand} in the hook and answer the question "
                "directly, but do not turn the script into a recruitment pitch."
            )
        elif self.settings.channel.brand_required and brand:
            brand_instruction = (
                f"Do not mention {brand} until roughly "
                f"{self.settings.script.brand_mention_min_fraction:.0%} through the narration. "
                f"Evaluate {brand} as one optional case study alongside alternatives."
            )
        else:
            brand_instruction = "Do not force a brand mention or promotional case study."
        target = self.settings.script
        return f"""Create a {target.target_minutes:.0f}-minute YouTube narration.

SEARCH TOPIC: {report.selected_title}
EDITORIAL ANGLE: {report.selected_angle}
TARGET LENGTH: {target.min_words}-{target.max_words} spoken words
AUDIENCE: {", ".join(self.settings.channel.audience)}
CURRENT TOPIC SIGNALS (not factual evidence):
{candidate_context}

PINNED OFFICIAL / REGULATORY EVIDENCE:
{source_context}

Structure:
1. A concrete hook that identifies the viewer's tension without fearmongering.
2. Five to eight coherent teaching sections with examples, decision criteria, and caveats.
3. {brand_instruction}
4. Clearly separate sourced facts, reasonable interpretations, and unresolved questions.
5. A low-pressure CTA asking for a thoughtful comment or subscription, not a purchase.

Use the pinned evidence for specific brand or regulatory facts. Do not treat search signals as facts.
Do not copy source wording. Put any claim not directly supported by the pinned evidence into
facts_to_verify, and prefer omitting it entirely.

The maximum word count is a hard limit. Count the hook, every body section, and the CTA before
returning JSON; do not exceed {target.max_words} spoken words.

The title must be searchable but honest. Put every externally verifiable statement that may need
editorial checking into facts_to_verify. Include the AI-voice disclosure and this channel disclosure
in disclosures: {self.settings.channel.disclosure}. Do not add citations you cannot verify."""

    def _normalize(
        self,
        payload: dict[str, Any],
        provider: str,
        words_per_minute: int,
        report: ResearchReport,
    ) -> ScriptDocument:
        hook = str(payload["hook"]).strip()
        body = [str(part).strip() for part in payload["body"] if str(part).strip()]
        cta = str(payload["cta"]).strip()
        fitted = _fit_segments_to_budget(
            [hook, *body, cta], self.settings.script.max_words
        )
        hook, body, cta = fitted[0], fitted[1:-1], fitted[-1]
        full_text = "\n\n".join([hook, *body, cta])
        word_count = _word_count(full_text)
        return ScriptDocument(
            title=str(payload["title"]).strip(),
            hook=hook,
            body=body,
            cta=cta,
            full_text=full_text,
            word_count=word_count,
            estimated_minutes=round(word_count / words_per_minute, 2),
            facts_to_verify=[str(value) for value in payload.get("facts_to_verify", [])],
            disclosures=[str(value) for value in payload.get("disclosures", [])],
            brand_focused=report.brand_focused,
            source_urls=[source.url for source in report.evidence],
            provider=provider,
        )

    def run(self, report: ResearchReport) -> ScriptDocument:
        result = self.chain.run(
            "script_generation",
            lambda provider: cast(TextProvider, provider).generate_json(
                system=SYSTEM_PROMPT,
                prompt=self._prompt(report),
                schema=SCRIPT_SCHEMA,
                temperature=0.65,
            ),
        )
        return self._normalize(
            result.value,
            result.provider,
            self.settings.script.words_per_minute,
            report,
        )

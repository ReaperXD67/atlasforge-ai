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
Write natural, specific narration for skeptical adults, not existing brand members. Every paragraph
must teach, demonstrate, compare, or qualify something. Avoid filler, hype, fake urgency, clichés,
and robotic signposting. Never promise income, passive earnings, health outcomes, cures, guaranteed
results, or financial freedom. Never invent prices, ingredients, certifications, compensation-plan
details, research findings, or testimonials. Separate opinions from facts. Mention Atomy only after
the viewer has received substantial independent value, and present it as one option with tradeoffs.
Return only JSON matching the requested schema."""


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
        target = self.settings.script
        return f"""Create a {target.target_minutes:.0f}-minute YouTube narration.

SEARCH TOPIC: {report.selected_title}
EDITORIAL ANGLE: {report.selected_angle}
TARGET LENGTH: {target.min_words}-{target.max_words} spoken words
AUDIENCE: {', '.join(self.settings.channel.audience)}
CURRENT TOPIC SIGNALS (not factual evidence):
{candidate_context}

Structure:
1. A concrete hook that identifies the viewer's tension without fearmongering.
2. Five to eight coherent teaching sections with examples, decision criteria, and caveats.
3. Do not mention Atomy until roughly {target.brand_mention_min_fraction:.0%} through the narration.
4. Evaluate Atomy as one optional case study alongside non-Atomy alternatives.
5. A low-pressure CTA asking for a thoughtful comment or subscription, not a purchase.

The title must be searchable but honest. Put every externally verifiable statement that may need
editorial checking into facts_to_verify. Include both the AI-voice disclosure and the educational
financial/medical disclaimer in disclosures. Do not add citations you cannot verify."""

    @staticmethod
    def _normalize(payload: dict[str, Any], provider: str, words_per_minute: int) -> ScriptDocument:
        hook = str(payload["hook"]).strip()
        body = [str(part).strip() for part in payload["body"] if str(part).strip()]
        cta = str(payload["cta"]).strip()
        full_text = "\n\n".join([hook, *body, cta])
        word_count = len(re.findall(r"\b[\w'-]+\b", full_text))
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
            result.value, result.provider, self.settings.script.words_per_minute
        )

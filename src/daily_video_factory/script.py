from __future__ import annotations

import json
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
schema. For Atomy, write "PV" or "Personal PV" exactly as the official U.S. plan does; never expand
it as "Point Value" or "Personal Volume." Do not redundantly define the acronym or write awkward
constructions such as "Personal PV, or PV"; direct viewers to the official plan for its mechanics."""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


GENERIC_HOOK_PATTERNS = (
    r"^considering\b",
    r"^have you ever\b",
    r"^you (?:may|might) have\b",
    r"^in today'?s (?:video|world)\b",
    r"^welcome (?:back|to)\b",
    r"\byou (?:may|might) be wondering\b",
    r"\blet'?s (?:dive|delve|get)\b",
)
DYNAMIC_SECTION_START = re.compile(
    r"^(?:but|before|if|why|what|which|the catch|here(?:'s| is)|most people|"
    r"the useful part|the part people miss|now compare|instead)",
    flags=re.IGNORECASE,
)
VIEWER_PROMISE = re.compile(
    r"\b(?:you(?:'ll| will)|we(?:'ll| will)|by the end|show you|walk through|"
    r"separate|compare|decide|check|spot|avoid)\b",
    flags=re.IGNORECASE,
)


def _has_dynamic_start(section: str) -> bool:
    sentences = _sentences(section)
    first_sentence = sentences[0] if sentences else section
    return "?" in first_sentence or DYNAMIC_SECTION_START.match(first_sentence) is not None


def _clean_spoken_copy(text: str) -> str:
    """Remove a few known TTS-hostile constructions without changing their meaning."""
    text = re.sub(r"\bPersonal PV,\s+or PV,?", "Personal PV", text, flags=re.IGNORECASE)
    text = re.sub(r"\bPV,\s+or Personal PV,?", "Personal PV", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _enforce_engagement_structure(payload: dict[str, Any], brand: str = "") -> dict[str, Any]:
    """Apply a conservative local fallback after the bounded LLM rewrite attempts."""
    polished = dict(payload)
    hook = _clean_spoken_copy(str(payload.get("hook", "")))
    if any(re.search(pattern, hook, flags=re.IGNORECASE) for pattern in GENERIC_HOOK_PATTERNS):
        brand_phrase = f"{brand.strip()} " if brand.strip() else ""
        hook = (
            f"The easiest-looking {brand_phrase}choice can create the wrong expectations later. "
            "Before you act, three checks will separate the paths, trade-offs, and details "
            "worth verifying."
        )
    if _word_count(hook) > 35:
        hook = _trim_to_words(hook, 35)
    if _word_count(hook) < 20:
        hook = f"{hook.rstrip('.!?')}—and the key is seeing the trade-off before you commit."
    polished["hook"] = hook

    body = [_clean_spoken_copy(str(part)) for part in payload.get("body", []) if str(part).strip()]
    first_75 = " ".join(re.findall(r"\S+", " ".join([hook, *body]))[:75])
    if body and VIEWER_PROMISE.search(first_75) is None:
        body[0] = (
            "In the next two minutes, you'll know what to decide, what to verify, and what to "
            f"do next. {body[0]}"
        )

    dynamic_starts = sum(_has_dynamic_start(section) for section in body)
    required_dynamic_starts = min(3, max(1, len(body) // 2))
    prefixes = (
        "Here's the useful part: ",
        "But there's a trade-off: ",
        "What should you check next? ",
    )
    for index, section in enumerate(body):
        if dynamic_starts >= required_dynamic_starts:
            break
        if not _has_dynamic_start(section):
            body[index] = f"{prefixes[dynamic_starts % len(prefixes)]}{section}"
            dynamic_starts += 1
    polished["body"] = body

    cta = _clean_spoken_copy(str(payload.get("cta", "")))
    if not re.search(
        r"\b(?:ask|comment|message|reach out|share|guided|walkthrough|help)\b",
        cta,
        flags=re.IGNORECASE,
    ):
        cta = f"If you want help checking your situation, ask for a guided walkthrough. {cta}"
    polished["cta"] = cta
    return polished


def _engagement_issues(payload: dict[str, Any]) -> list[str]:
    """Return concrete retention failures that deserve one focused rewrite."""
    hook = str(payload.get("hook", "")).strip()
    body = [str(part).strip() for part in payload.get("body", []) if str(part).strip()]
    cta = str(payload.get("cta", "")).strip()
    issues: list[str] = []
    hook_words = _word_count(hook)
    if not 20 <= hook_words <= 35:
        issues.append(f"the cold open is {hook_words} words instead of 20-35")
    if any(re.search(pattern, hook, flags=re.IGNORECASE) for pattern in GENERIC_HOOK_PATTERNS):
        issues.append("the cold open uses a generic YouTube opener")

    first_words = " ".join([hook, *body])
    first_75 = " ".join(re.findall(r"\S+", first_words)[:75])
    if VIEWER_PROMISE.search(first_75) is None:
        issues.append("the first 75 words do not make a concrete viewer promise")

    dynamic_starts = 0
    for section in body:
        if _has_dynamic_start(section):
            dynamic_starts += 1
    required_dynamic_starts = min(3, max(1, len(body) // 2))
    if dynamic_starts < required_dynamic_starts:
        issues.append(
            "too few teaching sections open with a question, contrast, objection, or payoff"
        )
    if not re.search(
        r"\b(?:ask|comment|message|reach out|share|guided|walkthrough|help)\b",
        cta,
        flags=re.IGNORECASE,
    ):
        issues.append("the CTA does not give the viewer a direct low-pressure next step")
    return issues


def _sentences(text: str) -> list[str]:
    marker = "<prd>"

    def protect(match: re.Match[str]) -> str:
        return match.group(0).replace(".", marker)

    protected = re.sub(
        r"\b(?:[A-Za-z]\.){2,}",
        protect,
        re.sub(
            r"\b(?:e\.g|i\.e|Mr|Mrs|Ms|Dr|St)\.",
            protect,
            text,
            flags=re.IGNORECASE,
        ),
        flags=re.IGNORECASE,
    )
    return [
        sentence.replace(marker, ".").strip()
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", protected))
        if sentence.strip()
    ]


def _trim_to_words(text: str, limit: int) -> str:
    text = text.strip()
    if _word_count(text) <= limit:
        return text.strip()
    sentences = _sentences(text)
    complete: list[str] = []
    used = 0
    for sentence in sentences:
        count = _word_count(sentence)
        if used + count > limit:
            break
        complete.append(sentence)
        used += count
    if complete:
        return " ".join(complete)

    # A single overlong sentence is the only case where a hard word cut is necessary.
    # Prefer a natural clause boundary before taking that fallback.
    clauses = [part.strip() for part in re.split(r"(?<=[,;:])\s+", text) if part.strip()]
    complete_clauses: list[str] = []
    used = 0
    for clause in clauses:
        count = _word_count(clause)
        if used + count > limit:
            break
        complete_clauses.append(clause)
        used += count
    if complete_clauses:
        trimmed_clause = " ".join(complete_clauses).rstrip(" ,;:-")
        return trimmed_clause if trimmed_clause.endswith((".", "!", "?")) else trimmed_clause + "."

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
        additions = [
            min(capacity, remaining * capacity // capacity_total) for capacity in capacities
        ]
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


def _reclaim_body_budget(
    hook: str,
    body: list[str],
    cta: str,
    max_words: int,
) -> tuple[str, list[str], str]:
    """Trim explanation from the longest sections without sacrificing retention anchors."""
    overflow = sum(_word_count(part) for part in [hook, *body, cta]) - max_words
    if overflow <= 0:
        return hook, body, cta

    # Protect the hook, first-third promise, dynamic paragraph openings, and actionable CTA.
    # Later/longer explanation absorbs the reduction first.
    order = sorted(range(1, len(body)), key=lambda index: _word_count(body[index]), reverse=True)
    order.extend([0] if body else [])
    for index in order:
        if overflow <= 0:
            break
        current = _word_count(body[index])
        floor = 18 if index == 0 else 14
        removable = max(0, current - floor)
        if not removable:
            continue
        before = current
        body[index] = _trim_to_words(body[index], current - min(removable, overflow))
        overflow -= max(0, before - _word_count(body[index]))
    return hook, body, cta


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
CONTENT GOAL: {self.settings.channel.content_goal}
TARGET LENGTH: {target.min_words}-{target.max_words} spoken words
AUDIENCE: {", ".join(self.settings.channel.audience)}
CURRENT TOPIC SIGNALS (not factual evidence):
{candidate_context}

PINNED OFFICIAL / REGULATORY EVIDENCE:
{source_context}

        Retention-first structure:
        1. Cold-open in 20-35 spoken words: begin with a viewer-specific question, surprising
           trade-off, or consequential mistake. No greeting, channel intro, or generic preamble.
        2. By the first 75 spoken words, state exactly what the viewer will be able to decide or do.
           Open one honest curiosity loop that the final third resolves; never manufacture suspense.
        3. Five to eight coherent teaching sections. Start each section with a fresh question,
           contrast, objection, or mini-payoff; then give an example, decision criterion, or action.
           Alternate tension, proof, and practical next step so the narration does not become a list.
        4. Put the most useful concrete step early. Around the midpoint, include a concise pattern
           interrupt such as "Here is the part most people miss" only when the following point earns it.
        5. {brand_instruction}
        6. Clearly separate sourced facts, reasonable interpretations, and unresolved questions.
        7. Resolve the opening loop before a low-pressure CTA. Invite the viewer to ask for guided
           help or share their situation, without urgency, pressure, a purchase, or an earnings promise.

        Performance writing:
        - Write for a lively human voice: short sentences beside occasional longer ones, contractions,
          deliberate questions, and punctuation that creates natural breath. Avoid repetitive sentence
          openings, corporate filler, stacked clauses, and robotic enumeration.
        - Energy must come from specificity, stakes, contrast, and useful payoff—not hype.

Use the pinned evidence for specific brand or regulatory facts. Do not treat search signals as facts.
Do not copy source wording. Put any claim not directly supported by the pinned evidence into
facts_to_verify, and prefer omitting it entirely.

The maximum word count is a hard limit. Count the hook, every body section, and the CTA before
returning JSON; do not exceed {target.max_words} spoken words.

The title must be searchable but honest. Put every externally verifiable statement that may need
        editorial checking into facts_to_verify. Include the synthetic-voice disclosure and this channel disclosure
in disclosures: {self.settings.channel.disclosure}. Do not add citations you cannot verify."""

    def _repair_prompt(
        self,
        payload: dict[str, Any],
        preferred_min_words: int,
        engagement_issues: list[str],
    ) -> str:
        target = self.settings.script
        quality_failures = (
            "\n".join(f"- {issue}" for issue in engagement_issues)
            or "- the runtime is below the preferred spoken-word target"
        )
        return f"""Revise the JSON narration below so its spoken narration contains between
{preferred_min_words} and {target.max_words} words. Preserve its title, factual restraint,
disclosures, and low-pressure intent.

The automated creative gate rejected these specific problems:
{quality_failures}

Fix them, not just the word count:
- Replace any generic opener with a 20-35 word cold open built from a consequential choice,
  believable mistake, or sharp contrast. Never begin with "Considering", "Have you ever",
  "In today's video", "You might be wondering", "Welcome", or "Let's dive in".
- Within the first 75 words, say exactly what the viewer will be able to decide, check, or avoid.
- Make at least three body sections begin with a real question, contrast, objection, or mini-payoff.
- Move a useful decision criterion or action into the first third. Vary sentence length and use
  contractions so it sounds performed rather than read from a brochure.
- Resolve the opening choice before a direct, low-pressure invitation for guided help.

Add useful clarification, examples, or decision guidance; never pad with repetition, hype,
invented details, earnings claims, health claims, or artificial suspense. Keep five to eight body
sections and return only JSON matching the original schema.

ORIGINAL JSON:
{json.dumps(payload, ensure_ascii=False)}"""

    def _normalize(
        self,
        payload: dict[str, Any],
        provider: str,
        words_per_minute: int,
        report: ResearchReport,
    ) -> ScriptDocument:
        brand = self.settings.channel.brand_name if report.brand_focused else ""
        payload = _enforce_engagement_structure(payload, brand)
        hook = str(payload["hook"]).strip()
        body = [str(part).strip() for part in payload["body"] if str(part).strip()]
        cta = str(payload["cta"]).strip()
        fitted = _fit_segments_to_budget([hook, *body, cta], self.settings.script.max_words)
        hook, body, cta = fitted[0], fitted[1:-1], fitted[-1]
        # Proportional compaction can remove a deliberately short promise or CTA. Run the local
        # guard once more, then reclaim any added words from later explanatory sections.
        retained = _enforce_engagement_structure(
            {"hook": hook, "body": body, "cta": cta},
            brand,
        )
        hook = str(retained["hook"])
        body = [str(part) for part in retained["body"]]
        cta = str(retained["cta"])
        hook, body, cta = _reclaim_body_budget(
            hook,
            body,
            cta,
            self.settings.script.max_words,
        )
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
        document = self._normalize(
            result.value,
            result.provider,
            self.settings.script.words_per_minute,
            report,
        )
        target = self.settings.script
        preferred_min_words = min(
            target.max_words,
            max(
                target.min_words,
                round(target.target_minutes * target.words_per_minute * 0.90),
            ),
        )
        engagement_issues = _engagement_issues(result.value)
        if document.word_count >= preferred_min_words and not engagement_issues:
            return document

        # Model word counts vary slightly even with a precise prompt. One focused repair gives
        # the writer a chance to reach the intended runtime, while the original remains a safe
        # fallback whenever it already clears the hard quality floor.
        try:
            repaired = self.chain.run(
                "script_length_repair",
                lambda provider: cast(TextProvider, provider).generate_json(
                    system=SYSTEM_PROMPT,
                    prompt=self._repair_prompt(
                        result.value,
                        preferred_min_words,
                        engagement_issues,
                    ),
                    schema=SCRIPT_SCHEMA,
                    temperature=0.25,
                ),
            )
            repaired_document = self._normalize(
                repaired.value,
                repaired.provider,
                target.words_per_minute,
                report,
            )
            repaired_issues = _engagement_issues(repaired.value)
            original_rank = (
                len(engagement_issues),
                max(0, preferred_min_words - document.word_count),
                -document.word_count,
            )
            repaired_rank = (
                len(repaired_issues),
                max(0, preferred_min_words - repaired_document.word_count),
                -repaired_document.word_count,
            )
            if repaired_rank < original_rank:
                document = repaired_document
                best_payload = repaired.value
                best_issues = repaired_issues
                # A second pass is reserved for cases where the first rewrite clearly improved
                # the script but left a smaller, concrete defect. This avoids open-ended LLM loops.
                if best_issues and len(best_issues) < len(engagement_issues):
                    polished = self.chain.run(
                        "script_final_polish",
                        lambda provider: cast(TextProvider, provider).generate_json(
                            system=SYSTEM_PROMPT,
                            prompt=self._repair_prompt(
                                best_payload,
                                preferred_min_words,
                                best_issues,
                            ),
                            schema=SCRIPT_SCHEMA,
                            temperature=0.2,
                        ),
                    )
                    polished_document = self._normalize(
                        polished.value,
                        polished.provider,
                        target.words_per_minute,
                        report,
                    )
                    polished_rank = (
                        len(_engagement_issues(polished.value)),
                        max(0, preferred_min_words - polished_document.word_count),
                        -polished_document.word_count,
                    )
                    if polished_rank < repaired_rank:
                        return polished_document
                return document
        except Exception:
            # ProviderChain already records the concrete provider failure. The downstream quality
            # gate still rejects a result below the hard floor; a usable original is never lost.
            pass
        return document

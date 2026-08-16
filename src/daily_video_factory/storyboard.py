from __future__ import annotations

import re

from .config import Settings
from .models import Scene, ScriptDocument, Storyboard


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
    )
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", re.sub(r"\s+", " ", protected).strip())
    return [part.replace(marker, ".").strip() for part in parts if part.strip()]


def _visual_plan(narration: str, index: int, title: str) -> tuple[str, str, str]:
    """Turn narration into a concrete, stock-searchable shot instead of keyword soup."""
    lower = narration.lower()
    plans = [
        (
            {"register", "registration", "application", "website", "sign-up"},
            (
                "person completing online registration on laptop close up",
                "hands typing secure online application form on laptop",
            ),
            "Registration walkthrough",
        ),
        (
            {"phone", "mobile", "verification", "code"},
            (
                "smartphone verification code hands close up",
                "person receiving secure mobile code at home",
            ),
            "Verify your mobile number",
        ),
        (
            {"sponsor", "mentor", "guidance"},
            (
                "business mentor meeting adult learner with laptop",
                "adult taking notes during online coaching session on laptop",
            ),
            "Choose a sponsor carefully",
        ),
        (
            {"consumer", "distributor", "membership", "member"},
            (
                "two adults comparing options and taking notes at desk",
                "person comparing a checklist of choices in notebook",
            ),
            "Consumer or distributor?",
        ),
        (
            {
                "bank",
                "social security",
                "identity",
                "legal name",
                "identification",
                "resident",
                "18 years",
            },
            (
                "adult checking passport identification before online registration",
                "hands holding passport identification beside laptop close up",
            ),
            "Use accurate legal details",
        ),
        (
            {"product", "skincare", "supplement", "wellness"},
            (
                "skincare products on clean shelf cinematic",
                "woman applying skincare serum at mirror natural light",
                "skincare serum bottle on clean vanity close up",
            ),
            "Understand the products",
        ),
        (
            {
                "pv",
                "commission",
                "income",
                "expense",
                "profit",
                "compensation",
                "tax",
                "independent participant",
            },
            (
                "small business owner reviewing calculator and expenses",
                "receipts notebook and budget planning overhead close up",
            ),
            "Revenue is not profit",
        ),
        (
            {"risk", "claim", "ftc", "evidence", "official", "verify"},
            (
                "professional fact checking trusted information on laptop and notebook",
                "consumer carefully reviewing terms on tablet at home",
            ),
            "Check the official source",
        ),
        (
            {"goal", "budget", "time", "decision", "compare"},
            (
                "thoughtful person planning budget and goals in notebook",
                "person comparing priorities on sticky notes at home",
            ),
            "Compare the trade-offs",
        ),
    ]
    ranked = sorted(
        (
            (sum(signal in lower for signal in signals), signals, queries, card_title)
            for signals, queries, card_title in plans
        ),
        key=lambda match: match[0],
        reverse=True,
    )
    if ranked and ranked[0][0] > 0:
        _score, signals, queries, card_title = ranked[0]
        matched_signals = {signal for signal in signals if signal in lower}
        exact_fact = matched_signals & {
            "pv",
            "commission",
            "social security",
            "legal name",
            "ftc",
        }
        must_own_visual = matched_signals & {"social security", "legal name", "ftc"}
        mode = (
            "information_card"
            if must_own_visual or (exact_fact and index % 3 == 0)
            else "documentary_broll"
        )
        return queries[(index - 1) % len(queries)], card_title, mode
    if index == 1:
        return (
            "confident adult beginning an online learning journey cinematic",
            title,
            "local_ai_candidate",
        )
    return (
        "authentic adult learning and taking notes in calm home office",
        "A practical next step",
        "documentary_broll",
    )


class StoryboardBuilder:
    ENVIRONMENTS = [
        "calm home office with tactile desk details",
        "modern city commute at early morning",
        "minimal Korean-inspired skincare shelf",
        "bright kitchen with everyday wellness objects",
        "small business planning table with notebooks",
        "abstract editorial space with layered paper textures",
        "quiet neighborhood walk at golden hour",
    ]
    ANGLES = [
        "slow push-in medium shot",
        "overhead detail shot",
        "wide establishing shot",
        "shallow-focus close-up",
        "subtle lateral tracking shot",
        "locked symmetrical composition",
    ]
    LIGHTING = [
        "soft window light with warm practicals",
        "clean diffused daylight",
        "golden-hour rim light",
        "low-key cinematic contrast",
    ]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, script: ScriptDocument) -> Storyboard:
        cfg = self.settings.storyboard
        sentences = _sentences(script.full_text)
        target_words = max(
            25, round(cfg.target_scene_seconds * self.settings.script.words_per_minute / 60)
        )
        groups: list[list[str]] = []
        current: list[str] = []
        current_words = 0
        for sentence in sentences:
            count = len(sentence.split())
            if current and current_words + count > target_words * 1.25:
                groups.append(current)
                current, current_words = [], 0
            current.append(sentence)
            current_words += count
        if current:
            groups.append(current)

        while len(groups) > cfg.max_scenes:
            tail = groups.pop()
            groups[-1].extend(tail)

        scenes: list[Scene] = []
        for index, group in enumerate(groups):
            narration = " ".join(group)
            words = len(narration.split())
            duration = words / self.settings.script.words_per_minute * 60
            duration = max(cfg.min_scene_seconds, min(cfg.max_scene_seconds, duration))
            lower = narration.lower()
            is_hook = index == 0
            is_product = any(word in lower for word in {"product", "skincare", "supplement"})
            is_emotional = any(
                word in lower for word in {"fear", "hope", "freedom", "overwhelmed", "confidence"}
            )
            has_motion = any(
                word in lower for word in {"build", "change", "journey", "grow", "move"}
            )
            premium = min(
                1.0,
                0.2 + 0.35 * is_hook + 0.25 * is_product + 0.15 * is_emotional + 0.1 * has_motion,
            )
            visual_query, onscreen_title, visual_mode = _visual_plan(
                narration, index + 1, script.title
            )
            if is_hook and visual_mode != "information_card":
                # The local generator opens on a brand-safe conceptual scene. Real product
                # claims and packaging remain licensed footage or owned information cards.
                visual_query = "open notebook smartphone and laptop on clean desk morning light"
                onscreen_title = script.title
                visual_mode = "local_ai_candidate"
            environment = self.ENVIRONMENTS[index % len(self.ENVIRONMENTS)]
            angle = self.ANGLES[index % len(self.ANGLES)]
            lighting = self.LIGHTING[index % len(self.LIGHTING)]
            scenes.append(
                Scene(
                    index=index + 1,
                    duration_seconds=round(duration, 2),
                    narration=narration,
                    camera_angle=angle,
                    environment=environment,
                    character_description="authentic adult learner or independent professional",
                    emotion="curious and grounded" if not is_emotional else "quietly reflective",
                    lighting=lighting,
                    sound_effects=["soft_whoosh"] if index else ["cinematic_rise"],
                    transition="crossfade" if index else "fade_from_black",
                    video_prompt=(
                        f"Cinematic documentary b-roll of {visual_query}, {environment}, "
                        f"{angle}, {lighting}, "
                        "natural human movement, realistic textures, no logos, no text, 16:9"
                    ),
                    visual_search_query=visual_query,
                    onscreen_title=onscreen_title,
                    visual_mode=visual_mode,
                    premium_score=round(premium, 2),
                )
            )
        total = round(sum(scene.duration_seconds for scene in scenes), 2)
        return Storyboard(
            title=script.title,
            total_duration_seconds=total,
            scenes=scenes,
            provider="deterministic",
        )

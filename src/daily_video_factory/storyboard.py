from __future__ import annotations

import re

from .config import Settings
from .models import Scene, ScriptDocument, Storyboard


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", re.sub(r"\s+", " ", text).strip())
    return [part.strip() for part in parts if part.strip()]


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
        target_words = max(25, round(cfg.target_scene_seconds * self.settings.script.words_per_minute / 60))
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
            is_product = any(word in lower for word in {"atomy", "product", "skincare", "supplement"})
            is_emotional = any(
                word in lower for word in {"fear", "hope", "freedom", "overwhelmed", "confidence"}
            )
            has_motion = any(word in lower for word in {"build", "change", "journey", "grow", "move"})
            premium = min(1.0, 0.2 + 0.35 * is_hook + 0.25 * is_product + 0.15 * is_emotional + 0.1 * has_motion)
            keywords = [
                word
                for word in re.findall(r"[a-zA-Z]{4,}", narration)
                if word.lower() not in {"that", "this", "with", "from", "your", "have", "will"}
            ][:5]
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
                        f"Cinematic documentary b-roll, {environment}, {angle}, {lighting}, "
                        "natural human movement, realistic textures, no logos, no text, 16:9"
                    ),
                    visual_search_query=" ".join(keywords) or script.title,
                    premium_score=round(premium, 2),
                )
            )
        total = round(sum(scene.duration_seconds for scene in scenes), 2)
        return Storyboard(title=script.title, total_duration_seconds=total, scenes=scenes, provider="deterministic")


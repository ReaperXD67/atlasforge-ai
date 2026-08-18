from __future__ import annotations

import hashlib
import json
import os
import random
import textwrap
from abc import abstractmethod
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import Settings
from ..exceptions import ProviderFailed
from ..models import OWNED_VISUAL_MODES, Scene
from .base import Provider


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _wrap_text(text: str, width: int, max_lines: int | None = None) -> str:
    """Wrap display copy without splitting readable compounds such as “trade-offs”."""
    lines = textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return "\n".join(lines if max_lines is None else lines[:max_lines])


class ImageProvider(Provider[Path]):
    @abstractmethod
    def generate(self, scene: Scene, output: Path) -> Path:
        pass


class PexelsImageProvider(ImageProvider):
    name = "pexels"

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.images

    def available(self) -> bool:
        return bool(os.getenv("PEXELS_API_KEY"))

    def generate(self, scene: Scene, output: Path) -> Path:
        response = httpx.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": os.environ["PEXELS_API_KEY"]},
            params={
                "query": scene.visual_search_query,
                "orientation": self.cfg.pexels_orientation,
                "per_page": 15,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise ProviderFailed(f"Pexels returned HTTP {response.status_code}")
        photos = response.json().get("photos", [])
        if not photos:
            raise ProviderFailed("Pexels returned no images")
        photo = photos[(scene.index - 1) % len(photos)]
        source = photo["src"].get("large2x") or photo["src"]["large"]
        image_response = httpx.get(source, timeout=60, follow_redirects=True)
        image_response.raise_for_status()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_response.content)
        attribution = {
            "provider": "Pexels",
            "photographer": photo.get("photographer"),
            "photographer_url": photo.get("photographer_url"),
            "photo_url": photo.get("url"),
        }
        output.with_suffix(".license.json").write_text(
            json.dumps(attribution, indent=2), encoding="utf-8"
        )
        self._fit(output)
        return output

    def _fit(self, path: Path) -> None:
        with Image.open(path) as source:
            image = source.convert("RGB")
            ratio = max(self.cfg.width / image.width, self.cfg.height / image.height)
            image = image.resize(
                (round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS
            )
            left = (image.width - self.cfg.width) // 2
            top = (image.height - self.cfg.height) // 2
            image.crop((left, top, left + self.cfg.width, top + self.cfg.height)).save(
                path, quality=94
            )


class TitleCardImageProvider(ImageProvider):
    name = "title_card"
    PALETTES = [
        ((12, 18, 26), (42, 92, 100), (246, 189, 66)),
        ((20, 17, 32), (102, 69, 119), (234, 134, 113)),
        ((14, 24, 22), (44, 102, 86), (215, 231, 199)),
        ((23, 26, 33), (55, 70, 91), (239, 104, 70)),
    ]

    def __init__(self, settings: Settings) -> None:
        self.cfg = settings.images

    def available(self) -> bool:
        return True

    def generate(self, scene: Scene, output: Path) -> Path:
        seed = int(hashlib.sha256(scene.video_prompt.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)
        bg, mid, accent = self.PALETTES[scene.index % len(self.PALETTES)]
        image = Image.new("RGB", (self.cfg.width, self.cfg.height), bg)
        draw = ImageDraw.Draw(image, "RGBA")
        for _ in range(18):
            x = rng.randint(-300, self.cfg.width)
            y = rng.randint(-300, self.cfg.height)
            size = rng.randint(160, 700)
            color = (*mid, rng.randint(18, 70))
            draw.ellipse((x, y, x + size, y + size), fill=color)
        image = image.filter(ImageFilter.GaussianBlur(radius=45))
        draw = ImageDraw.Draw(image, "RGBA")
        title_copy = scene.onscreen_title or scene.visual_search_query
        draw.rounded_rectangle(
            (88, 82, 1832, 998),
            radius=42,
            fill=(8, 13, 22, 218),
            outline=(*accent, 112),
            width=2,
        )
        draw.text((142, 122), "ATOMY USA  /  RETENTION CUT", font=_font(26, True), fill=(*accent, 255))
        draw.text((1660, 122), f"{scene.index:02d}", font=_font(30, True), fill=(210, 214, 216, 210))

        if scene.visual_mode == "kinetic_statement":
            draw.rounded_rectangle((138, 242, 362, 316), radius=36, fill=(*accent, 255))
            draw.text((180, 260), "THE PROMISE", font=_font(24, True), fill=(8, 13, 22, 255))
            title = _wrap_text(title_copy, width=25, max_lines=3)
            draw.multiline_text((142, 382), title, font=_font(100, True), fill=(250, 248, 242, 255), spacing=9)
            draw.rectangle((142, 790, 930, 804), fill=(*accent, 235))
        elif scene.visual_mode == "step_card":
            draw.text((128, 230), f"{scene.index:02d}", font=_font(270, True), fill=(*accent, 238))
            draw.line((620, 260, 620, 820), fill=(*accent, 150), width=3)
            draw.text((704, 270), "NEXT DECISION", font=_font(30, True), fill=(*accent, 255))
            title = _wrap_text(title_copy, width=20, max_lines=4)
            draw.multiline_text((704, 370), title, font=_font(76, True), fill=(250, 248, 242, 255), spacing=10)
        elif scene.visual_mode == "comparison_card":
            title = _wrap_text(title_copy, width=34, max_lines=2)
            draw.multiline_text((142, 220), title, font=_font(72, True), fill=(250, 248, 242, 255), spacing=8)
            for left, label, note in (
                (142, "CONSUMER", "Product access and informed use"),
                (986, "DISTRIBUTOR", "Responsibilities, costs, and goals"),
            ):
                draw.rounded_rectangle((left, 520, left + 704, 820), radius=28, fill=(18, 25, 34, 238), outline=(*accent, 112), width=2)
                draw.text((left + 42, 570), label, font=_font(36, True), fill=(*accent, 255))
                note_copy = _wrap_text(note, width=27)
                draw.multiline_text((left + 42, 650), note_copy, font=_font(30), fill=(226, 230, 228, 225), spacing=7)
        elif scene.visual_mode == "proof_card":
            draw.rounded_rectangle((142, 230, 390, 306), radius=38, fill=(*accent, 255))
            draw.text((190, 249), "VERIFY", font=_font(28, True), fill=(8, 13, 22, 255))
            title = _wrap_text(title_copy, width=27, max_lines=3)
            draw.multiline_text((142, 380), title, font=_font(88, True), fill=(250, 248, 242, 255), spacing=9)
            draw.rounded_rectangle((142, 740, 1460, 828), radius=16, fill=(21, 30, 39, 245), outline=(*accent, 88), width=2)
            draw.text((178, 766), "OFFICIAL PAGE  →  READ THE CURRENT REQUIREMENTS", font=_font(25, True), fill=(222, 228, 226, 230))
        else:
            draw.rectangle((90, 92, 104, 990), fill=(*accent, 255))
            title = _wrap_text(title_copy, width=24, max_lines=4)
            draw.multiline_text((148, 290), title, font=_font(88, True), fill=(248, 246, 240, 255), spacing=10)

        # Keep the subtitle-safe lower band visually quiet. Burned captions own that area.
        draw.line((142, 910, 1778, 910), fill=(*accent, 112), width=2)
        draw.text((142, 942), "CLEAR STEPS  •  OFFICIAL SOURCES  •  NO HYPE", font=_font(21, True), fill=(176, 185, 192, 210))
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, quality=95)
        output.with_suffix(".license.json").write_text(
            json.dumps({"provider": "locally_generated", "license": "project-owned"}, indent=2),
            encoding="utf-8",
        )
        return output


class SceneImageGenerator:
    def __init__(self, settings: Settings) -> None:
        mapping: dict[str, ImageProvider] = {
            "pexels": PexelsImageProvider(settings),
            "title_card": TitleCardImageProvider(settings),
        }
        self.providers = [mapping[name] for name in settings.images.providers if name in mapping]

    def run(self, scene: Scene, output: Path) -> tuple[str, Path]:
        errors: list[str] = []
        providers = self.providers
        if scene.visual_mode in OWNED_VISUAL_MODES:
            providers = sorted(self.providers, key=lambda provider: provider.name != "title_card")
        for provider in providers:
            if not provider.available():
                continue
            try:
                return provider.name, provider.generate(scene, output)
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
        raise ProviderFailed(
            f"No image provider could render scene {scene.index}: {' | '.join(errors)}"
        )

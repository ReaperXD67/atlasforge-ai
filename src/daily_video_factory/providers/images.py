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
from ..models import Scene
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
        draw.rectangle((90, 92, 104, 990), fill=(*accent, 255))
        draw.text((142, 104), f"SCENE {scene.index:02d}", font=_font(30, True), fill=(*accent, 255))
        words = scene.visual_search_query.upper().split()[:7]
        title = "\n".join(textwrap.wrap(" ".join(words), width=18))
        draw.multiline_text(
            (142, 220), title, font=_font(86, True), fill=(248, 246, 240, 255), spacing=12
        )
        caption = textwrap.fill(scene.environment, width=44)
        draw.multiline_text(
            (146, 800), caption, font=_font(34), fill=(225, 229, 226, 220), spacing=8
        )
        draw.line((142, 950, 890, 950), fill=(*accent, 170), width=3)
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
        for provider in self.providers:
            if not provider.available():
                continue
            try:
                return provider.name, provider.generate(scene, output)
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
        raise ProviderFailed(
            f"No image provider could render scene {scene.index}: {' | '.join(errors)}"
        )

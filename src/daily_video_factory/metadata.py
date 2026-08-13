from __future__ import annotations

import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .config import Settings
from .models import ScriptDocument, Storyboard, VideoMetadata


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    choices = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _chapter_time(seconds: float) -> str:
    total = max(0, round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def build_metadata(script: ScriptDocument, storyboard: Storyboard, settings: Settings) -> VideoMetadata:
    title = script.title[:100].rstrip(" -:,.!")
    tags = list(
        dict.fromkeys(
            [
                "online business",
                "side hustle",
                "entrepreneurship",
                "business mindset",
                "Atomy explained",
                "ethical direct selling",
                *[
                    value.lower()
                    for value in re.findall(r"\b[A-Za-z][A-Za-z -]{3,24}\b", title)[:5]
                ],
            ]
        )
    )[:30]
    chapter_indexes = sorted({0, len(storyboard.scenes) // 4, len(storyboard.scenes) // 2, len(storyboard.scenes) * 3 // 4})
    chapters: list[str] = []
    elapsed = 0.0
    start_times: list[float] = []
    for scene in storyboard.scenes:
        start_times.append(elapsed)
        elapsed += scene.duration_seconds
    for index in chapter_indexes:
        if index >= len(storyboard.scenes):
            continue
        scene = storyboard.scenes[index]
        label_words = re.findall(r"[A-Za-z0-9'-]+", scene.narration)[:7]
        chapters.append(f"{_chapter_time(start_times[index])} {' '.join(label_words).rstrip('.,:;')}")
    summary = textwrap.shorten(script.body[0], width=480, placeholder="…")
    sources = ""
    if script.source_urls:
        sources = "\n\nOFFICIAL SOURCES\n" + "\n".join(
            f"- {url}" for url in script.source_urls
        )
    description = (
        f"{summary}\n\n"
        "In this educational breakdown, we separate useful business and lifestyle principles "
        "from hype, then look at Atomy as one possible option—not a guaranteed shortcut.\n\n"
        f"{settings.channel.disclosure}\n\n"
        "CHAPTERS\n" + "\n".join(chapters) + sources + "\n\n"
        "#OnlineBusiness #SideHustle #BusinessMindset"
    )
    thumbnail_text = " ".join(re.findall(r"[A-Za-z0-9]+", title)[:6]).upper()
    return VideoMetadata(
        title=title,
        description=description[:5000],
        tags=tags,
        hashtags=["#OnlineBusiness", "#SideHustle", "#BusinessMindset"],
        chapters=chapters,
        thumbnail_text=thumbnail_text[:70],
        category_id=settings.publishing.category_id,
    )


def build_thumbnail(background: Path, metadata: VideoMetadata, output: Path) -> Path:
    with Image.open(background) as source:
        image = source.convert("RGB")
    ratio = max(1280 / image.width, 720 / image.height)
    image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = (image.width - 1280) // 2
    top = (image.height - 720) // 2
    image = image.crop((left, top, left + 1280, top + 720))
    image = ImageEnhance.Contrast(image).enhance(1.12)
    blurred = image.filter(ImageFilter.GaussianBlur(1.2))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.polygon([(0, 0), (850, 0), (700, 720), (0, 720)], fill=(8, 11, 17, 218))
    draw.rectangle((68, 76, 82, 644), fill=(255, 190, 58, 255))
    draw.text((116, 78), "A BETTER WAY TO THINK", font=_font(30, True), fill=(255, 198, 70, 255))
    wrapped = "\n".join(textwrap.wrap(metadata.thumbnail_text, width=15)[:4])
    draw.multiline_text(
        (112, 165),
        wrapped,
        font=_font(78, True),
        fill=(255, 255, 255, 255),
        spacing=3,
        stroke_width=2,
        stroke_fill=(8, 11, 17, 255),
    )
    result = Image.alpha_composite(blurred.convert("RGBA"), overlay).convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="JPEG", quality=94, optimize=True)
    return output

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .config import Settings
from .models import ScriptDocument, Storyboard, VideoMetadata

BRAND_LOGO = Path("assets/biznex/biznex-logo-mark-v2.png")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    choices = [
        Path("assets/fonts/BarlowCondensed-Black.ttf" if bold else "assets/fonts/Barlow-Regular.ttf"),
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


def _thumbnail_copy(script: ScriptDocument, title: str) -> tuple[str, list[str]]:
    supplied = [
        re.sub(r"\s+", " ", value).strip().upper()
        for value in script.thumbnail_text_options
        if value.strip()
    ]
    supplied = list(dict.fromkeys(supplied))[:3]
    if supplied:
        return supplied[0][:28], supplied

    lower = title.casefold()
    if "join" in lower or "registration" in lower:
        fallback = "BEFORE YOU JOIN"
    elif "compensation" in lower or "business" in lower:
        fallback = "HOW IT REALLY WORKS"
    elif "review" in lower or "product" in lower:
        fallback = "WORTH YOUR MONEY?"
    else:
        fallback = "WHAT TO KNOW"
    return fallback, [fallback]


def build_metadata(
    script: ScriptDocument, storyboard: Storyboard, settings: Settings
) -> VideoMetadata:
    title = script.title[:100].rstrip(" -:,.!")
    title_variants = list(
        dict.fromkeys(
            candidate[:100].rstrip(" -:,.!")
            for candidate in [title, *script.title_variants]
            if candidate.strip()
        )
    )[:3]
    brand = settings.channel.brand_name.strip()
    topic_tags = [value.lower().strip() for value in settings.research.seed_topics]
    tags = list(
        dict.fromkeys(
            [
                *topic_tags,
                f"{brand} explained" if brand else "educational explainer",
                f"{brand} consumer" if brand else "consumer guide",
                f"{brand} distributor" if brand else "distributor guide",
                f"before joining {brand}" if brand else "before joining a business",
                "network marketing explained",
            ]
        )
    )[:30]
    requested_chapters = len(script.chapter_titles) if script.chapter_titles else 4
    chapter_count = min(len(storyboard.scenes), max(4, requested_chapters))
    chapter_indexes = (
        sorted(
            {
                round(number * (len(storyboard.scenes) - 1) / max(1, chapter_count - 1))
                for number in range(chapter_count)
            }
        )
        if storyboard.scenes
        else []
    )
    chapters: list[str] = []
    elapsed = 0.0
    start_times: list[float] = []
    for scene in storyboard.scenes:
        start_times.append(elapsed)
        elapsed += scene.duration_seconds
    for chapter_number, index in enumerate(chapter_indexes):
        if index >= len(storyboard.scenes):
            continue
        scene = storyboard.scenes[index]
        if chapter_number < len(script.chapter_titles):
            label = script.chapter_titles[chapter_number]
        else:
            label_words = re.findall(r"[A-Za-z0-9'-]+", scene.narration)[:7]
            label = " ".join(label_words).rstrip(".,:;")
        chapters.append(
            f"{_chapter_time(start_times[index])} {label}"
        )
    summary = script.description_summary or textwrap.shorten(
        script.body[0], width=480, placeholder="…"
    )
    sources = ""
    if script.source_urls:
        sources = "\n\nOFFICIAL SOURCES\n" + "\n".join(f"- {url}" for url in script.source_urls)
    framing = (
        f"We separate useful principles from hype, then evaluate {brand} as one possible option "
        "with honest tradeoffs."
        if settings.channel.brand_required and brand
        else settings.channel.content_goal
    )
    search_context = " ".join(settings.research.seed_topics).casefold()
    if brand and any(term in search_context for term in {"business plan", "compensation plan"}):
        hashtags = [
            f"#{re.sub(r'[^A-Za-z0-9]', '', brand)}",
            f"#{re.sub(r'[^A-Za-z0-9]', '', brand)}Business",
            "#CompensationPlan",
        ]
    elif brand:
        hashtags = [
            f"#{re.sub(r'[^A-Za-z0-9]', '', brand)}",
            f"#{re.sub(r'[^A-Za-z0-9]', '', brand)}USA",
            "#NetworkMarketing",
        ]
    else:
        hashtags = ["#Explainer"]
    description = (
        f"{summary}\n\n{framing}\n\n{settings.channel.disclosure}\n\n"
        "CHAPTERS\n" + "\n".join(chapters) + sources + "\n\n" + " ".join(hashtags)
    )
    thumbnail_text, thumbnail_variants = _thumbnail_copy(script, title)
    return VideoMetadata(
        title=title,
        title_variants=title_variants,
        description=description[:5000],
        tags=tags,
        hashtags=hashtags,
        chapters=chapters,
        thumbnail_text=thumbnail_text,
        thumbnail_variants=thumbnail_variants,
        packaging_hypothesis=script.packaging_hypothesis,
        category_id=settings.publishing.category_id,
    )


def build_thumbnail(background: Path, metadata: VideoMetadata, output: Path) -> Path:
    with Image.open(background) as source:
        image = source.convert("RGB")
    ratio = max(1280 / image.width, 720 / image.height)
    image = image.resize(
        (round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS
    )
    left = (image.width - 1280) // 2
    top = (image.height - 720) // 2
    image = image.crop((left, top, left + 1280, top + 720))
    image = ImageEnhance.Contrast(image).enhance(1.14)
    blurred = image.filter(ImageFilter.GaussianBlur(0.65))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.polygon([(0, 0), (900, 0), (748, 720), (0, 720)], fill=(8, 9, 8, 232))
    draw.polygon([(0, 0), (58, 0), (0, 720)], fill=(225, 181, 92, 255))
    draw.text((78, 72), "ATOMY  •  EXPLAINED", font=_font(28, True), fill=(225, 181, 92, 255))
    wrapped = "\n".join(textwrap.wrap(metadata.thumbnail_text, width=12)[:3])
    draw.multiline_text(
        (74, 154),
        wrapped,
        font=_font(94, True),
        fill=(246, 241, 229, 255),
        spacing=-3,
        stroke_width=3,
        stroke_fill=(8, 9, 8, 255),
    )
    draw.rectangle((78, 595, 612, 600), fill=(225, 181, 92, 230))
    draw.text(
        (78, 620),
        "FACTS  •  TRADE-OFFS  •  NO HYPE",
        font=_font(23, True),
        fill=(246, 241, 229, 220),
    )
    result = Image.alpha_composite(blurred.convert("RGBA"), overlay).convert("RGB")
    if BRAND_LOGO.exists():
        with Image.open(BRAND_LOGO) as source:
            logo = source.convert("RGBA")
        logo.thumbnail((126, 126), Image.Resampling.LANCZOS)
        result_rgba = result.convert("RGBA")
        result_rgba.alpha_composite(logo, (1125, 565))
        result = result_rgba.convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="JPEG", quality=94, optimize=True)
    return output

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "biznex"
FONT_ROOT = ROOT / "assets" / "fonts"
GOLD = (223, 180, 92)
IVORY = (246, 241, 229)
INK = (10, 10, 9)


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_ROOT / filename), size=size)


def _cover(source: Image.Image, width: int, height: int) -> Image.Image:
    ratio = max(width / source.width, height / source.height)
    resized = source.resize(
        (round(source.width * ratio), round(source.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _contain(source: Image.Image, width: int, height: int) -> Image.Image:
    copy = source.copy()
    copy.thumbnail((width, height), Image.Resampling.LANCZOS)
    return copy


def build_avatar(mark_path: Path, output: Path) -> Path:
    mark = Image.open(mark_path).convert("RGBA")
    canvas = Image.new("RGBA", (800, 800), (*INK, 255))
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow, "RGBA")
    glow_draw.ellipse((95, 95, 705, 705), fill=(*GOLD, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(85))
    canvas = Image.alpha_composite(canvas, glow)
    fitted = _contain(mark, 660, 660)
    canvas.alpha_composite(
        fitted,
        ((canvas.width - fitted.width) // 2, (canvas.height - fitted.height) // 2),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=96, optimize=True)
    return output


def build_banner(background_path: Path, mark_path: Path, output: Path) -> Path:
    background = _cover(Image.open(background_path).convert("RGB"), 2560, 1440)
    background = ImageEnhance.Contrast(background).enhance(1.07)
    canvas = background.convert("RGBA")

    # YouTube's cross-device safe region is 1546 x 423, centered in the master.
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade, "RGBA")
    shade_draw.rounded_rectangle(
        (515, 505, 2045, 935),
        radius=30,
        fill=(7, 7, 6, 168),
        outline=(*GOLD, 58),
        width=2,
    )
    shade = shade.filter(ImageFilter.GaussianBlur(0.4))
    canvas = Image.alpha_composite(canvas, shade)

    mark = _contain(Image.open(mark_path).convert("RGBA"), 300, 300)
    canvas.alpha_composite(mark, (615, 570))

    draw = ImageDraw.Draw(canvas, "RGBA")
    wordmark_font = _font("BarlowCondensed-Black.ttf", 164)
    eyebrow_font = _font("Barlow-Regular.ttf", 28)
    tagline_font = _font("Barlow-Regular.ttf", 38)
    x = 965
    draw.text((x, 548), "BIZNEX", font=wordmark_font, fill=IVORY)
    draw.rectangle((x + 4, 731, x + 655, 736), fill=(*GOLD, 230))
    draw.text(
        (x + 4, 758),
        "ATOMY  •  BUSINESS  •  BUILT WITH AI",
        font=tagline_font,
        fill=GOLD,
    )
    draw.text(
        (x + 6, 821),
        "WE RESEARCH. TEST. MEASURE. IMPROVE.",
        font=eyebrow_font,
        fill=(*IVORY, 184),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=96, optimize=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic BizNex channel assets")
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    args = parser.parse_args()
    root = args.asset_root.resolve()
    mark = root / "biznex-logo-mark-v2.png"
    background = root / "biznex-banner-background-v2.png"
    build_avatar(mark, root / "biznex-youtube-avatar-v2.jpg")
    build_banner(background, mark, root / "biznex-youtube-banner-v2.jpg")


if __name__ == "__main__":
    main()

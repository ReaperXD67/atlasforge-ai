"""Render an 11-second native motion proof from the actual edit and lyric clock.

This is a quick FFmpeg/ASS preview, not a claim of pixel parity with the browser
render. Production edit, captions, source timing and media files are read only.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / "output/bosston-revision/preview"
LENGTH = 11.0
FPS = 30


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2500:])
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ass_time(t):
    centiseconds = round(t * 100)
    hours, centiseconds = divmod(centiseconds, 360000)
    minutes, centiseconds = divmod(centiseconds, 6000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def audio(path):
    raw = run(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-t",
        str(LENGTH),
        "-map",
        "0:a:0",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-f",
        "f32le",
        "-",
    )
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fonts = OUT / "fonts"
    fonts.mkdir(exist_ok=True)
    font_source = ROOT / "assets/fonts/NotoSerifCJKsc-Regular.otf"
    font_target = fonts / font_source.name
    if not font_target.exists():
        try:
            os.link(font_source, font_target)
        except OSError:
            shutil.copy2(font_source, font_target)
    plan_path, captions_path = ROOT / "scene-plan.json", ROOT / "captions.json"
    source_hashes = {"scene-plan.json": sha(plan_path), "captions.json": sha(captions_path)}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cues = json.loads(captions_path.read_text(encoding="utf-8"))
    selected = [s for s in plan if s["start"] < LENGTH]
    assert all(s["media"] == "video" for s in selected)
    assert all("Boston" not in c["text"] for c in cues)
    subtitle = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Lyric,Noto Serif CJK SC,49,&H00E4F5FF,&H00E4F5FF,&H90000000,&HC0000000,0,0,0,0,100,100,2.2,0,1,2,1.5,5,190,190,0,1",
        "Style: Title,Noto Serif CJK SC,140,&H00A9E2FF,&H00A9E2FF,&H90000000,&HC0000000,0,0,0,0,100,100,25.2,0,1,2,3,5,220,220,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        r"Dialogue: 0,0:00:00.35,0:00:04.50,Title,,0,0,0,,{\an5\pos(960,461)\fad(650,600)\blur1.2}好运来",
    ]
    for cue in cues:
        if cue["start"] >= LENGTH:
            continue
        subtitle.append(
            f"Dialogue: 1,{ass_time(cue['start'])},{ass_time(min(LENGTH, cue['end']))},Lyric,,0,0,0,,"
            + r"{\an5\pos(960,899)\fad(100,130)\blur0.7}"
            + cue["text"]
        )
    (OUT / "preview.ass").write_text("\n".join(subtitle) + "\n", encoding="utf-8-sig")
    veil = np.zeros((1080, 1920, 4), dtype=np.uint8)
    veil[:, :, :3] = (2, 4, 5)
    for y in range(650, 1004):
        p = (y - 650) / 354
        veil[y, :, 3] = round(36 * p / 0.35 if p < 0.35 else 36 + (207 - 36) * (p - 0.35) / 0.65)
    Image.fromarray(veil).save(OUT / "veil.png")
    encoder = imageio_ffmpeg.get_ffmpeg_exe()
    command = [encoder, "-y", "-hide_banner", "-v", "warning"]
    filters, shots = [], []
    for index, shot in enumerate(selected):
        end = min(LENGTH, shot["end"])
        frames = round(end * FPS) - round(shot["start"] * FPS)
        command += ["-ss", str(shot["source_at"]), "-threads", "2", "-i", str(ROOT / shot["src"])]
        filters.append(
            f"[{index}:v]setpts=(PTS-STARTPTS)/{shot['rate']},fps=30,trim=end_frame={frames},setpts=PTS-STARTPTS,crop=1920:928:0:76,pad=1920:1080:0:76:color=0x020305,setsar=1[v{index}]"
        )
        shots.append({k: shot[k] for k in ["id", "start", "end", "src", "rate", "source_at"]})
    logo_index = len(selected)
    command += [
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(ROOT / "assets/generated/bosston-pragon.png"),
    ]
    veil_index = logo_index + 1
    command += ["-loop", "1", "-framerate", "30", "-i", "veil.png"]
    audio_index = veil_index + 1
    command += ["-i", str(ROOT / "assets/bgm.wav")]
    filters += [
        "".join(f"[v{i}]" for i in range(len(selected)))
        + f"concat=n={len(selected)}:v=1:a=0[base]",
        f"[{logo_index}:v]scale=570:190,format=rgba,fade=t=in:st=0:d=0.9:alpha=1[logo]",
        f"[base][{veil_index}:v]overlay=0:0:shortest=1[shaded]",
        "[shaded][logo]overlay=84:60:shortest=1,ass=preview.ass:fontsdir=fonts,fade=t=in:st=0:d=0.55,format=yuv420p[out]",
    ]
    target = OUT / "Bosston-Pragon-Cinematic-Preview.mp4"
    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[out]",
        "-map",
        f"{audio_index}:a:0",
        "-t",
        str(LENGTH),
        "-frames:v",
        "330",
        "-r",
        "30",
        "-fps_mode",
        "cfr",
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p5",
        "-rc",
        "vbr",
        "-cq",
        "18",
        "-b:v",
        "8M",
        "-maxrate",
        "12M",
        "-bufsize",
        "24M",
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(target),
    ]
    run(*command, cwd=OUT)
    metadata = json.loads(
        run("ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(target))
    )
    picture = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (
        picture["width"],
        picture["height"],
        picture["avg_frame_rate"],
        int(picture["nb_frames"]),
    ) == (1920, 1080, "30/1", 330)
    assert abs(float(metadata["format"]["duration"]) - LENGTH) < 0.04
    run("ffmpeg", "-v", "error", "-xerror", "-i", str(target), "-f", "null", "-")
    original, encoded = audio(ROOT / "assets/bgm.wav"), audio(target)
    count = min(len(original), len(encoded))
    correlations = [
        float(np.corrcoef(original[:count, i], encoded[:count, i])[0, 1]) for i in (0, 1)
    ]
    assert min(correlations) > 0.98
    times = [0.8, 2.7, 3.9, 5.2, 6.9, 8.6, 9.2, 10.6]
    contact = Image.new("RGB", (1536, 4 * 470), (9, 9, 13))
    draw = ImageDraw.Draw(contact)
    for i, t in enumerate(times):
        raw = run(
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(t),
            "-i",
            str(target),
            "-frames:v",
            "1",
            "-vf",
            "scale=768:432",
            "-f",
            "image2pipe",
            "-c:v",
            "png",
            "-",
        )
        still = Image.open(io.BytesIO(raw)).convert("RGB")
        still.save(OUT / f"proof-{i + 1:02d}.jpg", quality=94)
        x, y = i % 2 * 768, i // 2 * 470
        contact.paste(still, (x, y))
        draw.text(
            (x + 8, y + 439),
            f"{t:.3f}s | actual moving source / corrected lyric spelling",
            fill="white",
        )
    contact.save(OUT / "Motion-Proof.jpg", quality=94, subsampling=0)
    assert source_hashes == {"scene-plan.json": sha(plan_path), "captions.json": sha(captions_path)}
    report = {
        "passed": True,
        "duration": LENGTH,
        "frames": 330,
        "width": 1920,
        "height": 1080,
        "fps": FPS,
        "full_decode": True,
        "audio_offset_samples": 0,
        "audio_per_channel_correlation": correlations,
        "audio_compared_samples_per_channel": count,
        "sha256": sha(target),
        "size_bytes": target.stat().st_size,
        "source_hashes": source_hashes,
        "shots": shots,
        "preview_method": "FFmpeg native excerpt of actual edit with ASS typography; not pixel-identical to final browser render",
    }
    (OUT / "preview-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"video": str(target), "verification": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

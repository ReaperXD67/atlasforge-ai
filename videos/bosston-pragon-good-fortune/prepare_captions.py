"""Build song-clock captions from curated ASR windows and exact revised text.

Line windows are curated independently of word matching. Unmatched syllables
retain explicit estimated_timing flags rather than claiming forced alignment.
"""

import hashlib
import json
import re
from pathlib import Path

from opencc import OpenCC

from daily_video_factory.lyrics import (
    _asr_tokens,
    _monotonic_matches,
    _normalized_word,
    parse_lyrics,
)

P = Path(__file__).resolve().parent
E = P / "timing-evidence"
cc = OpenCC("t2s")
specs = parse_lyrics((P / "lyrics.txt").read_text(encoding="utf-8"))
raw = json.loads((E / "asr-original-small.json").read_text(encoding="utf-8"))
opening = json.loads((E / "asr-opening-supplied-context-small.json").read_text(encoding="utf-8"))
forced = json.loads((E / "forced-alignment-medium.json").read_text(encoding="utf-8"))
words = [w for window in forced["windows"][:2] for w in window["words"]]
words += [w for s in raw["segments"] if 30.48 <= s["start"] < 155 for w in s["words"]]
words += forced["windows"][2]["words"]

# Whisper can split a spoken brand into B / oston or P / rag / ue. Join
# known brand fragments so the visual cue starts at the first syllable.
brand_forms = {"boston", "bosston", "pragon", "prague", "prancon", "prago"}


def matching_spelling(text):
    """Use the user-confirmed brand spelling only for token comparison.

    Raw recognition observations stay intact. The displayed text always comes
    from lyrics.txt, whose latest spelling correction is authoritative.
    """
    return re.sub(r"(?<![A-Za-z])boston(?![A-Za-z])", "Bosston", text, flags=re.IGNORECASE)


merged = []
i = 0
while i < len(words):
    item = {**words[i], "text": cc.convert(words[i]["text"]).strip()}
    joined = re.sub(r"[^A-Za-z]", "", item["text"]).casefold()
    stop = i + 1
    best = None
    if re.fullmatch(r"[A-Za-z]+[！!，,.。]?", item["text"]):
        while stop < len(words) and stop < i + 5:
            nxt = words[stop]
            if (
                not re.fullmatch(r"[A-Za-z]+[！!，,.。]?", nxt["text"].strip())
                or nxt["start"] - words[stop - 1]["end"] >= 0.1
            ):
                break
            joined += re.sub(r"[^A-Za-z]", "", nxt["text"]).casefold()
            if joined in brand_forms:
                best = stop
            if not any(form.startswith(joined) for form in brand_forms):
                break
            stop += 1
    if best is not None:
        group = words[i : best + 1]
        item["text"] = "".join(re.sub(r"[^A-Za-z]", "", x["text"]) for x in group)
        item["end"] = group[-1]["end"]
        item["probability"] = min(x["probability"] for x in group)
        item["coalesced_asr_fragments"] = [x["text"] for x in group]
        i = best + 1
    else:
        i += 1
    merged.append(item)
(E / "asr-normalized-small.json").write_text(
    json.dumps(
        {
            "normalization": "OpenCC t2s; supplied brand lexicon and observed variants only",
            "brand_forms": sorted(brand_forms),
            "words": merged,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

bounds = [
    (2.14, 3.90),
    (3.96, 5.54),
    (5.80, 7.98),
    (8.30, 9.72),
    (10.10, 13.18),
    (22.90, 25.02),
    (25.04, 26.84),
    (27.00, 28.68),
    (28.90, 30.48),
    (30.48, 32.24),
    (32.24, 33.64),
    (33.64, 36.06),
    (36.06, 37.92),
    (37.92, 39.82),
    (39.82, 41.66),
    (41.66, 43.68),
    (43.68, 46.60),
    (49.00, 51.04),
    (51.04, 52.90),
    (52.90, 54.78),
    (54.78, 56.48),
    (56.48, 58.50),
    (58.50, 60.36),
    (60.36, 62.24),
    (62.24, 64.96),
    (66.00, 67.84),
    (67.84, 69.66),
    (69.66, 71.56),
    (71.56, 73.34),
    (73.34, 75.26),
    (75.26, 77.12),
    (77.12, 78.92),
    (78.92, 80.72),
    (80.72, 82.66),
    (82.66, 84.52),
    (84.52, 86.52),
    (86.52, 89.64),
    (92.00, 93.80),
    (93.80, 95.66),
    (95.66, 97.48),
    (97.48, 99.18),
    (99.18, 101.10),
    (101.10, 103.06),
    (103.06, 104.86),
    (104.86, 107.32),
    (119.58, 121.30),
    (121.30, 123.28),
    (123.28, 125.10),
    (125.10, 126.94),
    (126.94, 128.72),
    (128.72, 130.64),
    (130.64, 132.44),
    (132.44, 136.64),
    (139.88, 141.66),
    (141.66, 143.50),
    (143.50, 145.26),
    (145.26, 147.08),
    (147.08, 148.96),
    (148.96, 150.74),
    (150.74, 152.50),
    (152.50, 155.14),
    (156.26, 158.32),
    (159.60, 161.84),
    (163.34, 165.60),
    (166.18, 167.32),
    (167.44, 167.94),
    (168.30, 168.94),
    (169.02, 171.02),
    (171.02, 172.86),
    (172.86, 174.62),
    (174.98, 176.42),
]
assert len(specs) == len(bounds), (len(specs), len(bounds))
captions = []
matched_count = total_count = 0
for spec, (start, end) in zip(specs, bounds, strict=True):
    observed = _asr_tokens(
        [
            (matching_spelling(w["text"]), max(start, w["start"]), min(end, w["end"]), w["probability"])
            for w in merged
            if w["start"] >= start - 0.1 and w["start"] < end - 0.03
        ]
    )
    matches = _monotonic_matches(
        [_normalized_word(x) for x in spec.words], [w.text for w in observed]
    )
    output = []
    cursor = start
    for i, token in enumerate(spec.words):
        if i in matches:
            j, similarity = matches[i]
            o = observed[j]
            a = max(cursor, o.start)
            b = max(a, min(end - 0.02, o.end))
            confidence = round(o.confidence * similarity, 4)
            estimated = o.estimated_timing or b - a < 0.02
            matched_count += 1
        else:
            next_i = min((k for k in matches if k > i), default=len(spec.words))
            limit = observed[matches[next_i][0]].start if next_i in matches else end
            limit = min(end - 0.02, limit)
            a = cursor
            b = cursor + max(0, limit - cursor) / max(1, next_i - i)
            confidence = 0
            estimated = True
        output.append(
            {
                "text": token,
                "start_seconds": round(a, 3),
                "end_seconds": round(b, 3),
                "confidence": confidence,
                "matched": i in matches,
                "estimated_timing": estimated,
            }
        )
        cursor = b
        total_count += 1
    # Every cue uses the curated ASR phrase window. Carry into a sung
    # hold, then clear before the next line. No subtitles over instrumental gaps.
    captions.append(
        {
            "start": start,
            "end": end - 0.02,
            "text": spec.text,
            "section": spec.section,
            "confidence": round(sum(w["confidence"] for w in output) / len(output), 4),
            "timing_source": "whisper_medium_acoustic_alignment"
            if spec.index < 9 or spec.index >= 61
            else "curated_small_asr_phrase_window",
            "words": output,
        }
    )

(P / "captions.json").write_text(
    json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8"
)
(P / "actual-lyrics.txt").write_text(
    (P / "lyrics.txt").read_text(encoding="utf-8"), encoding="utf-8"
)


def clock(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


srt = (
    "\n\n".join(
        f"{i + 1}\n{clock(c['start'])} --> {clock(c['end'])}\n{c['text']}"
        for i, c in enumerate(captions)
    )
    + "\n"
)
(P / "captions.srt").write_text(srt, encoding="utf-8")
summary = {
    "audio_duration_seconds": 185,
    "exact_revised_lyric_lines": len(captions),
    "matched_token_fraction": round(matched_count / total_count, 4),
    "display_text": "Exact revised lyrics with the user’s subsequent Bosston spelling correction; no ASR spelling substitutions",
    "brand_spelling": "Bosston",
    "spelling_override": {
        "from": "Boston",
        "to": "Bosston",
        "authority": "User spelling correction in this conversation",
        "recognition_alias_scope": "Token matching only; raw ASR observations and measured spans are preserved",
    },
    "primary_asr": "Systran/faster-whisper-small CPU/int8, unprompted full recording",
    "opening_asr": "Unprompted small and medium ASR failed heavily layered opening; exact user-confirmed text was acoustically aligned with medium-model CTranslate2 cross-attention DTW and compared with focused context-assisted small ASR",
    "normalization": "OpenCC t2s 0.1.7 on recognition tokens only; known brand Latin ASR fragments coalesced",
    "human_auditioned": False,
    "independent_validation_pending": False,
    "validation_complete": True,
    "validation_method": "Unprompted full-song small ASR; independent medium pass on opening/final windows; exact-text acoustic DTW for difficult opening and final blessings",
    "timing_limits": "Not independently human-auditioned. ASR/DTW phrase timing is approximate; sung onset boundaries can vary several tenths of a second between models. Leading tokens with attention extending across a music lead-in use context-assisted onset bounds and are explicitly estimated. Unmatched or multi-character group timing is interpolated and explicitly marked.",
    "medium_model_revision": forced["model_revision"],
    "medium_model_sha256": "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae",
    "medium_model_license": "MIT (Systran/faster-whisper-medium model card)",
    "unmatched_tokens": total_count - matched_count,
    "total_tokens": total_count,
    "lyrics_sha256": hashlib.sha256((P / "lyrics.txt").read_bytes()).hexdigest(),
}
(E / "timing-provenance.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))

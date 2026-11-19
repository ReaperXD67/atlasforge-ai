"""Verify V3 native-cadence picture, recipient coverage and original soundtrack."""
from __future__ import annotations

import argparse
import math
import re
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from prepare_film import read_json, write_json
from prepare_film_v3 import FPS, OUTPUT, ROOT, load_clips, validate_plan
from verify_film import (
    audio_payload,
    frame,
    luma_similarity,
    normalize,
    probe,
    require,
    run,
    sha256,
    stereo,
)


def lyrics_check(cues):
    supplied = [x.strip() for x in (ROOT / 'lyrics.txt').read_text(encoding='utf-8').splitlines()
                if x.strip() and not re.fullmatch(r'\[.*\]|【.*】', x.strip())]
    require(len(cues) == len(supplied) == 40, 'Expected all40 canonical sung lines.')
    require(normalize(''.join(supplied)) == normalize(''.join(c['text'] for c in cues)), 'V3 caption text changed.')
    events = []
    for line in (ROOT / 'film-v3.ass').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('Dialogue:'):
            fields = line.split(',', 9)
            if fields[3] in {'Lyrics', 'Chorus'}:
                events.append(re.sub(r'\{.*?\}', '', fields[9]).replace('\\N', '\n'))
    require(events == [c['text'] for c in cues], 'V3 rendered lyrics differ from canonical cues.')
    return {'caption_cues': 40, 'canonical_text': 'passed', 'rendered_ass': 'passed'}


def picture_binding(video, plan):
    candidates = [s for s in plan['shots'] if (s['start_frame'] + s['end_frame']) / (2 * FPS) > 7
                  and s['end_frame'] / FPS < plan['closing_start']]
    indices = sorted({round(i * (len(candidates) - 1) / 8) for i in range(9)})
    samples = []
    for index in indices:
        shot = candidates[index]
        number = (shot['start_frame'] + shot['end_frame']) // 2
        at = number / FPS
        expected = frame(OUTPUT / 'segments' / f'{shot["id"]}.mkv',
                         (number - shot['start_frame']) / FPS, (210, 230, 1500, 530))
        actual = frame(video, at, (210, 230, 1500, 530))
        error = float(np.abs(np.asarray(actual, dtype=np.float32) - np.asarray(expected, dtype=np.float32)).mean())
        similarity = luma_similarity(actual, expected)
        require(error < 5 and similarity > .97, f'V3 encoded source mismatch at {shot["id"]}.')
        samples.append({'shot': shot['id'], 'frame': number, 'rgb_mae': round(error, 6), 'luma_ssim': round(similarity, 6)})
    return {'passed': True, 'samples': samples, 'source_stage': 'lossless FFV1',
            'limits': 'Sampled correspondence, not proof of every-frame likeness or quality.'}


def contact_sheets(video, plan, cues):
    directory = OUTPUT / 'review'
    directory.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(ROOT / 'assets/fonts/NotoSerifCJKsc-Regular.otf'), 18)
    pages = []
    for offset in range(0, len(plan['shots']), 16):
        shots = plan['shots'][offset:offset + 16]
        board = Image.new('RGB', (1920, 46 + math.ceil(len(shots) / 4) * 325), '#101116')
        draw = ImageDraw.Draw(board)
        draw.text((14, 8), f'Hock Siew V3 — actual encoded frames — {offset + 1}–{offset + len(shots)}', font=font, fill='#f6d38a')
        for slot, shot in enumerate(shots):
            at = ((shot['start_frame'] + shot['end_frame']) // 2) / FPS
            still = frame(video, at).resize((480, 270), Image.Resampling.LANCZOS)
            x, y = slot % 4 * 480, 46 + slot // 4 * 325
            board.paste(still, (x, y))
            draw.text((x + 8, y + 273), f'{shot["id"]} {at:.3f}s', font=font, fill='#f6d38a')
            text = next((c['text'] for c in cues if c['start'] <= at < c['end']), '[instrumental / dedication]')
            draw.text((x + 8, y + 298), text, font=font, fill='white')
        output = directory / f'contact-sheet-{len(pages) + 1:02}.jpg'
        board.save(output, quality=93, subsampling=0)
        pages.append(output.relative_to(ROOT).as_posix())
    names = [c for c in cues if any(n in c['text'] for n in ('Hock Siew', '谢惠福'))]
    proof = Image.new('RGB', (1920, math.ceil(len(names) / 2) * 600 + 50), '#101116')
    draw = ImageDraw.Draw(proof)
    for index, cue in enumerate(names):
        at = math.floor((cue['start'] + cue['end']) / 2 * FPS) / FPS
        x, y = index % 2 * 960, 50 + index // 2 * 600
        actual = frame(video, at)
        proof.paste(actual.resize((960, 540), Image.Resampling.LANCZOS), (x, y))
        # Full portrait visibility matters at name anchors; store separate full frames.
        actual.save(directory / f'name-anchor-{index + 1:02}.png')
        draw.text((x + 15, y + 545), f'{at:.3f}s {cue["text"]}', font=font, fill='#f6d38a')
    proof.save(directory / 'name-identity-anchors.jpg', quality=94, subsampling=0)
    # Individual full-resolution name-anchor frames are the authoritative proofs.
    frame(video, 2.5).save(directory / 'opening-identity.png')
    frame(video, plan['duration_seconds'] - 4).save(directory / 'closing-dedication.png')
    cropped = [s for s in plan['shots'] if s['kind'] == 'native' and s.get('crop')]
    for offset in range(0, len(cropped), 8):
        shots = cropped[offset:offset + 8]
        board = Image.new('RGB', (1920, len(shots) * 390 + 40), '#101116')
        draw = ImageDraw.Draw(board)
        for row, shot in enumerate(shots):
            for column, number in enumerate((shot['start_frame'],
                                             (shot['start_frame'] + shot['end_frame']) // 2,
                                             shot['end_frame'] - 1)):
                still = frame(video, number / FPS)
                board.paste(still.resize((640, 360), Image.Resampling.LANCZOS),
                            (column * 640, 40 + row * 390))
                draw.text((column * 640 + 8, 40 + row * 390 + 363),
                          f'{shot["id"]} {number / FPS:.3f}s', font=font, fill='#f6d38a')
        board.save(directory / f'context-edges-{offset // 8 + 1:02}.jpg', quality=94, subsampling=0)
    return {'shot_midpoint_sheets': pages, 'sampled_shots': len(plan['shots']), 'full_name_anchors': len(names),
            'cropped_context_shots_with_first_middle_last_frames': len(cropped),
            'review_status': 'pending visual inspection of actual encoded frames'}


def verify(video, make_sheets=False):
    plan = read_json(ROOT / 'edit-plan-v3.json')
    cues = read_json(ROOT / 'captions.json')
    clips = load_clips()
    original = ROOT / 'assets/bgm.wav'
    duration = float(probe(original)['format']['duration'])
    coverage = validate_plan(plan, clips, cues, duration)
    meta = probe(video)
    v = next(s for s in meta['streams'] if s.get('codec_type') == 'video')
    a = next(s for s in meta['streams'] if s.get('codec_type') == 'audio')
    require((v['width'], v['height']) == (1920, 1080) and Fraction(v['avg_frame_rate']) == FPS
            and v['codec_name'] == 'h264' and v['pix_fmt'] == 'yuv420p', 'Wrong V3 video format.')
    require(a['codec_name'] == 'aac' and a['channels'] == 2 and int(a['sample_rate']) == 48000, 'Wrong V3 soundtrack.')
    require(float(v.get('start_time', 0)) == float(a.get('start_time', 0)) == 0, 'V3 does not begin at zero.')
    require(abs(float(meta['format']['duration']) - duration) <= 1 / FPS, 'V3 song coverage differs.')
    progress = run(['ffmpeg', '-v', 'error', '-xerror', '-i', video, '-progress', 'pipe:1', '-nostats', '-f', 'null', '-']).decode()
    frames = re.findall(r'^frame=(\d+)$', progress, flags=re.M)
    require(frames and int(frames[-1]) == plan['frames'] and 'progress=end' in progress, 'V3 full decode failed.')
    x, y = stereo(original), stereo(video)
    require(abs(len(x) - len(y)) <= 1024, 'V3 audio sample count changed.')
    count = min(len(x), len(y))
    correlations = [float(np.corrcoef(x[:count, i], y[:count, i])[0, 1]) for i in range(2)]
    gains = [20 * math.log10(float(np.dot(x[:count, i].astype(float), y[:count, i].astype(float))
                                 / np.dot(x[:count, i].astype(float), x[:count, i].astype(float)))) for i in range(2)]
    require(all(c > .98 for c in correlations) and all(abs(g) < .15 for g in gains), 'V3 original-song correlation/gain failed.')
    result = {'passed': True, 'verified_at_utc': datetime.now(UTC).isoformat(), 'video': video.relative_to(ROOT).as_posix(),
              'video_sha256': sha256(video), 'size_bytes': video.stat().st_size, 'fps': FPS, 'frames': plan['frames'],
              'duration_seconds': float(meta['format']['duration']), 'audio_master_seconds': duration, 'full_decode': True,
              'lyrics': lyrics_check(cues), 'identity_coverage': coverage,
              'used_native_source_count': len({s['clip'] for s in plan['shots'] if s['kind'] == 'native'}),
              'used_native_sources': sorted({s['clip'] for s in plan['shots'] if s['kind'] == 'native'}),
              'picture_binding': picture_binding(video, plan),
              'audio': {'offset_samples': 0, 'per_channel_correlation': correlations, 'gain_db': gains,
                        'encoded_aac_sha256': audio_payload(video)},
              'source_hashes': {p.relative_to(ROOT).as_posix(): sha256(p) for p in ROOT.glob('*')
                                if p.is_file() and p.suffix in {'.py', '.json', '.ass', '.txt'}}}
    sharing = video.with_name(video.stem + '-720p.mp4')
    if sharing.exists():
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', sharing, '-f', 'null', '-'])
        sv = next(s for s in probe(sharing)['streams'] if s.get('codec_type') == 'video')
        require((sv['width'], sv['height']) == (1280, 720) and int(sv['nb_frames']) == plan['frames'], 'Wrong V3 sharing format.')
        require(audio_payload(sharing) == result['audio']['encoded_aac_sha256'], 'V3 sharing audio changed.')
        result['sharing_copy'] = {'path': sharing.relative_to(ROOT).as_posix(), 'size_bytes': sharing.stat().st_size,
                                  'sha256': sha256(sharing), 'full_decode': True, 'aac_identical': True}
    if make_sheets:
        result['visual_review'] = contact_sheets(video, plan, cues)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--contact-sheets', action='store_true')
    args = parser.parse_args()
    try:
        receipt = verify(args.video.resolve(), args.contact_sheets)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        receipt = {'passed': False, 'error': str(error)}
    write_json(args.video.with_suffix('.verification.json'), receipt)
    print({k: receipt.get(k) for k in ('passed', 'error', 'frames', 'audio')})
    raise SystemExit(0 if receipt['passed'] else 1)

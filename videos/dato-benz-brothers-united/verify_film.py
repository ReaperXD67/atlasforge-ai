"""Verify the encoded tribute, its original soundtrack and exact local edit."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import unicodedata
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FPS = 30
SAMPLE_RATE = 48000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, timeout=900):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-2500:])
    return result.stdout


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text)
                   if not c.isspace() and unicodedata.category(c)[0] not in {'P', 'Z'})


def lyrics_check(cues, duration):
    supplied = [line.strip() for line in (ROOT / 'lyrics.txt').read_text(encoding='utf-8').splitlines()
                if line.strip() and not re.fullmatch(r'\[.*\]|【.*】', line.strip())]
    require(len(cues) == len(supplied) and bool(cues), 'Expected every supplied sung line.')
    require(normalize(''.join(supplied)) == normalize(''.join(c['text'] for c in cues)),
            'Caption text differs from the exact supplied lyrics.')
    previous = 0
    for cue in cues:
        require(previous <= cue['start'] < cue['end'] <= duration, 'Cue order/bounds changed.')
        previous = cue['end']
    ass_lines = []
    for line in (ROOT / 'film.ass').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('Dialogue:'):
            fields = line.split(',', 9)
            if fields[3] in {'Lyrics', 'Chorus'}:
                ass_lines.append(re.sub(r'\{.*?\}', '', fields[9]).replace('\\N', '\n'))
    require(ass_lines == [c['text'] for c in cues], 'Rendered ASS lyric events differ from measured cues.')
    return {'supplied_lines': len(supplied), 'caption_cues': len(cues),
            'text_completeness': 'passed', 'cue_order_bounds': 'passed', 'rendered_ass_text': 'passed',
            'timing_limits': 'Model-derived vocal alignment; encoded crops and listening remain separate review.'}


def stereo(path):
    raw = run(['ffmpeg', '-v', 'error', '-xerror', '-i', path, '-map', '0:a:0', '-vn', '-ac', '2',
               '-ar', str(SAMPLE_RATE), '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').reshape((-1, 2))


def audio_payload(path):
    return hashlib.sha256(run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0',
                               '-c:a', 'copy', '-f', 'adts', '-'])).hexdigest()


def frame(path, at, crop=None):
    filters = []
    if crop:
        x, y, width, height = crop
        filters.append(f'crop={width}:{height}:{x}:{y}')
    command = ['ffmpeg', '-v', 'error', '-ss', f'{at:.9f}', '-i', path, '-frames:v', '1']
    if filters:
        command += ['-vf', ','.join(filters)]
    raw = run([*command, '-f', 'image2pipe', '-c:v', 'png', '-'])
    return Image.open(io.BytesIO(raw)).convert('RGB')


def luma_similarity(a, b):
    weights = np.array([.2126, .7152, .0722], dtype=np.float32)
    x = np.asarray(a, dtype=np.float32) @ weights
    y = np.asarray(b, dtype=np.float32) @ weights
    covariance = np.mean((x - x.mean()) * (y - y.mean()))
    c1, c2 = (255 * .01) ** 2, (255 * .03) ** 2
    score = ((2 * x.mean() * y.mean() + c1) * (2 * covariance + c2)
             / ((x.mean() ** 2 + y.mean() ** 2 + c1) * (x.var() + y.var() + c2)))
    return float(score)


def picture_binding(video, plan):
    # Opening typography is deliberately rendered above the picture. Compare
    # source-only picture areas after that bookend has completely left.
    native = [s for s in plan['shots'] if s['kind'] == 'native'
              and (s['start_frame'] + s['end_frame']) / (2 * FPS) >= 6]
    require(len(native) >= 3, 'Need native shots beyond the opening for picture correspondence.')
    indices = sorted({round(i * (len(native) - 1) / 8) for i in range(9)})
    samples = []
    for index in indices:
        shot = native[index]
        number = (shot['start_frame'] + shot['end_frame']) // 2
        relative = (number - shot['start_frame']) / FPS
        actual = frame(video, number / FPS, (210, 230, 1500, 530))
        expected = frame(ROOT / 'renders/segments' / f'{shot["id"]}.mp4', relative, (210, 230, 1500, 530))
        error = float(np.abs(np.asarray(actual, dtype=np.float32) - np.asarray(expected, dtype=np.float32)).mean())
        similarity = luma_similarity(actual, expected)
        require(error <= 5 and similarity >= .97, f'Encoded picture does not match {shot["id"]}: error={error}, luma={similarity}')
        samples.append({'shot': shot['id'], 'frame': number, 'time': number / FPS,
                        'rgb_mae_0_255': round(error, 6), 'global_bt709_luma_ssim': round(similarity, 6)})
    return {'passed': True, 'samples': samples, 'thresholds': {'maximum_rgb_mae': 5, 'minimum_luma_ssim': .97},
            'method': 'Native central-picture band at exact EDL clock vs staged source. No resize, alignment search or colour fitting.',
            'limits': 'Sampled source correspondence, not proof of subject motion or every-frame image quality.'}


def contact_sheets(video, plan, cues, directory):
    directory.mkdir(parents=True, exist_ok=True)
    font_path = ROOT / 'assets/fonts/NotoSerifCJKsc-Regular.otf'
    font = ImageFont.truetype(str(font_path), 18)
    pages = []
    for offset in range(0, len(plan['shots']), 16):
        shots = plan['shots'][offset:offset + 16]
        board = Image.new('RGB', (1920, 46 + math.ceil(len(shots) / 4) * 325), '#101116')
        draw = ImageDraw.Draw(board)
        draw.text((14, 8), f'Hock Siew — encoded film — shots {offset + 1}–{offset + len(shots)}', font=font, fill='#f6d38a')
        for slot, shot in enumerate(shots):
            at = ((shot['start_frame'] + shot['end_frame']) // 2) / FPS
            still = frame(video, at).resize((480, 270), Image.Resampling.LANCZOS)
            x, y = (slot % 4) * 480, 46 + (slot // 4) * 325
            board.paste(still, (x, y))
            draw.text((x + 8, y + 273), f'{shot["id"]}  {at:.3f}s', font=font, fill='#f6d38a')
            text = next((c['text'] for c in cues if c['start'] <= at < c['end']), '[instrumental / dedication]')
            draw.text((x + 8, y + 298), text, font=font, fill='#ffffff')
        output = directory / f'contact-sheet-{len(pages) + 1:02}.jpg'
        board.save(output, quality=93, subsampling=0)
        pages.append(output.relative_to(ROOT).as_posix())
    spelling = [c for c in cues if any(name in c['text'].lower() for name in ('hock', 'siew', '谢惠福', '拿督'))]
    proof = Image.new('RGB', (1540, max(1, len(spelling)) * 150 + 60), '#101116')
    draw = ImageDraw.Draw(proof)
    draw.text((15, 8), f'Actual MP4 — {len(spelling)} name/dedication lyric appearances', font=font, fill='#f6d38a')
    for index, cue in enumerate(spelling):
        at = math.floor((cue['start'] + cue['end']) * FPS / 2) / FPS
        still = frame(video, at, (190, 850, 1540, 120))
        proof.paste(still, (0, 45 + index * 150))
        draw.text((12, 166 + index * 150), f'{at:.3f}s   {cue["text"]}', font=font, fill='white')
    proof.save(directory / 'name-lyric-proofs.png')
    frame(video, plan['duration_seconds'] - 4).save(directory / 'closing-dedication.png')
    return {'contact_sheets': pages, 'sampled_shots': len(plan['shots']), 'spelling_crops': len(spelling),
            'spelling_sheet': (directory / 'name-lyric-proofs.png').relative_to(ROOT).as_posix(),
            'closing_dedication': (directory / 'closing-dedication.png').relative_to(ROOT).as_posix(),
            'review_status': 'pending visual inspection of actual encoded images'}


def verify(video, make_sheets=False):
    plan = read(ROOT / 'edit-plan.json')
    cues = read(ROOT / 'captions.json')
    master = ROOT / 'assets/bgm.wav'
    original_duration = float(probe(master)['format']['duration'])
    metadata = probe(video)
    picture = [s for s in metadata['streams'] if s.get('codec_type') == 'video']
    audio = [s for s in metadata['streams'] if s.get('codec_type') == 'audio']
    require(len(picture) == len(audio) == 1, 'Expected one video and one song stream.')
    v, a = picture[0], audio[0]
    require((v.get('width'), v.get('height')) == (1920, 1080) and v.get('codec_name') == 'h264'
            and v.get('pix_fmt') == 'yuv420p' and Fraction(v['avg_frame_rate']) == FPS, 'Wrong delivery format.')
    require(a.get('codec_name') == 'aac' and a.get('channels') == 2 and int(a['sample_rate']) == SAMPLE_RATE,
            'Wrong soundtrack format.')
    require(abs(float(v.get('start_time', 0))) < .00001 and abs(float(a.get('start_time', 0))) < .00001,
            'Picture/song does not begin at zero.')
    require(abs(float(metadata['format']['duration']) - original_duration) <= 1 / FPS,
            'The export does not preserve the complete song duration.')
    progress = run(['ffmpeg', '-v', 'error', '-xerror', '-i', video, '-map', '0:v:0', '-map', '0:a:0',
                    '-progress', 'pipe:1', '-nostats', '-f', 'null', '-']).decode('utf-8')
    counts = re.findall(r'^frame=(\d+)$', progress, flags=re.M)
    require(counts and 'progress=end' in progress and int(counts[-1]) == math.ceil(original_duration * FPS),
            'Complete film decode/frame count failed.')
    x, y = stereo(master), stereo(video)
    require(len(x) == round(original_duration * SAMPLE_RATE) and abs(len(x) - len(y)) <= 1024,
            'Soundtrack sample count differs from the master.')
    count = min(len(x), len(y))
    correlations = [float(np.corrcoef(x[:count, channel], y[:count, channel])[0, 1]) for channel in range(2)]
    require(all(math.isfinite(c) and c >= .98 for c in correlations), 'Zero-offset original-song correlation failed.')
    gains_db = []
    for channel in range(2):
        original = x[:count, channel].astype(np.float64)
        encoded = y[:count, channel].astype(np.float64)
        gain = float(np.dot(original, encoded) / np.dot(original, original))
        gains_db.append(20 * math.log10(gain) if gain > 0 else float('-inf'))
    require(all(math.isfinite(gain) and abs(gain) <= .15 for gain in gains_db),
            'The encoded song gain differs from the unmodified master.')
    require(plan['audio_sha256'] == sha256(master) and plan['captions_sha256'] == sha256(ROOT / 'captions.json'),
            'The original source clock or lyrics changed after planning.')
    from prepare_film import load_clips, validate_plan
    clips = load_clips()
    validate_plan(plan, clips, cues, original_duration)
    hashes = {clip['sha256'] for clip in clips.values()}
    require(len(hashes) == len(clips), 'Two native clip IDs point to the same physical source.')
    result = {'passed': True, 'verified_at_utc': datetime.now(UTC).isoformat(), 'video': str(video.resolve()),
              'video_sha256': sha256(video), 'size_bytes': video.stat().st_size,
              'duration_seconds': float(metadata['format']['duration']), 'audio_master_seconds': original_duration,
              'frames': int(counts[-1]), 'width': 1920, 'height': 1080, 'fps': FPS, 'full_decode': True,
              'audio': {'offset_samples': 0, 'per_channel_correlation': correlations,
                        'per_channel_least_squares_gain_db': gains_db, 'gain_tolerance_db': .15,
                        'compared_samples_per_channel': count, 'encoded_aac_sha256': audio_payload(video)},
              'lyrics': lyrics_check(cues, original_duration), 'native_clip_count': len(clips),
              'picture_binding': picture_binding(video, plan),
              'source_hashes': {p.relative_to(ROOT).as_posix(): sha256(p) for p in ROOT.glob('*')
                                if p.is_file() and p.suffix in {'.py', '.json', '.ass', '.txt'}}}
    if make_sheets:
        result['visual_review'] = contact_sheets(video, plan, cues, ROOT / 'renders/review')
    sharing = video.with_name(video.stem + '-720p.mp4')
    if sharing.exists():
        shared = probe(sharing)
        vs = next(s for s in shared['streams'] if s.get('codec_type') == 'video')
        require((vs['width'], vs['height']) == (1280, 720) and int(vs['nb_frames']) == result['frames'],
                'Sharing copy dimensions/frame count differ.')
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', sharing, '-f', 'null', '-'])
        require(audio_payload(sharing) == result['audio']['encoded_aac_sha256'], 'Sharing copy changed the encoded song.')
        result['sharing_copy'] = {'path': str(sharing.resolve()), 'size_bytes': sharing.stat().st_size,
                                  'sha256': sha256(sharing), 'full_decode': True, 'audio_payload_identical': True}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--contact-sheets', action='store_true')
    args = parser.parse_args()
    try:
        receipt = verify(args.video.resolve(), args.contact_sheets)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        receipt = {'passed': False, 'error': str(error), 'video': str(args.video.resolve())}
    output = args.video.with_suffix('.verification.json')
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: receipt.get(key) for key in ('passed', 'error', 'frames', 'audio', 'size_bytes')}, indent=2))
    raise SystemExit(0 if receipt['passed'] else 1)

"""Probe, fully decode and sample raw V3 sources; never accept identity automatically."""
from __future__ import annotations

import argparse
import json
import re
from fractions import Fraction
from pathlib import Path

from prepare_film import probe, read_json, run, sha256, write_json

ROOT = Path(__file__).resolve().parent


def project_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'Path escapes this project: {value}')
    return path


def inspect_job(job, review_dir):
    ident = job['id']
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', ident):
        raise ValueError(f'Unsafe source id: {ident}')
    path = project_path(job['path'])
    if not path.is_file():
        return {'id': ident, 'path': job['path'], 'technical_status': 'missing'}
    metadata = probe(path)
    streams = metadata['streams']
    pictures = [s for s in streams if s.get('codec_type') == 'video']
    if len(pictures) != 1:
        raise ValueError(f'{ident}: expected one video stream')
    video = pictures[0]
    fps = Fraction(video['avg_frame_rate'])
    duration = float(video.get('duration') or metadata['format']['duration'])
    if fps <= 0 or duration <= 0:
        raise ValueError(f'{ident}: invalid timing metadata')
    # This decodes every video frame; a readable container alone is insufficient.
    run(['ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-i', path,
         '-map', '0:v:0', '-f', 'null', '-'])
    read_count = json.loads(run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames', '-of', 'json', path]))
    frames = int(read_count['streams'][0]['nb_read_frames'])
    if frames < 10:
        raise ValueError(f'{ident}: fewer than ten decoded frames')
    indexes = [round(n * (frames - 1) / 9) for n in range(10)]
    select = '+'.join(f'eq(n\\,{n})' for n in indexes)
    sheet = review_dir / f'{ident}.jpg'
    run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', path,
         '-vf', f'select={select},scale=640:360:force_original_aspect_ratio=decrease,'
                'pad=640:360:(ow-iw)/2:(oh-ih)/2,tile=5x2',
         '-frames:v', '1', '-q:v', '3', sheet])
    digest = sha256(path)
    if job.get('sha256') and digest != job['sha256']:
        raise ValueError(f'{ident}: recorded source hash mismatch')
    return {
        'id': ident, 'path': job['path'], 'model': job.get('model'),
        'task_id': job.get('task_id'), 'sha256': digest,
        'bytes': path.stat().st_size, 'codec': video['codec_name'],
        'width': video['width'], 'height': video['height'],
        'fps': str(fps), 'duration_seconds': duration, 'decoded_frames': frames,
        'audio_streams': sum(s.get('codec_type') == 'audio' for s in streams),
        'technical_status': 'full_decode_passed', 'raw_file_modified': False,
        'sample_sheet': sheet.relative_to(ROOT).as_posix(),
        'sample_frame_indexes': indexes,
        'sample_times_seconds': [round(n / float(fps), 6) for n in indexes],
        'identity_and_naturalness': 'not_automatically_assessed',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', default='generation-jobs-v3.json')
    parser.add_argument('--output', default='source-metadata-v3.json')
    parser.add_argument('--review-dir', default='renders/v3/source-review')
    parser.add_argument('--allow-missing', action='store_true')
    args = parser.parse_args()
    jobs = read_json(project_path(args.jobs))['jobs']
    if not jobs or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('Job ids must be unique and the job list nonempty')
    review_dir = project_path(args.review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)
    sources = [inspect_job(job, review_dir) for job in jobs]
    missing = [s['id'] for s in sources if s['technical_status'] == 'missing']
    write_json(project_path(args.output), {
        'sources': sources, 'complete': not missing, 'missing_ids': missing,
        'method': 'Full video decode plus ten evenly spaced native-frame samples per present source.',
        'creative_acceptance': 'requires_separate_visual_review',
    })
    print(json.dumps({'inspected': len(sources) - len(missing), 'missing': missing,
                      'output': args.output}, ensure_ascii=False))
    if missing and not args.allow_missing:
        raise SystemExit('Missing source files; this inspection is incomplete.')


if __name__ == '__main__':
    main()

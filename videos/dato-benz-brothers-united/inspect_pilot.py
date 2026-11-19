"""Inspect local raw pilot outputs without modifying picture, timing or audio.

Runway submission/download is separate. These checks establish file integrity,
not a person's likeness or naturalness; the complete raw clips need user review.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from prepare_film import probe, run, sha256, write_json

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'pilot-v3.json').read_text(encoding='utf-8-sig'))
    for ref in manifest['inputs']:
        if sha256(ROOT / ref['path']) != ref['sha256']:
            raise ValueError(f"Changed original reference: {ref['path']}")
    outputs = []
    for item in manifest['candidates']:
        path = ROOT / item['path']
        data = probe(path)
        videos = [s for s in data['streams'] if s['codec_type'] == 'video']
        audio = [s for s in data['streams'] if s['codec_type'] == 'audio']
        if len(videos) != 1:
            raise ValueError(f'Expected one video stream: {path}')
        video = videos[0]
        fps = float(Fraction(video['avg_frame_rate']))
        duration = float(video.get('duration') or data['format']['duration'])
        if (video['width'], video['height']) != (1920, 1080):
            raise ValueError(f'Unexpected native dimensions: {path}')
        if abs(duration - 5) > max(0.05, 1 / fps):
            raise ValueError(f'Unexpected duration: {path}: {duration}')
        if audio:
            raise ValueError(f'Unexpected audio in silent raw test: {path}')
        # Full decode, not just container/first-frame inspection.
        run(['ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-i', path,
             '-map', '0:v:0', '-f', 'null', '-'])
        counted = json.loads(run([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=nb_read_frames', '-of', 'json', path]))
        sheet = ROOT / 'renders/pilot-v3' / f"{item['model']}-samples.jpg"
        run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', path,
             '-vf', 'fps=2,scale=640:360,tile=5x2', '-frames:v', '1',
             '-q:v', '3', sheet])
        outputs.append({
            'model': item['model'], 'task_id': item['task_id'],
            'path': item['path'], 'sha256': sha256(path),
            'bytes': path.stat().st_size, 'codec': video['codec_name'],
            'width': video['width'], 'height': video['height'],
            'frame_rate': video['avg_frame_rate'], 'duration_seconds': duration,
            'decoded_frames': int(counted['streams'][0]['nb_read_frames']),
            'audio_streams': len(audio), 'full_decode': 'passed',
            'sample_sheet': sheet.relative_to(ROOT).as_posix(),
            'sample_interval_seconds': 0.5,
            'raw_file_modified': False,
            'likeness_and_naturalness': 'requires_complete_clip_user_review',
        })
    write_json(ROOT / 'PILOT-TECHNICAL.json', {
        'original_reference_hashes': 'matched',
        'outputs': outputs,
        'technical_checks': 'passed',
        'creative_acceptance': 'pending_user_review',
        'note': 'Chronological samples and full decoding do not prove natural motion or personal likeness.',
    })
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Make and verify a smaller 720p copy, retaining the final AAC stream exactly."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args):
    return subprocess.run(args, check=True, capture_output=True).stdout


def audio_hash(path):
    return hashlib.sha256(run('ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                              '-c:a', 'copy', '-f', 'adts', '-')).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'renders/BOSSTON-Pragon-Good-Fortune-Cinematic.mp4')
    parser.add_argument('--output', type=Path, default=ROOT / 'renders/BOSSTON-Pragon-Good-Fortune-Cinematic-720p.mp4')
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError('Sharing copy must have a distinct path.')
    run('ffmpeg', '-y', '-v', 'error', '-i', str(args.source), '-map', '0:v:0', '-map', '0:a:0',
        '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-maxrate', '6M', '-bufsize', '12M', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
        '-movflags', '+faststart', str(args.output))
    metadata = json.loads(run('ffprobe', '-v', 'error', '-show_streams', '-show_format',
                              '-of', 'json', str(args.output)))
    v = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    assert (v['width'], v['height'], v['avg_frame_rate']) == (1280, 720, '30/1')
    assert int(v['nb_frames']) == 5550
    assert abs(float(metadata['format']['duration']) - 185) < .04
    run('ffmpeg', '-v', 'error', '-xerror', '-i', str(args.output), '-f', 'null', '-')
    original_audio, copied_audio = audio_hash(args.source), audio_hash(args.output)
    assert original_audio == copied_audio, 'Sharing copy changed the encoded audio.'
    result = {'passed': True, 'duration_seconds': 185, 'frames': 5550, 'width': 1280, 'height': 720,
              'full_decode': True, 'audio_payload_identical': True, 'audio_adts_sha256': copied_audio,
              'size_bytes': args.output.stat().st_size,
              'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.output.with_suffix('.verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Verify the encoded music film, including original-track timing and full decode."""
from pathlib import Path
import argparse
import json
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parent


def run(*args: str) -> bytes:
    return subprocess.run(args, check=True, capture_output=True).stdout


def audio(path: Path) -> np.ndarray:
    return np.frombuffer(run('ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1',
                             '-ar', '8000', '-f', 'f32le', '-'), dtype='<f4')


def verify(path: Path, *, share: bool = False) -> dict:
    metadata = json.loads(run('ffprobe', '-v', 'error', '-show_streams', '-show_format',
                              '-of', 'json', str(path)))
    video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    sound = next(s for s in metadata['streams'] if s['codec_type'] == 'audio')
    duration = float(metadata['format']['duration'])
    assert (video['width'], video['height']) == ((1280, 720) if share else (1920, 1080))
    assert video['codec_name'] == 'h264' and video['pix_fmt'] == 'yuv420p'
    assert video['avg_frame_rate'] == '30/1'
    assert sound['codec_name'] == 'aac' and sound['channels'] == 2
    assert sound['sample_rate'] == '48000'
    assert abs(duration - 372.76) <= .04, duration
    # Decode the entire export; broken frame packets fail here.
    run('ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-')
    original, encoded = audio(ROOT / 'assets/bgm.wav'), audio(path)
    length = min(len(original), len(encoded))
    correlation = float(np.corrcoef(original[:length], encoded[:length])[0, 1])
    assert correlation >= .98, f'Original-track timing/content mismatch: {correlation}'
    captions = json.loads((ROOT / 'captions.json').read_text(encoding='utf-8'))
    for current in captions:
        assert 0 <= current['start'] < current['end'] <= duration
    for first, second in zip(captions, captions[1:]):
        assert first['end'] <= second['start'] + .001
    return {'passed': True, 'duration_seconds': duration, 'width': video['width'],
            'height': video['height'], 'fps': 30, 'video_codec': video['codec_name'],
            'audio_codec': sound['codec_name'], 'audio_sample_rate': 48000,
            'audio_channels': 2, 'original_audio_correlation': round(correlation, 6),
            'subtitle_cues': len(captions), 'full_decode': 'passed',
            'size_bytes': path.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('--share', action='store_true', help='Verify the 720p sharing profile.')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(args.video, share=args.share)
    report = args.report or ROOT / ('renders/share-verification.json' if args.share
                                   else 'renders/delivery-verification.json')
    report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

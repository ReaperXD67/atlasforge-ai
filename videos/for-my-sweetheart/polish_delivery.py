"""Replace rejected generated-motion windows with verified composition patches.

The full composition is already corrected for future renders. This optional
post-render path preserves the completed export and its audio while replacing
only four short visual windows, avoiding a second full browser capture.
"""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parent
RENDERS = ROOT / 'renders'
PATCHES = (
    ('repair-lily-a.mp4', 4080, 153),
    ('repair-garden-a.mp4', 8637, 186),
    ('repair-lily-b.mp4', 9759, 156),
    ('repair-garden-b.mp4', 9978, 186),
)


def probe(path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams',
                             '-of', 'json', str(path)], capture_output=True, check=True)
    return next(s for s in json.loads(result.stdout)['streams'] if s['codec_type'] == 'video')


def audio_hash(path: Path) -> str:
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                             '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'],
                            capture_output=True, check=True)
    return result.stdout.decode().strip()


def main():
    source = RENDERS / 'For-my-Sweetheart-Anniversary.mp4'
    destination = RENDERS / 'For-my-Sweetheart-Anniversary-Final.mp4'
    command = ['ffmpeg', '-hide_banner', '-y', '-i', str(source)]
    filters = ['[0:v]settb=1/30,setpts=N[base]']
    current = 'base'
    for index, (name, start_frame, count) in enumerate(PATCHES, 1):
        path = RENDERS / name
        metadata = probe(path)
        assert (metadata['width'], metadata['height']) == (1920, 1080), name
        assert metadata['avg_frame_rate'] == '30/1', name
        assert int(metadata['nb_frames']) == count, (name, metadata['nb_frames'])
        command.extend(['-i', str(path)])
        filters.append(f'[{index}:v]settb=1/30,setpts=N+{start_frame}[patch{index}]')
        # A sub-frame epsilon avoids decimal-boundary ambiguity in enable.
        first = start_frame / 30 - .0001
        last = (start_frame + count) / 30 - .0001
        filters.append(f'[{current}][patch{index}]overlay=eof_action=pass:repeatlast=0:'
                       f"enable='between(t,{first:.6f},{last:.6f})'[out{index}]")
        current = f'out{index}'
    command.extend(['-filter_complex', ';'.join(filters), '-map', f'[{current}]',
                    '-map', '0:a:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '17',
                    '-pix_fmt', 'yuv420p', '-r', '30', '-frames:v', '11183',
                    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                    '-c:a', 'copy', '-movflags', '+faststart', str(destination)])
    subprocess.run(command, check=True)
    source_audio, final_audio = audio_hash(source), audio_hash(destination)
    assert source_audio == final_audio, 'The encoded audio payload changed.'
    metadata = probe(destination)
    assert int(metadata['nb_frames']) == 11183
    assert metadata['avg_frame_rate'] == '30/1'
    (RENDERS / 'polish-verification.json').write_text(json.dumps({
        'passed': True, 'frame_count': 11183, 'audio_payload_unchanged': True,
        'audio_sha256': final_audio, 'replaced_windows': [
            {'patch': name, 'first_frame': start, 'frame_count': count}
            for name, start, count in PATCHES
        ]}, indent=2), encoding='utf-8')
    print(destination)


if __name__ == '__main__':
    main()

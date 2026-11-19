"""Render the identity-led second cut without changing the first delivery.

V2 stays on the native 24fps picture cadence. Its EDL records every identity,
context crop and deliberate reprise; the original song keeps its exact clock.
"""
from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

from prepare_film import (
    ass_text,
    ass_time,
    ffmpeg,
    local_path,
    probe,
    read_json,
    run,
    sha256,
    write_json,
)

ROOT = Path(__file__).resolve().parent
FPS = 24
WIDTH, HEIGHT = 1920, 1080
OUTPUT = ROOT / 'renders/v2'
MASTER_NAME = 'Hock-Siew-Personal-Tribute-V2.mp4'


def load_clips():
    manifest = read_json(ROOT / 'native-clips-v2.json')
    clips = manifest['clips']
    result = {}
    for ident in manifest.get('order', clips):
        item = clips[ident]
        if item.get('status') != 'accepted' or not item.get('provenance'):
            raise ValueError(f'{ident}: admission and provenance required.')
        source = local_path(item['path'])
        metadata = probe(source)
        stream = next(s for s in metadata['streams'] if s.get('codec_type') == 'video')
        duration = float(stream.get('duration') or metadata['format']['duration'])
        digest = sha256(source)
        if item.get('sha256') and item['sha256'] != digest:
            raise ValueError(f'{ident}: source hash changed.')
        lower, upper = item['usable_range']['start'], item['usable_range']['end']
        if not 0 <= lower < upper <= duration + .00001:
            raise ValueError(f'{ident}: bad admitted interval.')
        if item.get('identity') not in {'hock_siew', 'context'}:
            raise ValueError(f'{ident}: explicit protagonist or context identity is required.')
        result[ident] = {**item, 'sha256': digest, 'duration': duration,
                         'width': stream['width'], 'height': stream['height']}
    return result


def validate_plan(plan, clips, cues, duration):
    if plan['fps'] != FPS or abs(plan['duration_seconds'] - duration) > .00001:
        raise ValueError('V2 picture clock must be native24fps and the complete song.')
    if plan['audio_sha256'] != sha256(ROOT / 'assets/bgm.wav') or plan['captions_sha256'] != sha256(ROOT / 'captions.json'):
        raise ValueError('Frozen audio/captions changed since the edit was authored.')
    if plan['frames'] != math.ceil(duration * FPS):
        raise ValueError('V2 must cover the full recording at native24fps.')
    cursor, previous, windows = 0, {}, {}
    recognition_seconds = native_seconds = 0
    for shot in plan['shots']:
        if shot['id'] in previous or shot['start_frame'] != cursor or shot['end_frame'] <= cursor:
            raise ValueError('Duplicate shot id, gap or overlap in V2.')
        if not isinstance(shot['start_frame'], int) or not isinstance(shot['end_frame'], int):
            raise ValueError('Cuts must use integer frames.')
        length = (shot['end_frame'] - cursor) / FPS
        if shot['kind'] == 'native':
            native_seconds += length
            clip = clips[shot['clip']]
            a, rate = float(shot['source_at']), float(shot.get('rate', 1))
            b = a + length * rate
            if (not math.isfinite(a) or not .8 <= rate <= 1.2
                    or a < clip['usable_range']['start'] - .00001 or b > clip['usable_range']['end'] + .00001):
                raise ValueError(f'{shot["id"]}: source interval outside admission.')
            if clip['identity'] == 'context' and not shot.get('context_only'):
                raise ValueError(f'{shot["id"]}: context must be explicitly identified.')
            if clip['identity'] == 'context' and shot['clip'] not in {'sea-dawn', 'wet-footsteps'} and not shot.get('crop'):
                raise ValueError(f'{shot["id"]}: this contextual source requires an approved face-free crop.')
            overlaps = [other for lo, hi, other in windows.setdefault(shot['clip'], []) if min(b, hi) - max(a, lo) > .00001]
            if overlaps:
                origin = previous.get(shot.get('reprise_of'))
                if not ((clip['identity'] == 'hock_siew' or shot['clip'] == 'sea-dawn') and shot.get('reprise_reason')
                        and origin and origin.get('clip') == shot['clip']):
                    raise ValueError(f'{shot["id"]}: repeated source time needs an earlier shot and editorial reason.')
            windows[shot['clip']].append((a, b, shot['id']))
            crop = shot.get('crop')
            if crop and not (crop['x'] >= 0 and crop['y'] >= 0 and crop['width'] > 0 and crop['height'] > 0
                             and crop['x'] + crop['width'] <= clip['width'] and crop['y'] + crop['height'] <= clip['height']):
                raise ValueError(f'{shot["id"]}: crop outside source frame.')
            if clip['identity'] == 'hock_siew':
                recognition_seconds += length
        elif shot['kind'] == 'photo':
            local_path(shot['path'])
            if shot.get('identity') != 'hock_siew':
                raise ValueError('Every body photograph must have confirmed recipient identity.')
            if not shot.get('closing') and length > 6:
                raise ValueError('Body photo inserts should remain brief.')
            recognition_seconds += length
        else:
            raise ValueError('Only native motion or supplied recipient photographs are permitted.')
        previous[shot['id']] = shot
        cursor = shot['end_frame']
    if cursor != plan['frames']:
        raise ValueError('V2 does not cover the entire recording.')
    if native_seconds < duration * .8:
        raise ValueError('V2 needs native movement for at least80percent of the full film.')
    final = plan['shots'][-1]
    if (final['kind'] != 'photo' or final['path'] != 'assets/photos/seaside.jpg'
            or not final.get('closing') or final['start_frame'] != round(plan['closing_start'] * FPS)):
        raise ValueError('V2 ends with the supplied original seaside photograph.')
    first = plan['shots'][0]
    if first['kind'] != 'photo' and clips[first['clip']]['identity'] != 'hock_siew':
        raise ValueError('V2 must introduce the real recipient in its first shot.')
    for cue in cues:
        if not 0 <= cue['start'] < cue['end'] <= duration:
            raise ValueError('A lyric cue leaves the master clock.')
        if any(name in cue['text'] for name in ('Hock Siew', '谢惠福')):
            overlapping = [s for s in plan['shots'] if s['end_frame'] / FPS > cue['start'] + .00001
                           and s['start_frame'] / FPS < cue['end'] - .00001]
            for shot in overlapping:
                if shot['kind'] != 'photo' and clips[shot['clip']]['identity'] != 'hock_siew':
                    raise ValueError(f'{shot["id"]}: the entire named lyric must show Hock Siew.')
    return {'recognisable_recipient_seconds': round(recognition_seconds, 3),
            'recognisable_recipient_fraction': round(recognition_seconds / duration, 4),
            'native_motion_seconds': round(native_seconds, 3),
            'original_photo_seconds': round(plan['frames'] / FPS - native_seconds, 3),
            'intentional_reprises': sum(bool(s.get('reprise_of')) for s in plan['shots'])}


def write_ass(cues, plan):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyrics,Noto Serif CJK SC,52,&H00E8F3FA,&H00E8F3FA,&H00101822,&H90000000,0,0,0,0,100,100,1.7,0,1,2.0,1.0,2,130,130,130,1
Style: Chorus,Noto Serif CJK SC,54,&H0096D5F1,&H0096D5F1,&H00101822,&H90000000,0,0,0,0,100,100,1.7,0,1,2.0,1.0,2,130,130,130,1
Style: Title,Noto Serif CJK SC,91,&H00DFF2FF,&H00DFF2FF,&H00101822,&H90000000,0,0,0,0,100,100,7,0,1,1.0,1.0,5,100,100,100,1
Style: Small,Noto Serif CJK SC,36,&H00DFF2FF,&H00DFF2FF,&H00101822,&H90000000,0,0,0,0,100,100,2,0,1,1.0,1.0,5,100,100,100,1
Style: Dedication,Noto Serif CJK SC,58,&H00DFF2FF,&H00DFF2FF,&H00101822,&H90000000,0,0,0,0,100,100,3,0,1,1.0,1.0,5,100,100,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []

    def event(start, end, style, text, layer=1):
        events.append(f'Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{text}')

    intro = plan.get('intro_text', {'start': .4, 'end': 5.3})
    event(intro['start'], intro['end'], 'Title', r'{\fad(550,550)\pos(1320,405)}有你，兄弟同心')
    event(intro['start'] + .3, intro['end'], 'Small', r'{\fad(550,550)\pos(1320,515)}献给拿督斯里谢惠福')
    event(intro['start'] + .6, intro['end'], 'Dedication', r'{\fad(550,550)\fs61\pos(1320,600)\c&H0096D5F1&}Hock Siew')
    for cue in cues:
        style = 'Chorus' if '副歌' in cue.get('section', '') else 'Lyrics'
        event(cue['start'], cue['end'], style, r'{\fad(70,100)}' + ass_text(cue['text']), 2)
    for label in plan.get('memory_labels', []):
        event(label['start'], label['end'], 'Dedication', r'{\fad(300,350)\fs64\pos(1300,465)}' + ass_text(label['latin']), 3)
        event(label['start'] + .15, label['end'], 'Small', r'{\fad(300,350)\pos(1300,565)}' + ass_text(label['text']), 3)
    start = plan['closing_start'] + .7
    end = plan['duration_seconds']
    for delay, style, text in [
        (0, 'Small', r'{\fad(800,1000)\pos(1300,280)}献给拿督斯里谢惠福'),
        (0, 'Dedication', r'{\fad(800,1000)\fs69\pos(1300,360)\c&H0096D5F1&}Hock Siew'),
        (.4, 'Dedication', r'{\fad(800,1000)\fs63\pos(1300,505)}有你，兄弟同心。'),
        (.9, 'Dedication', r'{\fad(800,1000)\fs51\pos(1300,600)}愿你平安，幸福永久。'),
        (1.4, 'Small', r'{\fad(800,1000)\pos(1300,745)\c&H0096D5F1&}兄弟情义 · 一路同行'),
    ]:
        event(start + delay, end, style, text, 3)
    (ROOT / 'film-v2.ass').write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')


def prepare():
    clips = load_clips()
    plan = read_json(ROOT / 'edit-plan-v2.json')
    cues = read_json(ROOT / 'captions.json')
    duration = float(probe(ROOT / 'assets/bgm.wav')['format']['duration'])
    stats = validate_plan(plan, clips, cues, duration)
    write_ass(cues, plan)
    write_json(ROOT / 'source-bindings-v2.json', {'audio_sha256': sha256(ROOT / 'assets/bgm.wav'),
               'captions_sha256': sha256(ROOT / 'captions.json'), 'clips': clips, 'identity_coverage': stats,
               'photo_sha256': sha256(ROOT / 'assets/photos/seaside.jpg')})
    return plan, clips


def admit(path, frames, width=WIDTH, height=HEIGHT):
    stream = next(s for s in probe(path)['streams'] if s.get('codec_type') == 'video')
    number = stream.get('nb_frames')
    if not number:
        import json
        metadata = run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=nb_read_frames', '-of', 'json', path])
        number = json.loads(metadata)['streams'][0]['nb_read_frames']
    if int(number) != frames or (stream['width'], stream['height']) != (width, height):
        raise ValueError(f'Incomplete V2 staged export: {path}')


def render(plan, clips):
    cache = OUTPUT / 'segments'
    cache.mkdir(parents=True, exist_ok=True)
    segments = []
    for shot in plan['shots']:
        path = cache / f'{shot["id"]}.mkv'
        frames = shot['end_frame'] - shot['start_frame']
        source = local_path(clips[shot['clip']]['path'] if shot['kind'] == 'native' else shot['path'])
        signature = {**shot, 'recipe_sha256': sha256(Path(__file__)), 'source_sha256': sha256(source)}
        sidecar = path.with_suffix('.json')
        if not path.exists() or not sidecar.exists() or read_json(sidecar) != signature:
            temporary = path.with_name(path.stem + '.staging.mkv')
            command = [ffmpeg(), '-y', '-hide_banner', '-v', 'error']
            if shot['kind'] == 'native':
                crop = shot.get('crop')
                filtering = [f'setpts=(PTS-STARTPTS)/{shot.get("rate", 1)}']
                if crop:
                    filtering += [f'crop={crop["width"]}:{crop["height"]}:{crop["x"]}:{crop["y"]}']
                filtering += ['fps=24', 'scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos',
                              'crop=1920:1080', 'setsar=1']
                filtering += [shot.get('grade', 'unsharp=3:3:0.18:3:3:0,eq=contrast=1.012:saturation=.98')]
                filtering += ['format=yuv420p']
                if shot.get('layout') == 'portrait':
                    if not crop:
                        raise ValueError('The group-memory portrait needs an explicit approved crop.')
                    filtering = (f'[0:v]setpts=(PTS-STARTPTS)/{shot.get("rate", 1)},fps=24,'
                                 f'crop={crop["width"]}:{crop["height"]}:{crop["x"]}:{crop["y"]},split[bg][fg];'
                                 '[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,'
                                 'boxblur=55:3,eq=brightness=-.28:saturation=.6[base];'
                                 '[fg]scale=710:900:force_original_aspect_ratio=decrease:flags=lanczos[portrait];'
                                 '[base][portrait]overlay=(960-w)/2:(H-h)/2,setsar=1,format=yuv420p[out]')
                    command += ['-ss', str(shot['source_at']), '-i', source, '-an', '-filter_complex', filtering, '-map', '[out]']
                else:
                    command += ['-ss', str(shot['source_at']), '-i', source, '-an', '-vf', ','.join(filtering)]
            else:
                side = shot.get('layout', 'left')
                x = '150' if side == 'left' else '(W-w)/2'
                foreground = '710:900' if side == 'left' else '1500:900'
                filtering = ('[0:v]split[bg][fg];[bg]scale=1920:1080:force_original_aspect_ratio=increase,'
                             'crop=1920:1080,boxblur=35:2,eq=brightness=-.24:saturation=.72[base];'
                             f'[fg]scale={foreground}:force_original_aspect_ratio=decrease:flags=lanczos[picture];'
                             f'[base][picture]overlay={x}:(H-h)/2,setsar=1,format=yuv420p[out]')
                command += ['-loop', '1', '-framerate', '24', '-i', source, '-filter_complex', filtering,
                            '-map', '[out]', '-an']
            command += ['-frames:v', str(frames), '-r', '24', '-c:v', 'ffv1', '-level', '3',
                        '-coder', '1', '-context', '1', '-slicecrc', '1', '-threads', '8',
                        '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                        '-colorspace', 'bt709', temporary]
            run(command)
            admit(temporary, frames)
            temporary.replace(path)
            write_json(sidecar, signature)
        segments.append(path)
        print(f'V2 staged {shot["id"]}: {frames} frames', flush=True)
    concat = OUTPUT / 'picture-concat.txt'
    concat.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding='utf-8')
    duration = plan['frames'] / FPS
    filters = ('ass=film-v2.ass:fontsdir=assets/fonts,'
               'drawbox=x=0:y=0:w=iw:h=76:color=0x030609:t=fill,'
               'drawbox=x=0:y=1004:w=iw:h=76:color=0x030609:t=fill,'
               f'fade=t=in:st=0:d=0.45,fade=t=out:st={duration - 1.0:.6f}:d=1.0')
    output = OUTPUT / MASTER_NAME
    temporary = output.with_name(output.stem + '.rendering.mp4')
    command = [ffmpeg(), '-y', '-hide_banner', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', concat,
               '-i', ROOT / 'assets/bgm.wav', '-map', '0:v:0', '-map', '1:a:0', '-vf', filters,
               '-frames:v', str(plan['frames']), '-t', f'{duration:.9f}', '-c:v', 'h264_nvenc', '-preset', 'p6', '-rc', 'vbr',
               '-cq', '16', '-b:v', '18M', '-maxrate', '28M', '-bufsize', '56M', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart',
               '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', temporary]
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-3000:])
    admit(temporary, plan['frames'])
    temporary.replace(output)
    return output


def share(master):
    output = master.with_name(master.stem + '-720p.mp4')
    temporary = output.with_name(output.stem + '.rendering.mp4')
    run([ffmpeg(), '-y', '-hide_banner', '-v', 'error', '-i', master, '-vf', 'scale=1280:720:flags=lanczos',
         '-c:v', 'h264_nvenc', '-preset', 'p6', '-rc', 'vbr', '-cq', '20', '-b:v', '5M', '-maxrate', '8M',
         '-bufsize', '16M', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', temporary])
    frames = int(next(s for s in probe(master)['streams'] if s.get('codec_type') == 'video')['nb_frames'])
    admit(temporary, frames, 1280, 720)
    temporary.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--share', action='store_true')
    args = parser.parse_args()
    plan, clips = prepare()
    if args.render:
        master = render(plan, clips)
        print(master, flush=True)
        if args.share:
            print(share(master), flush=True)

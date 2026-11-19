"""Compile and render the tribute from local native video and measured lyrics.

The original recording supplies the audio clock. edit-plan.json is editable and
stores exact source windows. Runway generation is deliberately outside this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FPS = 30
WIDTH, HEIGHT = 1920, 1080
MASTER_NAME = 'Hock-Siew-Brothers-United-Cinematic.mp4'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(command):
    result = subprocess.run([str(x) for x in command], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-3500:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def ffmpeg():
    # This official imageio binary supports the installed driver's NVENC API.
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def admit_render(path, frames, width=WIDTH, height=HEIGHT):
    metadata = probe(path)
    pictures = [stream for stream in metadata['streams'] if stream.get('codec_type') == 'video']
    if (len(pictures) != 1 or int(pictures[0].get('nb_frames', 0)) != frames
            or (pictures[0]['width'], pictures[0]['height']) != (width, height)):
        raise ValueError(f'Incomplete staged render: {path}')


def local_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError(f'Missing project-local source: {value}')
    return path


def load_clips():
    manifest = read_json(ROOT / 'native-clips.json')
    clips = manifest.get('clips', manifest)
    if isinstance(clips, list):
        clips = {item['id']: item for item in clips}
    order = manifest.get('order') or list(clips)
    if not clips or set(order) != set(clips):
        raise ValueError('The native clip manifest needs a complete explicit clip order.')
    result = {}
    for ident in order:
        item = clips[ident]
        if item.get('status') != 'accepted':
            raise ValueError(f'{ident}: native output still needs visual admission.')
        path = local_path(item['path'])
        if not item.get('provenance'):
            raise ValueError(f'{ident}: generation provenance is required.')
        metadata = probe(path)
        video = [s for s in metadata['streams'] if s.get('codec_type') == 'video']
        if len(video) != 1:
            raise ValueError(f'{ident}: expected one native video stream.')
        duration = float(video[0].get('duration') or metadata['format']['duration'])
        supplied = item.get('sha256')
        digest = sha256(path)
        if supplied and supplied != digest:
            raise ValueError(f'{ident}: native file hash changed.')
        lower = float(item.get('usable_range', {}).get('start', .2))
        upper = float(item.get('usable_range', {}).get('end', duration - .2))
        if not 0 <= lower < upper <= duration + .00001:
            raise ValueError(f'{ident}: invalid usable source interval.')
        result[ident] = {**item, 'duration': duration, 'sha256': digest,
                         'usable_range': {'start': lower, 'end': upper}}
    return result


def ass_time(seconds):
    ticks = round(seconds * 100)
    hours, ticks = divmod(ticks, 360000)
    minutes, ticks = divmod(ticks, 6000)
    secs, hundredths = divmod(ticks, 100)
    return f'{hours}:{minutes:02}:{secs:02}.{hundredths:02}'


def ass_text(value):
    return value.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', '\\N')


def write_ass(cues, closing_start, duration):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyrics,Noto Serif CJK SC,51,&H00DDF4FF,&H00DDF4FF,&H00101822,&H90000000,0,0,0,0,100,100,2.0,0,1,2.2,1.2,2,150,150,132,1
Style: Chorus,Noto Serif CJK SC,53,&H008AD3F6,&H008AD3F6,&H00101822,&H90000000,0,0,0,0,100,100,2.0,0,1,2.2,1.2,2,150,150,132,1
Style: Title,Noto Serif CJK SC,124,&H0095D9FA,&H0095D9FA,&H00101822,&H90000000,0,0,0,0,100,100,12,0,1,1.0,1.5,5,100,100,100,1
Style: Small,Noto Serif CJK SC,35,&H00DDF4FF,&H00DDF4FF,&H00101822,&H90000000,0,0,0,0,100,100,2,0,1,1.0,1.0,5,100,100,100,1
Style: Dedication,Noto Serif CJK SC,51,&H00DDF4FF,&H00DDF4FF,&H00101822,&H90000000,0,0,0,0,100,100,3.0,0,1,1.0,1.0,5,100,100,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []

    def event(start, end, style, content, layer=1):
        events.append(f'Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{content}')

    first_vocal = float(cues[0]['start'])
    title_end = min(5.0, max(2.8, first_vocal - .35))
    event(.2, title_end, 'Title', r'{\fad(650,700)\fs108\pos(960,417)}有你，兄弟同心')
    event(.65, title_end, 'Small', r'{\fad(650,700)\pos(960,535)}献给拿督斯里谢惠福')
    for cue in cues:
        style = 'Chorus' if '副歌' in cue.get('section', '') or 'chorus' in cue.get('section', '').lower() else 'Lyrics'
        event(cue['start'], cue['end'], style, r'{\fad(90,120)}' + ass_text(cue['text']), 2)
    reveal = closing_start + .7
    event(reveal, duration, 'Small', r'{\fad(900,1100)\pos(1300,280)}献给拿督斯里谢惠福', 3)
    event(reveal, duration, 'Dedication', r'{\fad(900,1100)\fs69\pos(1300,360)\c&H008AD3F6&}Hock Siew', 3)
    event(reveal + .5, duration, 'Dedication', r'{\fad(900,1100)\fs63\pos(1300,505)}有你，兄弟同心。', 3)
    event(reveal + 1.2, duration, 'Dedication', r'{\fad(900,1100)\pos(1300,600)}愿你平安，幸福永久。', 3)
    event(reveal + 1.8, duration, 'Small', r'{\fad(900,1100)\pos(1300,745)\c&H008AD3F6&}兄弟情义 · 一路同行', 3)
    (ROOT / 'film.ass').write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')


def make_plan(clips, cues, duration, total_frames):
    end_vocal = max(float(c['end']) for c in cues)
    closing_start = max(duration - 12, min(end_vocal + .35, duration - 8))
    native_frames = round(closing_start * FPS)
    closing_start = native_frames / FPS
    chunks = []
    # Two passes create returns to earlier action with independent source time.
    for half in range(2):
        for ident, clip in clips.items():
            lower, upper = clip['usable_range']['start'], clip['usable_range']['end']
            middle = (lower + upper) / 2
            a, b = (lower, middle) if half == 0 else (middle, upper)
            chunks.append((ident, a, b))
    capacity = sum(b - a for _, a, b in chunks)
    if capacity * FPS + .01 < native_frames:
        raise ValueError(f'Need {native_frames / FPS:.2f}s of admitted source motion, have {capacity:.2f}s.')
    spans, previous = [], 0
    running = 0.0
    for index, (ident, a, b) in enumerate(chunks):
        running += b - a
        boundary = native_frames if index == len(chunks) - 1 else round(native_frames * running / capacity)
        count = boundary - previous
        if count < 8:
            raise ValueError('An automatic shot would be too brief to read.')
        spans.append({'id': f'shot-{index + 1:02}', 'kind': 'native', 'clip': ident,
                      'start_frame': previous, 'end_frame': boundary, 'source_at': round(a, 6),
                      'rate': 1.0, 'description': clips[ident].get('description', ident)})
        previous = boundary
    spans.append({'id': 'closing-memory', 'kind': 'photo', 'path': 'assets/photos/seaside.jpg',
                  'start_frame': native_frames, 'end_frame': total_frames,
                  'description': 'Original supplied seaside photograph and authored Mandarin dedication'})
    return {'revision': 1, 'duration_seconds': duration, 'fps': FPS, 'frames': total_frames,
            'closing_start': closing_start, 'source_mode': 'native-ai-video-and-supplied-memory',
            'shots': spans, 'captions_sha256': sha256(ROOT / 'captions.json'),
            'audio_sha256': sha256(ROOT / 'assets/bgm.wav'),
            'closing_message': '有你，兄弟同心。愿你平安，幸福永久。'}


def validate_plan(plan, clips, cues, duration):
    if plan['fps'] != FPS or abs(plan['duration_seconds'] - duration) > .00001:
        raise ValueError('Edit clock differs from the recording.')
    if plan['captions_sha256'] != sha256(ROOT / 'captions.json') or plan['audio_sha256'] != sha256(ROOT / 'assets/bgm.wav'):
        raise ValueError('Audio or lyric alignment changed since this edit was authored.')
    frame = 0
    windows = {}
    identities = set()
    if (not plan['shots'] or plan['shots'][-1]['kind'] != 'photo'
            or plan['shots'][-1].get('path') != 'assets/photos/seaside.jpg'
            or plan['shots'][-1]['start_frame'] != round(plan['closing_start'] * FPS)
            or any(shot['kind'] != 'native' for shot in plan['shots'][:-1])):
        raise ValueError('Use native motion throughout the body and the original seaside photograph for the final dedication.')
    for shot in plan['shots']:
        if (shot['id'] in identities or not isinstance(shot['start_frame'], int)
                or not isinstance(shot['end_frame'], int)):
            raise ValueError('Shot identifiers must be unique and boundaries must be integer frames.')
        identities.add(shot['id'])
        if shot['start_frame'] != frame or shot['end_frame'] <= frame:
            raise ValueError('The edit contains a gap, overlap or empty shot.')
        frame = shot['end_frame']
        if shot['kind'] == 'native':
            clip = clips[shot['clip']]
            a = float(shot['source_at'])
            end = a + (shot['end_frame'] - shot['start_frame']) / FPS * shot['rate']
            if (not math.isfinite(a) or not .8 <= shot['rate'] <= 1.2
                    or a < clip['usable_range']['start'] - .00001 or end > clip['usable_range']['end'] + .00001):
                raise ValueError(f'{shot["id"]}: source interval is outside its admitted range.')
            for lower, upper in windows.setdefault(shot['clip'], []):
                if min(end, upper) - max(a, lower) > .00001:
                    raise ValueError(f'{shot["id"]}: source motion is repeated.')
            windows[shot['clip']].append((a, end))
        elif shot['kind'] == 'photo':
            local_path(shot['path'])
        else:
            raise ValueError('Every shot must be a native clip or the supplied closing photograph.')
    if frame != plan['frames'] or frame != math.ceil(duration * FPS):
        raise ValueError('The timeline does not cover the complete recording.')
    for cue in cues:
        if not 0 <= cue['start'] < cue['end'] <= duration:
            raise ValueError('A lyric cue leaves the recording clock.')


def prepare():
    clips = load_clips()
    cues = read_json(ROOT / 'captions.json')
    duration = float(probe(ROOT / 'assets/bgm.wav')['format']['duration'])
    plan_path = ROOT / 'edit-plan.json'
    plan = read_json(plan_path) if plan_path.exists() else make_plan(clips, cues, duration, math.ceil(duration * FPS))
    validate_plan(plan, clips, cues, duration)
    write_json(plan_path, plan)
    write_ass(cues, plan['closing_start'], duration)
    write_json(ROOT / 'source-bindings.json', {'audio': {'path': 'assets/bgm.wav', 'sha256': sha256(ROOT / 'assets/bgm.wav')},
                                              'captions_sha256': sha256(ROOT / 'captions.json'), 'clips': clips,
                                              'photo_sha256': sha256(ROOT / 'assets/photos/seaside.jpg')})
    return plan, clips


def render(plan, clips):
    target = ROOT / 'renders'
    cache = target / 'segments'
    cache.mkdir(parents=True, exist_ok=True)
    encoder = ffmpeg()
    recipe_sha256 = sha256(Path(__file__))
    segments = []
    for shot in plan['shots']:
        path = cache / f'{shot["id"]}.mp4'
        frames = shot['end_frame'] - shot['start_frame']
        signature = {**shot, 'frames': frames, 'recipe_sha256': recipe_sha256,
                     'source_sha256': clips[shot['clip']]['sha256'] if shot['kind'] == 'native' else sha256(local_path(shot['path']))}
        sidecar = path.with_suffix('.json')
        if not path.exists() or not sidecar.exists() or read_json(sidecar) != signature:
            temporary = path.with_name(path.stem + '.staging.mp4')
            common = ['-y', '-hide_banner', '-v', 'error']
            if shot['kind'] == 'native':
                source = local_path(clips[shot['clip']]['path'])
                filters = (f'setpts=(PTS-STARTPTS)/{shot["rate"]},fps=30,'
                           'scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080,'
                           'setsar=1,eq=contrast=1.025:saturation=.96:brightness=-.004,'
                           'colorbalance=rs=.008:bs=-.006,format=yuv420p')
                command = common + ['-ss', str(shot['source_at']), '-i', str(source), '-an', '-vf', filters]
            else:
                source = local_path(shot['path'])
                filters = ('[0:v]split[background][photo];'
                           '[background]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,'
                           'boxblur=35:2,eq=brightness=-.22:saturation=.65[base];'
                           '[photo]scale=710:900:force_original_aspect_ratio=decrease:flags=lanczos[portrait];'
                           '[base][portrait]overlay=150:(H-h)/2,setsar=1,format=yuv420p[out]')
                command = common + ['-loop', '1', '-framerate', '30', '-i', str(source), '-filter_complex', filters, '-map', '[out]', '-an']
            command += ['-frames:v', str(frames), '-r', '30', '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr',
                        '-cq', '17', '-b:v', '12M', '-maxrate', '20M', '-bufsize', '40M', '-pix_fmt', 'yuv420p',
                        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', str(temporary)]
            run([encoder, *command])
            admit_render(temporary, frames)
            temporary.replace(path)
            write_json(sidecar, signature)
        segments.append(path)
        print(f'Staged {shot["id"]}: {frames} frames', flush=True)
    concat = target / 'picture-concat.txt'
    concat.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding='utf-8')
    duration = plan['frames'] / FPS
    picture_filters = ("ass=film.ass:fontsdir=assets/fonts,"
                       "drawbox=x=0:y=0:w=iw:h=76:color=0x030609:t=fill,"
                       "drawbox=x=0:y=1004:w=iw:h=76:color=0x030609:t=fill,"
                       f'fade=t=in:st=0:d=0.6,fade=t=out:st={duration - 1.1:.6f}:d=1.1')
    output = target / MASTER_NAME
    temporary = output.with_name(output.stem + '.rendering.mp4')
    command = [encoder, '-y', '-hide_banner', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
               '-i', str(ROOT / 'assets/bgm.wav'), '-map', '0:v:0', '-map', '1:a:0', '-vf', picture_filters,
               '-frames:v', str(plan['frames']), '-c:v', 'h264_nvenc', '-preset', 'p6', '-rc', 'vbr', '-cq', '17',
               '-b:v', '14M', '-maxrate', '24M', '-bufsize', '48M', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k',
               '-ar', '48000', '-movflags', '+faststart', '-color_primaries', 'bt709', '-color_trc', 'bt709',
               '-colorspace', 'bt709', str(temporary)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-3500:])
    admit_render(temporary, plan['frames'])
    temporary.replace(output)
    print(f'Rendered {output}', flush=True)
    return output


def share(master):
    output = master.with_name(master.stem + '-720p.mp4')
    temporary = output.with_name(output.stem + '.rendering.mp4')
    run([ffmpeg(), '-y', '-hide_banner', '-v', 'error', '-i', master, '-map', '0:v:0', '-map', '0:a:0',
         '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'h264_nvenc', '-preset', 'p6', '-rc', 'vbr', '-cq', '22',
         '-b:v', '3M', '-maxrate', '5M', '-bufsize', '10M', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
         '-movflags', '+faststart', temporary])
    frames = int(next(stream for stream in probe(master)['streams'] if stream.get('codec_type') == 'video')['nb_frames'])
    admit_render(temporary, frames, 1280, 720)
    temporary.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--share', action='store_true')
    args = parser.parse_args()
    edit, sources = prepare()
    if args.render:
        movie = render(edit, sources)
        if args.share:
            print(share(movie))

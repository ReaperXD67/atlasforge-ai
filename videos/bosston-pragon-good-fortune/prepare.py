"""Compile the reviewed vocal edit into a local, seek-safe HyperFrames film."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DURATION = 185.0
FPS = 30
ASSETS = {
    'avenue': 'assets/generated/lantern-avenue.png',
    'dragon': 'assets/generated/dragon-arena.png',
    'ribbon': 'assets/generated/silk-mountains.png',
    'sunrise': 'assets/generated/sky-lanterns.png',
    'drums': 'assets/generated/festival-drums.png',
    'koi': 'assets/generated/golden-koi.png',
    'bridge': 'assets/generated/celestial-bridge.png',
}


def read_json(name, default):
    path = ROOT / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def section_name(value):
    if '最终' in value or 'Final' in value:
        return 'final-chorus'
    if '预' in value or 'Pre-' in value:
        return 'pre-chorus'
    if '副歌' in value or 'Chorus' in value:
        return 'chorus'
    if '说唱' in value or 'Bridge' in value:
        return 'bridge'
    if '结尾' in value or 'Outro' in value:
        return 'outro'
    if '主歌二' in value or 'Verse 2' in value:
        return 'verse-2'
    if '主歌' in value or 'Verse' in value:
        return 'verse-1'
    return 'intro'


def scene_plan(captions, motion_assets, audio_map):
    """Action footage and physical camera scenes; no still-only shot is allowed."""
    def v(name):
        return ('video', name)

    def w(name):
        return ('world3d', name)
    chapters = [
        (0, 22.9, 'intro', [v('live-drums'), v('dragon-head'), v('lantern-field'),
                           v('live-drums'), v('white-lion'), v('cloud-dawn'), v('lantern-field')]),
        (22.9, 37.92, 'verse-1', [v('lantern-field'), v('lion-street'), v('koi'), v('cloud-sunrise'), v('cloud-dawn')]),
        (37.92, 49, 'pre-chorus', [v('koi'), v('lantern-field'), v('cloud-dawn'), v('dragon-head')]),
        (49, 66, 'chorus', [v('dragon-head'), v('white-lion'), v('lion-street'), v('live-drums'),
                           v('lion-street'), v('koi'), v('live-drums'), v('gold-fireworks'), v('white-lion')]),
        (66, 80.72, 'verse-2', [v('cloud-sunrise'), v('koi'), v('lantern-field'), v('white-lion'), v('koi')]),
        (80.72, 92, 'pre-chorus', [v('lantern-field'), v('koi'), v('cloud-dawn'), v('lion-street')]),
        (92, 108, 'chorus', [v('lion-street'), v('live-drums'), v('dragon-head'), v('white-lion'),
                            v('dragon-head'), v('live-drums'), v('koi'), v('gold-fireworks'), v('lion-street')]),
        (108, 119.58, 'instrumental', [v('cloud-sunrise'), v('gold-fireworks'), v('lantern-field')]),
        (119.58, 139.88, 'bridge', [v('live-drums'), v('white-lion'), v('live-drums'), v('koi'),
                                   v('lantern-field'), v('dragon-head'), v('gold-fireworks')]),
        (139.88, 156.26, 'final-chorus', [v('lion-street'), v('dragon-head'), v('white-lion'), v('gold-fireworks'),
                                        v('live-drums'), v('cloud-sunrise'), v('dragon-head'), v('gold-fireworks')]),
        (156.26, 176.4, 'outro', [v('gold-fireworks'), v('lantern-field'), v('koi'),
                                 v('dragon-head'), v('cloud-sunrise'), v('gold-fireworks')]),
        (176.4, 185, 'ending', [v('cloud-sunrise')]),
    ]
    aliases = {'lion-street': ['lion-street', 'white-lion'],
               'live-drums': ['live-drums', 'white-lion'],
               'lantern-close': ['lantern-close', 'lantern-field'],
               'cloud-sunrise': ['cloud-sunrise', 'cloud-dawn']}
    world_assets = {'lanterns': 'avenue', 'silk': 'ribbon', 'dragon': 'dragon',
                    'bridge': 'bridge', 'drums': 'drums', 'fireworks': 'dragon',
                    'finale': 'sunrise', 'water': 'koi'}
    onsets = [float(x) for x in audio_map.get('onsets_sec', [])]
    result = []
    usage = {}
    for start, end, section, shots in chapters:
        # Alternate closer action cuts and breathing room; use measured transients
        # only when close to the intended editorial boundary, not a made-up BPM.
        weights = [1.08 if i % 3 == 0 else .9 if i % 3 == 1 else 1.02 for i in range(len(shots))]
        boundaries = [start]
        running = 0
        for weight in weights[:-1]:
            running += weight
            target = start + (end - start) * running / sum(weights)
            near = min(onsets, key=lambda x: abs(x - target)) if onsets else target
            if abs(near - target) < .1:
                target = near
            boundaries.append(round(target * FPS) / FPS)
        boundaries.append(end)
        for local, ((media, key), (a, b)) in enumerate(zip(shots, pairwise(boundaries), strict=True)):
            seed = 1811 + len(result) * 37
            world = key if media == 'world3d' else 'lanterns'
            selected = next((name for name in aliases.get(key, [key]) if name in motion_assets), None)
            if media == 'video' and selected is None:
                media = 'world3d'
                world = 'drums' if 'drum' in key else 'dragon' if 'dragon' in key or 'lion' in key else 'water' if key == 'koi' else 'finale' if 'cloud' in key else 'lanterns'
            asset = world_assets.get(world, 'avenue')
            cue = next((c for c in captions if c['start'] <= a + .03 < c['end']), None)
            shot = {'id': f'shot-{len(result) + 1:02}', 'start': a, 'end': b,
                    'media': media, 'asset': asset, 'world': world,
                    'mode': 'plate', 'motion': ['track', 'orbit', 'rush', 'crane'][local % 4],
                    'seed': seed, 'transition': 'cut', 'section': section,
                    'lyric': cue['text'] if cue else ''}
            if media == 'video':
                item = motion_assets[selected]
                variants = item.get('variants') or [item]
                uses = usage.get(selected, 0)
                item = variants[uses % len(variants)]
                usage[selected] = uses + 1
                rate = .82 if any(x in selected for x in ['koi', 'lantern', 'cloud']) else 1
                safe = item.get('usable_range', {'start': .1, 'end': float(item['duration'])-.1})
                lower, upper = float(safe['start']), float(safe['end'])
                rate = min(rate, (upper-lower-.05) / (b - a))
                assert rate >= .65, (selected, rate, b-a, item['duration'])
                needed = (b - a) * rate
                available = upper-lower-needed
                assert available >= 0, (selected, needed, item['duration'])
                shot.update(video=selected, src=item['path'], rate=rate,
                            source_at=round(lower + available * ((seed * .6180339) % 1), 3),
                            crop='50% 50%', world3d=False)
            result.append(shot)
    assert result[0]['start'] == 0 and result[-1]['end'] == DURATION
    for a, b in pairwise(result):
        assert abs(a['end'] - b['start']) < 1e-8
    return result


def build(preview=False):
    captions = read_json('captions.json', [])
    if isinstance(captions, dict):
        captions = captions.get('cues', captions.get('captions', []))
    if not captions and not preview:
        raise RuntimeError('Reviewed, audio-matched captions.json is required for delivery.')
    wrong_brand = re.compile(r'(?<![A-Za-z])boston(?![A-Za-z])', re.IGNORECASE)
    display_text = [(ROOT / 'lyrics.txt').read_text(encoding='utf-8')]
    display_text += [c['text'] for c in captions]
    display_text += [word['text'] for c in captions for word in c.get('words', [])]
    if any(wrong_brand.search(text) for text in display_text):
        raise ValueError('Production brand spelling must be Bosston (double s).')
    for cue in captions:
        assert 0 <= cue['start'] < cue['end'] <= DURATION, cue
        assert cue['text'].strip()
    for a, b in pairwise(captions):
        assert a['end'] <= b['start'] + .001, (a, b)
    for asset in ['assets/generated/bosston-pragon.png', 'assets/bgm.wav', 'assets/gsap.min.js', 'assets/fonts/NotoSerifCJKsc-Regular.otf']:
        if not (ROOT / asset).is_file():
            raise FileNotFoundError(asset)
    audio_map = read_json('audiomap.json', {})
    motion_assets = read_json('motion-assets.json', {}).get('clips', {})
    if not preview and len(motion_assets) < 6:
        raise RuntimeError('The cinematic revision requires at least six reviewed moving-footage assets; use --draft only for proofing.')
    scenes = scene_plan(captions, motion_assets, audio_map)
    if not preview and any(s['media'] != 'video' for s in scenes):
        raise RuntimeError('Every shot in this cinematic delivery requires reviewed moving footage.')
    for source in {s['src'] for s in scenes if s['media'] == 'video'}:
        if not (ROOT / source).is_file():
            raise FileNotFoundError(f'Missing staged motion source: {source}')
    (ROOT / 'scene-plan.json').write_text(json.dumps(scenes, indent=2), encoding='utf-8')
    data = {'duration': DURATION, 'fps': FPS, 'revision': 2, 'scenes': scenes, 'captions': captions,
            'assets': {'brand': 'assets/generated/bosston-pragon.png'}, 'motionAssets': motion_assets, 'audioMap': audio_map, 'beats': []}
    (ROOT / 'film-data.js').write_text('window.FILM_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n', encoding='utf-8')
    cues = []
    for i, c in enumerate(captions):
        text = html.escape(c['text'])
        cues.append(f'<div id="lyric-{i:03}" class="clip lyric" data-start="{c["start"]:.3f}" data-duration="{c["end"]-c["start"]:.3f}" data-track-index="8" data-track-kind="captions"><span class="lyric-inner">{text}</span></div>')
    videos = []
    for shot in scenes:
        if shot['media'] != 'video':
            continue
        ident = shot['id']
        videos.append(f'<div id="footage-{ident}" class="footage-window" data-layout-ignore>'
                      f'<video id="video-{ident}" class="clip" src="{shot["src"]}" muted playsinline '
                      f'data-start="{shot["start"]:.6f}" data-duration="{shot["end"]-shot["start"]:.6f}" '
                      f'data-media-start="{shot["source_at"]:.6f}" data-playback-rate="{shot["rate"]}" '
                      f'data-track-index="2" style="object-position:{shot["crop"]}"></video></div>')
    template = (ROOT / 'index.html.in').read_text(encoding='utf-8')
    generated = template.replace('<!-- LYRIC_CUES -->', '\n'.join(cues)).replace('<!-- MOTION_FOOTAGE -->', '\n'.join(videos))
    (ROOT / 'index.html').write_text(generated, encoding='utf-8')
    storyboard = ['# BOSSTON | Pragon — vocal-led edit', '',
                  'Revision 2 uses moving footage and physical 3D shots. The original WAV runs for 185 seconds, with the preserved vocal cue clock. Measured transients refine nearby cuts; no invented BPM.', '',
                  '| Shot | Seconds | Section | Moving subject / camera | Entry |', '| --- | --- | --- | --- | --- |']
    for s in scenes:
        storyboard.append(f'| {s["id"]} | {s["start"]:.3f}–{s["end"]:.3f} | {s["section"]} | {s.get("video",s["world"])} / {s["media"]} / {s["motion"]} | {s["transition"]} |')
    (ROOT / 'STORYBOARD.md').write_text('\n'.join(storyboard) + '\n', encoding='utf-8')
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT / 'assets').rglob('*') if p.is_file()}
    (ROOT / 'asset-hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(f'Built {len(scenes)} shots / {len(captions)} vocal cues / {int(DURATION * FPS)} frames. Preview-only: {preview}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--draft', action='store_true', help='Allow incomplete motion sourcing for preview only.')
    parser.add_argument('--preview-without-captions', action='store_true')
    args = parser.parse_args()
    build(args.draft or args.preview_without_captions)

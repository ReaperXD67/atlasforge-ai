"""Compile the full-song AI-art cinematic edit without changing vocal timing."""
from __future__ import annotations

import hashlib
import html
import json
import re
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DURATION = 185.0
FPS = 30

# Authored musical phrases, not a fabricated beat grid. Every original AI world
# returns with a different shot scale; ten new worlds expand the visual story.
SHOTS = [
    (0, 'star-gong'), (2.14, 'drums'), (5.8, 'avenue'),
    (9.72, 'lantern-river'), (13.18, 'silk-tunnel'), (17.8, 'palace-garden'),
    (22.9, 'avenue'), (25.04, 'palace-garden'), (28.9, 'unity-gate'),
    (32.24, 'ribbon'), (34.02, 'bridge'), (37.92, 'ribbon'),
    (41.66, 'lotus-gate'), (46.6, 'star-gong'), (49, 'dragon'),
    (52.9, 'dragon-close'), (56.48, 'fortune-forge'), (60.36, 'phoenix-sky'),
    (64.96, 'silk-tunnel'), (66, 'sunrise'), (69.66, 'palace-garden'),
    (73.34, 'koi'), (77.12, 'koi-cosmos'), (80.72, 'lantern-river'),
    (84.52, 'unity-gate'), (89.64, 'star-gong'), (92, 'dragon-close'),
    (95.66, 'dragon'), (99.18, 'fortune-forge'), (103.06, 'phoenix-sky'),
    (107.32, 'silk-tunnel'), (111.5, 'lotus-gate'), (115.6, 'palace-garden'),
    (119.58, 'star-gong'), (123.28, 'fortune-forge'), (126.94, 'palace-garden'),
    (130.64, 'unity-gate'), (132.44, 'ribbon'), (136.64, 'silk-tunnel'),
    (139.88, 'dragon-close'), (141.66, 'phoenix-sky'), (145.26, 'dragon'),
    (147.08, 'lotus-gate'), (150.74, 'sunrise'), (155.14, 'star-gong'),
    (156.26, 'fortune-forge'), (159.6, 'palace-garden'), (163.34, 'koi-cosmos'),
    (166.18, 'dragon-close'), (169.02, 'unity-gate'), (172.86, 'phoenix-sky'),
    (176.4, 'sunrise'),
]


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def section_at(t):
    return next(name for end, name in [
        (22.9, 'intro'), (37.92, 'verse-1'), (49, 'pre-chorus'),
        (66, 'chorus'), (80.72, 'verse-2'), (92, 'pre-chorus'),
        (108, 'chorus'), (119.58, 'instrumental'), (139.88, 'bridge'),
        (156.26, 'final-chorus'), (176.4, 'outro'), (185.01, 'ending'),
    ] if t < end)


def build():
    captions = read_json('captions.json')
    assert len(captions) == 71
    wrong = re.compile(r'(?<![A-Za-z])boston(?![A-Za-z])', re.I)
    texts = [(ROOT / 'lyrics.txt').read_text(encoding='utf-8')]
    texts += [c['text'] for c in captions]
    texts += [w['text'] for c in captions for w in c.get('words', [])]
    if any(wrong.search(text) for text in texts):
        raise ValueError('Production brand spelling must be Bosston (double s).')
    for cue in captions:
        assert 0 <= cue['start'] < cue['end'] <= DURATION
    assets = read_json('ai-assets.json')['assets']
    depth_manifest = read_json('ai-depths.json')
    depths = depth_manifest['depths']
    assert set(assets) == set(depths) and len(assets) == 17
    for ident, path in assets.items():
        source = ROOT / path
        depth = depths[ident]
        assert source.is_file() and (ROOT / depth['path']).is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == depth['source_sha256']
        assert hashlib.sha256((ROOT / depth['path']).read_bytes()).hexdigest() == depth['depth_sha256']
    water = {'koi', 'koi-cosmos', 'lantern-river', 'lotus-gate'}
    silk = {'ribbon', 'silk-tunnel'}
    lanterns = {'avenue', 'palace-garden'}
    dragons = {'dragon', 'dragon-close', 'phoenix-sky'}
    scenes = []
    for i, ((start, asset), (end, _)) in enumerate(pairwise(SHOTS + [(DURATION, '')])):
        section = section_at(start)
        world = ('water' if asset in water else 'silk' if asset in silk else
                 'lanterns' if asset in lanterns else 'dragon' if asset in dragons else 'clouds')
        length = end - start
        # Sustained travel has nonzero, same-sign X/Z velocity across every seam.
        # Overscan covers the camera offset + conservative depth displacement.
        zoom = 1.15 + (i % 3) * .018
        x = -.022
        y = -.007 + (i % 3) * .007
        transition = 'cut'
        if i and asset in silk:
            transition = 'silk-wipe'
        elif i and start in {49, 92, 139.88, 156.26, 176.4}:
            transition = 'light-leak'
        cue = next((c for c in captions if c['start'] <= start + .03 < c['end']), None)
        scenes.append({
            'id': f'ai-shot-{i + 1:02}', 'start': start, 'end': end,
            'media': 'ai-depth', 'asset': asset, 'world': world, 'section': section,
            'motion': 'continuous-dolly', 'cameraEase': 'linear',
            'cameraFrom': [x, y, round(zoom, 4), -.0015],
            'cameraTo': [round(x + .008 * length, 5), y,
                         round(zoom + .016 * length, 5), .0015],
            'parallax': 1.05, 'flow': 1.05 if asset in water | silk else .85,
            'dof': .45, 'focusDepth': .48, 'exposure': 1,
            'atmosphere': .55, 'celebration': section == 'final-chorus',
            'transition': transition, 'transitionDuration': .3 if transition == 'silk-wipe' else .2,
            'seed': 1811 + i * 37, 'lyric': cue['text'] if cue else '',
        })
    for a, b in pairwise(scenes):
        assert a['end'] == b['start']
    data = {'duration': DURATION, 'fps': FPS, 'revision': 3,
            'mediaMode': 'ai-depth-cinema', 'requireDepth': True,
            'scenes': scenes, 'captions': captions, 'assets': assets, 'depths': depths,
            'audioMap': read_json('audiomap.json'), 'beats': []}
    (ROOT / 'scene-plan.json').write_text(json.dumps(scenes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'film-data.js').write_text('window.FILM_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n', encoding='utf-8')
    cues = []
    for i, c in enumerate(captions):
        cues.append(f'<div id="lyric-{i:03}" class="clip lyric" data-start="{c["start"]:.3f}" '
                    f'data-duration="{c["end"]-c["start"]:.3f}" data-track-index="8" '
                    f'data-track-kind="captions"><span class="lyric-inner">{html.escape(c["text"])}</span></div>')
    markers = [f'<div id="{s["id"]}" class="clip shot-marker" data-start="{s["start"]:.3f}" '
               f'data-duration="{s["end"]-s["start"]:.3f}" data-track-index="2" '
               f'data-track-kind="graphics" data-layout-ignore><span>{s["asset"]}</span></div>' for s in scenes]
    template = (ROOT / 'index_ai.html.in').read_text(encoding='utf-8')
    (ROOT / 'index.html').write_text(template.replace('<!-- LYRIC_CUES -->', '\n'.join(cues))
                                   .replace('<!-- AI_SHOT_MARKERS -->', '\n'.join(markers)), encoding='utf-8')
    ledger = {'renderer': 'custom WebGL shader', 'gate': 'verify_ai_motion.mjs',
              'note': 'The upstream POSIX DOM seam gate does not validate this shader.',
              'seams': [{'at': b['start'], 'from': a['id'], 'to': b['id'],
                         'transition': b['transition'], 'x_velocity': .008, 'zoom_velocity': .016,
                         'same_direction': True} for a, b in pairwise(scenes)]}
    (ROOT / 'motion-ledger.json').write_text(json.dumps(ledger, indent=2) + '\n', encoding='utf-8')
    storyboard = ['# BOSSTON | Pragon — AI cinematic edit', '',
                  '17 AI artworks, 52 authored shots, inferred depth and continuous lens travel. '
                  'The original 185-second song and all 71 lyric timings are preserved. '
                  'This is animated AI artwork, not native generated-video footage.', '',
                  '| Shot | Seconds | Section | AI world | Entry |', '| --- | --- | --- | --- | --- |']
    storyboard += [f'| {s["id"]} | {s["start"]:.2f}–{s["end"]:.2f} | {s["section"]} | {s["asset"]} | {s["transition"]} |' for s in scenes]
    (ROOT / 'STORYBOARD.md').write_text('\n'.join(storyboard) + '\n', encoding='utf-8')
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT / 'assets').rglob('*') if p.is_file()}
    (ROOT / 'asset-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    print(f'Built AI cinema: {len(scenes)} shots, {len(assets)} artworks/depths, {len(captions)} preserved cues, {int(DURATION * FPS)} frames.')


if __name__ == '__main__':
    build()

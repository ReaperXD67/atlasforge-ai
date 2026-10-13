"""Package local approved assets and measured lyrics for the deterministic film."""
from pathlib import Path
import argparse
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = {
    'cathedral': '01-obsidian-cathedral.png',
    'stairs': '02-ocean-stairway.png',
    'lily': '03-cosmic-blue-lily.png',
    'garden': '04-ocean-of-blue-lilies.png',
    'moon': '05-shattered-moon.png',
    'intimate': '06-couple-rain-garden.png',
}
MOTION = [
    ('stairs-a', '08-ocean-stairway-wan-motion.mp4', 37.9, 5, .6, 2),
    ('stairs-b', '08-ocean-stairway-wan-motion.mp4', 76.6, 5, .6, 2),
    ('stairs-c', '08-ocean-stairway-wan-motion.mp4', 164.8, 5, .6, 2),
    ('moon-a', '09-shattered-moon-wan-motion.mp4', 69.9, 5, .8, 3),
    ('moon-b', '09-shattered-moon-wan-motion.mp4', 186.5, 4.9, .8, 3),
    ('moon-c', '09-shattered-moon-wan-motion.mp4', 263.6, 5.7, .8, 3),
    ('lily-a', '07-blue-lily-wan-motion.mp4', 136, 5.1, .55, 4),
    ('lily-b', '07-blue-lily-wan-motion.mp4', 325.3, 5.2, .55, 4),
    ('garden-a', '10-blue-lily-ocean-wan-motion-deflicker.mp4', 287.9, 6.2, .7, 5),
    ('garden-b', '10-blue-lily-ocean-wan-motion-deflicker.mp4', 332.6, 6.2, .7, 5),
]


def prepare(assets: Path, analysis: Path):
    destination = ROOT / 'assets/generated'
    destination.mkdir(parents=True, exist_ok=True)
    for name in NAMES.values():
        source = assets / name
        if not source.is_file():
            raise FileNotFoundError(f'Required approved plate missing: {source}')
        shutil.copy2(source, destination / name)
    for name in {m[1] for m in MOTION}:
        source = assets / name
        if not source.exists():
            raise FileNotFoundError(f'Required approved motion clip missing: {source}')
        shutil.copy2(source, destination / name)
    clips = []
    for ident, name, start, duration, rate, track in MOTION:
        clips.append(f'<div id="motion-{ident}" class="motion-window" data-layout-ignore>'
                     f'<video id="{ident}" class="clip" src="assets/generated/{name}" muted playsinline '
                     f'data-start="{start}" data-duration="{duration}" data-playback-rate="{rate}" '
                     f'data-track-index="{track}"></video></div>')
    block = '<!-- MOTION INSERTS -->\n' + '\n'.join(clips) + '\n<!-- END MOTION INSERTS -->'
    index = ROOT / 'index.html'
    html = index.read_text(encoding='utf-8')
    if '<!-- MOTION INSERTS -->' in html:
        html = re.sub(r'<!-- MOTION INSERTS -->.*?<!-- END MOTION INSERTS -->', lambda _: block, html, flags=re.S)
    else:
        html = html.replace('</canvas>', '</canvas>\n' + block, 1)
    index.write_text(html, encoding='utf-8')
    for name in ('captions.json', 'captions.srt', 'audiomap.json'):
        source = analysis / name
        if source.exists():
            shutil.copy2(source, ROOT / name)
    captions = json.loads((ROOT / 'captions.json').read_text(encoding='utf-8'))
    if isinstance(captions, dict):
        captions = captions.get('lines', captions.get('captions', []))
    for line in captions:
        assert 0 <= line['start'] < line['end'] <= 372.76, line
        assert line['text'].strip(), line
    assert captions, 'No measured subtitles'
    scenes = json.loads((ROOT / 'scene-plan.json').read_text())
    assert scenes[0]['start'] == 0 and scenes[-1]['end'] == 372.76
    for previous, current in zip(scenes, scenes[1:]):
        assert previous['end'] == current['start'], 'Gap or overlap in scene plan'
    data = {'duration': 372.76, 'scenes': scenes, 'captions': captions,
            'assets': {k: 'assets/generated/' + v for k, v in NAMES.items()}}
    data['assets']['original'] = 'assets/private/couple.jpg'
    data['audioMap'] = json.loads((ROOT / 'audiomap.json').read_text(encoding='utf-8'))
    (ROOT / 'film-data.js').write_text('window.FILM_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n', encoding='utf-8')
    print(f'Packaged {len(scenes)} shots, {len(captions)} measured captions, {len(NAMES)} generated plates.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, default=REPO / 'output/sweetheart-assets')
    parser.add_argument('--analysis', type=Path, default=REPO / 'output/sweetheart-analysis')
    args = parser.parse_args()
    prepare(args.assets, args.analysis)

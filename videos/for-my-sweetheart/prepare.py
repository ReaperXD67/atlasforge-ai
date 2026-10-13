"""Package local approved assets and measured lyrics for the deterministic film."""
from pathlib import Path
import argparse
import json
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


def prepare(assets: Path, analysis: Path):
    destination = ROOT / 'assets/generated'
    destination.mkdir(parents=True, exist_ok=True)
    for name in NAMES.values():
        source = assets / name
        if not source.is_file():
            raise FileNotFoundError(f'Required approved plate missing: {source}')
        shutil.copy2(source, destination / name)
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

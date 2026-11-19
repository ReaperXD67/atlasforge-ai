"""Author the natural-setting Seedance V3 cut against the frozen song clock.

This EDL uses named clips and declared usable intervals/crops, so authoring does
not imply admission of unfinished media. The renderer validates files/reviews.
No rejected V2 Hock interpretation or generated identity anchor enters this EDL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FPS = 24
DURATION = 196.760
HEROES = {
    'hock-room-close', 'hock-room-medium', 'hock-window', 'hock-tea',
    'hock-doorway', 'hock-boat-wide', 'hock-boat-close', 'hock-waterfront',
}
CONTEXT = {
    'context-water', 'context-rain', 'context-tea', 'context-waterfront',
    'context-trees', 'context-table', 'sea-dawn', 'wet-footsteps',
}
RANGES = {ident: (.2, 9.8) for ident in HEROES | CONTEXT}
RANGES['wet-footsteps'] = (.2, 9.75)
# The original ten-second medium take clipped the head and is excluded. This
# alias now resolves to the five-second repaired source, including safe edges.
RANGES['hock-room-medium'] = (.2, 4.8)
MANDATORY_CROPS = {
    'hock-boat-wide': {'x': 0, 'y': 0, 'width': 1280, 'height': 720},
    'hock-window': {'x': 80, 'y': 0, 'width': 1600, 'height': 900},
    'hock-waterfront': {'x': 0, 'y': 0, 'width': 1280, 'height': 720},
    'hock-doorway': {'x': 600, 'y': 0, 'width': 704, 'height': 396},
    'context-tea': {'x': 540, 'y': 270, 'width': 720, 'height': 405},
}

# Phrase-flow editing: most shots breathe for four to seven seconds. The few
# shorter chorus turns are attached to vocal phrases rather than effects.
CUTS = [
    (0, 'hock-boat-close', 'A moving seaside portrait introduces Hock Siew beneath the title'),
    (3.75, 'hock-room-close', 'Meet Hock Siew in a quiet close portrait'),
    (8, 'context-water', 'Moving water opens the story into an ordinary horizon'),
    (13, 'context-rain', 'Soft rain outside the same modest room gives a lived-in atmosphere'),
    (18.4, 'hock-room-medium', 'His real build and white shirt establish the single recipient'),
    (22.30, 'hock-doorway', 'The first meeting begins with the man being honoured'),
    (29.54, 'hock-room-close', 'The full name is sung over Hock Siew himself'),
    (33.02, 'context-trees', 'Ordinary daylight and leaves provide a gentle breath'),
    (36.90, 'hock-window', 'A calm listening moment carries the lyric about a generous heart'),
    (43.48, 'context-table', 'Two cups at a shared table suggest care without a substitute face'),
    (47.56, 'wet-footsteps', 'The rain detail gives the journey a physical, ordinary texture'),
    (51.66, 'context-waterfront', 'An unadorned waterfront links people and distance'),
    (57.90, 'wet-footsteps', 'A brief physical rain detail anticipates the line about obstacles'),
    (62.34, 'hock-room-medium', 'Return to the recipient as the lyric speaks of sharing burdens'),
    (66, 'context-tea', 'A practical cup and steady pouring stream represent quiet generosity'),
    (69.46, 'hock-doorway', 'His presence carries the promise kept in the heart'),
    (73.40, 'context-tea', 'The cup detail completes as concern becomes a shared everyday ritual'),
    (77.10, 'hock-window', 'The passage of years returns to a steady personal portrait'),
    (81.04, 'hock-boat-close', 'The first Hock Siew chorus call belongs to his face'),
    (84.92, 'hock-boat-wide', 'The real seaside setting opens around the person'),
    (88.64, 'hock-room-medium', 'The indoor portrait connects the promise of walking together'),
    (90.42, 'hock-boat-close', 'The second name call returns to the same recipient'),
    (94.34, 'context-water', 'Water continues physically under the flowing-friendship lyric'),
    (97.14, 'hock-waterfront', 'His presence carries the wish outward without changing into a new lead'),
    (103, 'context-tea', 'The instrumental completes the ordinary cup ritual through fresh source time'),
    (105.46, 'context-trees', 'Leaves and daylight provide a short musical breath'),
    (107.04, 'sea-dawn', 'A natural water texture gives the instrumental space'),
    (111.20, 'context-trees', 'Leaves and ordinary sunlight answer the instrumental rise'),
    (115.30, 'context-rain', 'The room-side rain detail resolves through a fresh source interval'),
    (119.42, 'hock-room-medium', 'The bridge begins beside the person receiving the thanks'),
    (123.20, 'hock-tea', 'Quiet company turns gratitude into a blessing'),
    (128.70, 'hock-window', 'Soft natural light and a restrained smile carry the wish for health'),
    (133.96, 'context-table', 'A remembered small deed is shown through hands rather than another male face'),
    (138.90, 'hock-tea', 'Hock Siew and the cup are present before the sung toast'),
    (144.74, 'hock-doorway', 'The unchanged bond returns to a familiar, ordinary place'),
    (149.32, 'hock-boat-wide', 'The final name chorus opens on the single recipient'),
    (154.80, 'hock-room-close', 'His full name and the respect lyric stay with his face'),
    (158.40, 'hock-boat-close', 'The final Hock Siew call returns to his face in the original seaside setting'),
    (160.44, 'context-water', 'A compact water accent supports the promise of a lasting bond'),
    (162.10, 'hock-window', 'The final wish for peace stays with the honouree'),
    (164.08, 'hock-waterfront', 'The sustained final vocal holds a calm personal moment'),
    (170.10, 'hock-boat-wide', 'A quiet moving release follows the final sung phrase'),
    (176, 'sea-dawn', 'The water horizon continues using a different source interval'),
    (181.40, 'context-waterfront', 'The ordinary waterfront settles before the original photograph'),
]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author():
    cues = read_json(ROOT / 'captions.json')
    closing = round((DURATION - 12) * FPS)
    starts = [round(at * FPS) for at, _, _ in CUTS]
    for i, (at, ident, _) in enumerate(CUTS):
        if ident in HEROES and any(
            any(name in cue['text'] for name in ('Hock Siew', '谢惠福'))
            and abs(cue['start'] - at) < .01 for cue in cues
        ):
            starts[i] = math.floor(at * FPS)
    ends = starts[1:] + [closing]
    shots, cursors, source_windows = [], {}, {}
    for i, ((_, ident, description), start, end) in enumerate(zip(CUTS, starts, ends, strict=True)):
        shot = {'id': f'v3-shot-{i + 1:02}', 'start_frame': start,
                'end_frame': end, 'description': description}
        length = (end - start) / FPS
        if ident == 'photo-seaside':
            shot.update(kind='photo', path='assets/photos/seaside.jpg',
                        identity='hock_siew', layout='left')
        else:
            lower, upper = RANGES[ident]
            at = cursors.get(ident, lower)
            if i == 0 and ident == 'hock-boat-close':
                # This frame/interval has been reviewed with the right-side
                # title over clear water, leaving the recipient unobstructed.
                at = 2.0
            if at + length > upper + .000001:
                if ident not in HEROES:
                    raise ValueError(f'{ident}: would replay contextual source time')
                # Use the still-unseen tail before replaying already shown time.
                # Once exhausted, a centred return avoids a literal whole-take loop.
                if ident == 'hock-boat-close':
                    # The reviewed opening starts at2s, leaving a genuine new
                    # leading interval for the first later chorus return.
                    first_used = min(a for a, _, _ in source_windows[ident])
                    at = lower if first_used > lower + .000001 else upper - length
                else:
                    at = upper - length if at < upper - .000001 else lower + (upper - lower - length) / 2
                cursors[ident] = upper
            else:
                cursors[ident] = at + length
            overlaps = [origin for lo, hi, origin in source_windows.get(ident, [])
                        if min(at + length, hi) - max(at, lo) > .000001]
            if overlaps:
                if ident not in HEROES:
                    raise ValueError(f'{ident}: repeated contextual source time')
                shot.update(reprise_of=overlaps[0],
                            reprise_reason='Declared non-adjacent recipient motif across musical sections; no new identity or motion is claimed.')
            shot.update(kind='native', clip=ident, source_at=at, rate=1.0,
                        context_only=ident in CONTEXT)
            if ident in MANDATORY_CROPS:
                # Reviewed crops preserve the complete face/headroom while
                # excluding unsupported watch/ring/chest details.
                shot['crop'] = dict(MANDATORY_CROPS[ident])
            source_windows.setdefault(ident, []).append((at, at + length, shot['id']))
        shots.append(shot)
    shots.append({'id': 'v3-closing-memory', 'kind': 'photo',
                  'path': 'assets/photos/seaside.jpg', 'identity': 'hock_siew',
                  'layout': 'left', 'closing': True, 'start_frame': closing,
                  'end_frame': math.ceil(DURATION * FPS),
                  'description': 'The supplied original seaside photograph closes with the Mandarin dedication'})
    plan = {
        'revision': 3, 'duration_seconds': DURATION, 'fps': FPS,
        'frames': math.ceil(DURATION * FPS), 'closing_start': closing / FPS,
        'shots': shots, 'audio_sha256': digest(ROOT / 'assets/bgm.wav'),
        'captions_sha256': digest(ROOT / 'captions.json'),
        'editorial_method': 'Natural-setting full-song tribute: original photos, Seedance recipient shots, fresh face-free context, normal-speed native motion and declared non-adjacent recipient reprises.',
        'media_admission': 'Declared usable source ranges and mandatory reviewed crops; final renderer requires actual reviewed sources and hashes.',
        'intro_text': {'start': .3, 'end': 3.6},
        'memory_labels': [],
    }
    plan['identity_coverage'] = validate(plan, cues)
    return plan


def validate(plan, cues):
    cursor, history, windows = 0, {}, {}
    hero_seconds = photo_seconds = native_seconds = 0.0
    for i, shot in enumerate(plan['shots']):
        if shot['start_frame'] != cursor or shot['end_frame'] <= cursor or shot['id'] in history:
            raise ValueError('EDL has a gap, overlap or repeated shot ID')
        length = (shot['end_frame'] - cursor) / FPS
        if shot['kind'] == 'photo':
            photo_seconds += length
            if not (ROOT / shot['path']).is_file():
                raise ValueError('Original photo missing')
        else:
            native_seconds += length
            ident = shot['clip']
            a, b = shot['source_at'], shot['source_at'] + length
            lo, hi = RANGES[ident]
            if a < lo - .000001 or b > hi + .000001:
                raise ValueError(f'{ident}: interval leaves provisional trim')
            if ident in MANDATORY_CROPS and shot.get('crop') != MANDATORY_CROPS[ident]:
                raise ValueError(f'{ident}: reviewed safety crop must be retained')
            overlapping = [(max(a, x), min(b, y), sid) for x, y, sid in windows.get(ident, [])
                           if min(b, y) - max(a, x) > .000001]
            if overlapping:
                origin = history.get(shot.get('reprise_of'))
                if ident not in HEROES or not origin or origin[1]['clip'] != ident or i - origin[0] < 2 or not shot.get('reprise_reason'):
                    raise ValueError(f'{ident}: replay needs a non-adjacent earlier recipient shot and reason')
            windows.setdefault(ident, []).append((a, b, shot['id']))
            if ident in HEROES:
                hero_seconds += length
        history[shot['id']] = (i, shot)
        cursor = shot['end_frame']
    if cursor != math.ceil(DURATION * FPS):
        raise ValueError('EDL must tile the complete song')
    for cue in cues:
        if any(name in cue['text'] for name in ('Hock Siew', '谢惠福')):
            for shot in plan['shots']:
                if shot['end_frame'] / FPS > cue['start'] + .000001 and shot['start_frame'] / FPS < cue['end'] - .000001:
                    if shot['kind'] != 'photo' and shot['clip'] not in HEROES:
                        raise ValueError(f"{shot['id']}: the complete named lyric must show Hock Siew")
    unique = 0.0
    for intervals in windows.values():
        merged = []
        for a, b, _ in sorted(intervals):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(b, merged[-1][1])
            else:
                merged.append([a, b])
        unique += sum(b - a for a, b in merged)
    return {
        'recognisable_recipient_seconds': round(hero_seconds + photo_seconds, 3),
        'recognisable_recipient_fraction': round((hero_seconds + photo_seconds) / DURATION, 4),
        'native_motion_seconds': round(native_seconds, 3),
        'original_photo_seconds': round(photo_seconds, 3),
        'distinct_native_source_seconds': round(unique, 3),
        'reused_native_source_seconds': round(native_seconds - unique, 3),
        'intentional_reprises': sum(bool(s.get('reprise_of')) for s in plan['shots']),
        'named_lyric_coverage': 'All complete name-containing cues show the recipient, subject to source admission.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    plan = author()
    if args.write:
        (ROOT / 'edit-plan-v3.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'shots': len(plan['shots']), 'frames': plan['frames'],
                      'coverage': plan['identity_coverage']}, ensure_ascii=False, indent=2))

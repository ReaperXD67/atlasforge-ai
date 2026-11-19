"""Write the phrase-aware source edit after the native takes are admitted.

The table is an editorial decision, not a generated slideshow. Each return to a
take consumes a later source interval; the recording and measured captions keep
their original clock. Re-running is explicit because edit-plan.json is editable.
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict

from prepare_film import FPS, ROOT, load_clips, probe, read_json, sha256, validate_plan, write_json

# Start seconds, admitted source ID, musical/story relationship. Scene changes
# use phrase openings and instrumental breaths; they do not restart a video.
CUTS = [
    (0.00, 'sea-journey', 'A journey begins: moving water and an open horizon'),
    (4.60, 'sea-dawn', 'Morning light and water establish the coastal world'),
    (9.10, 'wet-footsteps', 'A human rhythm enters the rain'),
    (13.40, 'rain-arrival', 'Friends move toward the same doorway'),
    (17.90, 'open-door', 'Warmth and welcome before the first vocal'),
    (22.30, 'warm-conversation', 'The day and place where friendship began'),
    (27.50, 'shoulder-support', 'A name held with respect and companionship'),
    (32.76, 'hands-help', 'A visible hand offered with practical care'),
    (37.90, 'shared-table', 'There is room for everyone at the table'),
    (42.90, 'shoulder-support', 'Respect grows from everyday gestures'),
    (47.56, 'warm-conversation', 'Return to the warmth behind the friendship'),
    (51.66, 'community-boxes', 'Sincerity becomes action in the community'),
    (56.80, 'packing-table', 'Hands prepare help for someone else'),
    (61.10, 'hands-help', 'A later moment of the same completed helping action'),
    (64.20, 'burden-shared', 'The weight is shared between friends'),
    (69.46, 'covered-path', 'Care continues through ordinary weather'),
    (75.10, 'rain-arrival', 'A later stage of the journey together'),
    (81.04, 'joined-hands', 'The first chorus gathers the circle'),
    (85.30, 'workshop-team', 'Togetherness expressed through shared work'),
    (89.40, 'sea-dawn', 'Flowing water carries the long-lived friendship'),
    (94.34, 'workshop-team', 'Shared effort links the community'),
    (97.14, 'sea-journey', 'The horizon opens as sincerity travels farther'),
    (103.00, 'wet-footsteps', 'Instrumental breath: a later ripple and footstep'),
    (107.10, 'open-door', 'The doorway opens farther into warmth'),
    (111.20, 'covered-path', 'The path continues in one direction'),
    (115.30, 'burden-shared', 'The work reaches its later payoff'),
    (119.42, 'shared-table', 'The brothers gather close for the blessing'),
    (124.20, 'tea-pour', 'A quiet act of care accompanies the wishes'),
    (129.00, 'passing-kindness', 'The original kindness passes onward'),
    (133.96, 'packing-table', 'Small deeds are remembered one by one'),
    (138.90, 'tea-pour', 'The cup and toast meet the lyric about the bond'),
    (144.74, 'community-boxes', 'The lasting friendship continues through action'),
    (149.32, 'joined-hands', 'The final chorus returns to the united circle'),
    (153.20, 'passing-kindness', 'The helping hand is now offered by others'),
    (157.00, 'open-shutters', 'New light arrives as the name is celebrated'),
    (160.33, 'through-storm', 'Shared weather meets the storm-and-loyalty line'),
    (164.08, 'dawn-brothers', 'The long final phrase walks into the horizon'),
    (171.20, 'open-shutters', 'Instrumental release into the morning before the real memory'),
    (177.80, 'photo-brothers', 'Accepted native animation of the supplied group memory'),
]


def author():
    clips = load_clips()
    cues = read_json(ROOT / 'captions.json')
    duration = float(probe(ROOT / 'assets/bgm.wav')['format']['duration'])
    closing_frame = round((duration - 12) * FPS)
    total_frames = math.ceil(duration * FPS)
    starts = [round(start * FPS) for start, _, _ in CUTS]
    ends = starts[1:] + [closing_frame]
    required = {ident for _, ident, _ in CUTS}
    if not required <= clips.keys():
        raise ValueError(f'Missing admitted editorial sources: {sorted(required - clips.keys())}')
    if abs(cues[0]['start'] - 22.30) > .05 or abs(cues[-1]['end'] - 170.10) > .05:
        raise ValueError('The measured vocal clock changed; review this authored sequence first.')
    totals = defaultdict(int)
    for (_, ident, _), start, end in zip(CUTS, starts, ends, strict=True):
        totals[ident] += end - start
    rates, cursors = {}, {}
    for ident, frames in totals.items():
        interval = clips[ident]['usable_range']
        available = interval['end'] - interval['start']
        rates[ident] = min(1.0, available / (frames / FPS))
        if rates[ident] < .8:
            raise ValueError(f'{ident}: not enough admitted movement for its two editorial windows.')
        cursors[ident] = interval['start']
    shots = []
    for index, ((_, ident, description), start, end) in enumerate(zip(CUTS, starts, ends, strict=True)):
        shots.append({'id': f'shot-{index + 1:02}', 'kind': 'native', 'clip': ident,
                      'start_frame': start, 'end_frame': end, 'source_at': cursors[ident],
                      'rate': rates[ident], 'description': description})
        cursors[ident] += (end - start) / FPS * rates[ident]
    shots.append({'id': 'closing-memory', 'kind': 'photo', 'path': 'assets/photos/seaside.jpg',
                  'start_frame': closing_frame, 'end_frame': total_frames,
                  'description': 'Unretouched supplied seaside photograph with local Mandarin dedication'})
    plan = {'revision': 2, 'duration_seconds': duration, 'fps': FPS, 'frames': total_frames,
            'closing_start': closing_frame / FPS,
            'source_mode': 'native-ai-video-and-supplied-memory',
            'editorial_method': 'Phrase-aware section order; unique chronological source intervals; real memory bookend',
            'shots': shots, 'captions_sha256': sha256(ROOT / 'captions.json'),
            'audio_sha256': sha256(ROOT / 'assets/bgm.wav'),
            'closing_message': '有你，兄弟同心。愿你平安，幸福永久。'}
    validate_plan(plan, clips, cues, duration)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Replace the editable edit-plan.json with this authored sequence')
    args = parser.parse_args()
    edit = author()
    if args.write:
        write_json(ROOT / 'edit-plan.json', edit)
    print(f'{len(edit["shots"])} shots, {edit["frames"]} frames, original photo from {edit["closing_start"]:.6f}s')

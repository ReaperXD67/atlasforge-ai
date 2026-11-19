"""Author the personal V2 cut after native likeness and context crops are admitted.

Context aliases resolve through v2-context-selections.json. Each alias may be a
single selection or a list of alternatives. Context source time is consumed
once; protagonist reprises are deliberate and labelled in the resulting EDL.
"""
from __future__ import annotations

import argparse
import math

from prepare_film import probe, read_json, sha256, write_json
from prepare_film_v2 import FPS, ROOT, load_clips, validate_plan

CUTS = [
    (0, 'hock-seaside', 'Meet the one recipient in a recognisable moving portrait'),
    (6, 'sea-dawn', 'An open horizon between the opening portrait and journey'),
    (10, 'hock-walk', 'Hock Siew carries the story forward'),
    (15, 'wet-footsteps', 'Rain becomes a concise physical detail'),
    (18, 'photo-brothers', 'A centred moving portrait from the authentic supplied group photograph anchors the first verse'),
    (22.30, 'hock-doorway', 'A meaningful meeting begins with Hock Siew'),
    (29.54, 'hock-seaside', 'Show the named recipient as his full name is sung'),
    (33.02, 'detail-hands', 'A brief anonymous detail of help, without a substitute face'),
    (36.90, 'hock-window', 'A spacious pause around the warmth he offers'),
    (43.48, 'hock-tea', 'Quiet attention and familiar company'),
    (47.56, 'detail-packing', 'Care appears through useful hands'),
    (51.66, 'detail-box', 'A box passes forward; the people remain contextual'),
    (58.18, 'detail-rain', 'Weather and the shared burden as a short detail'),
    (62.34, 'hock-walk', 'Return to the protagonist rather than a new male lead'),
    (66, 'detail-beam', 'A close detail of shared work'),
    (69.46, 'hock-window', 'A thoughtful personal refrain'),
    (73.40, 'detail-cup', 'Small acts of care in a cup and hands'),
    (77.10, 'detail-kindness', 'A short gesture of kindness carries the music into its chorus'),
    (81.04, 'hock-seaside', 'Hock Siew is visibly the person being named'),
    (86.78, 'hock-doorway', 'His presence holds the chorus together'),
    (90.42, 'hock-dawn', 'The second name call returns to his face'),
    (94.34, 'detail-cup', 'A short continuation of kindness'),
    (97.14, 'hock-walk', 'The personal journey carries the lyric farther'),
    (103, 'wet-footsteps', 'Instrumental breath and an evolving ripple'),
    (107.10, 'sea-dawn', 'A new water detail on the instrumental phrase'),
    (111.20, 'detail-work', 'Hands and materials supply a brief rhythmic accent'),
    (115.30, 'detail-rain', 'A concise rain detail, without anonymous male leads'),
    (119.42, 'photo-seaside', 'An authentic personal memory introduces the blessing'),
    (123.20, 'hock-tea', 'The recipient shares a quiet moment of warmth'),
    (129, 'hock-window', 'The blessing remains personal'),
    (133.96, 'detail-packing', 'The remembered small deeds are practical details'),
    (138.90, 'hock-tea', 'Hock Siew and the cup arrive together with the sung toast'),
    (144.74, 'hock-doorway', 'The grateful lyric comes back to its recipient'),
    (149.32, 'hock-dawn', 'A name call in the final chorus belongs to Hock Siew'),
    (152.92, 'detail-hands', 'A brief bridge from kindness to a personal name anchor'),
    (154.80, 'photo-seaside', 'The original photograph meets the full-name dedication'),
    (156.64, 'hock-walk', 'Continue the promise with the same protagonist'),
    (158.40, 'hock-seaside', 'The last name call returns to his face'),
    (160.44, 'detail-rain', 'A compact rain accent under the blessing'),
    (162.10, 'hock-window', 'The last quiet wish remains with him'),
    (164.08, 'hock-dawn', 'His face and the warm horizon hold the final phrase'),
    (170.10, 'hock-walk', 'A forward-looking personal release after the vocal'),
    (177.80, 'sea-dawn', 'The horizon opens before the real-photo ending'),
]


def author():
    clips = load_clips()
    cues = read_json(ROOT / 'captions.json')
    selections = read_json(ROOT / 'v2-context-selections.json')
    duration = float(probe(ROOT / 'assets/bgm.wav')['format']['duration'])
    closing_frame = round((duration - 12) * FPS)
    starts = [round(t * FPS) for t, _, _ in CUTS]
    # A name entering between picture frames belongs to the incoming portrait.
    # Snap the chorus entrance down one frame so even the continuous cue span
    # cannot overlap the preceding anonymous detail.
    for index, (at, alias, _) in enumerate(CUTS):
        if alias.startswith('hock-') and any('Hock Siew' in c['text'] and abs(c['start'] - at) < .01 for c in cues):
            starts[index] = math.floor(at * FPS)
    ends = starts[1:] + [closing_frame]
    cursors, history, source_windows, shots = {}, {}, {}, []

    def native_choice(alias, length):
        if alias.startswith('hock-') or alias == 'photo-brothers':
            return selections.get(alias, {'clip': alias}), True
        candidates = selections.get(alias, {'clip': alias})
        if isinstance(candidates, dict):
            candidates = [candidates]
        for candidate in candidates:
            ident = candidate['clip']
            interval = candidate.get('usable_range', clips[ident]['usable_range'])
            cursor = max(cursors.get(ident, interval['start']), interval['start'])
            if interval['end'] - cursor >= length - .00001:
                return candidate, False
        for candidate in candidates:
            ident = candidate['clip']
            interval = candidate.get('usable_range', clips[ident]['usable_range'])
            if ident == 'sea-dawn' and candidate.get('allow_reprise') and interval['end'] - interval['start'] >= length:
                return candidate, False
        raise ValueError(f'{alias}: no admitted face-free interval has {length:.3f}s remaining.')

    for index, ((_, alias, description), start, end) in enumerate(zip(CUTS, starts, ends, strict=True)):
        length = (end - start) / FPS
        shot = {'id': f'v2-shot-{index + 1:02}', 'start_frame': start, 'end_frame': end,
                'description': description}
        if alias == 'photo-seaside':
            shot.update({'kind': 'photo', 'path': 'assets/photos/seaside.jpg', 'identity': 'hock_siew', 'layout': 'center'})
        else:
            selection, hero = native_choice(alias, length)
            ident = selection['clip']
            interval = selection.get('usable_range', clips[ident]['usable_range'])
            at = max(cursors.get(ident, interval['start']), interval['start'])
            reprise = at + length > interval['end'] + .00001
            if reprise:
                if not (hero or ident == 'sea-dawn' and selection.get('allow_reprise')) or length > interval['end'] - interval['start'] + .00001:
                    raise ValueError(f'{ident}: source is too short for an unbroken native shot.')
                # A deliberate chorus/verse return to a central portrait is a motif.
                at = interval['start'] + (interval['end'] - interval['start'] - length) / 2
                reason = ('Intentional non-adjacent protagonist motif across musical sections; preserves a single recognisable recipient.'
                          if hero else 'Explicit instrumental horizon motif; an evolving native water shot returns between personal scenes.')
                shot.update({'reprise_of': history[ident][0], 'reprise_reason': reason})
            shot.update({'kind': 'native', 'clip': ident, 'source_at': at, 'rate': 1.0,
                         'context_only': not hero})
            overlaps = [origin for lower, upper, origin in source_windows.get(ident, [])
                        if min(at + length, upper) - max(at, lower) > .00001]
            if overlaps and 'reprise_of' not in shot:
                if not hero:
                    raise ValueError(f'{ident}: context source time would be reused.')
                shot.update({'reprise_of': overlaps[0],
                             'reprise_reason': 'Intentional non-adjacent return to the same protagonist portrait across musical sections.'})
            for key in ('crop', 'grade', 'layout'):
                if key in selection:
                    shot[key] = selection[key]
            if ident == 'hock-walk':
                # Preserve forehead space beneath the global cinematic matte.
                # Padding is fully hidden by its76px top bar; no stretch occurs.
                shot['grade'] = ('crop=1920:1010:0:0,pad=1920:1080:0:70:black,'
                                 'unsharp=3:3:0.18:3:3:0,eq=contrast=1.012:saturation=.98')
            cursors[ident] = at + length
            history.setdefault(ident, []).append(shot['id'])
            source_windows.setdefault(ident, []).append((at, at + length, shot['id']))
        shots.append(shot)
    shots.append({'id': 'v2-closing-memory', 'kind': 'photo', 'path': 'assets/photos/seaside.jpg',
                  'identity': 'hock_siew', 'layout': 'left', 'closing': True,
                  'start_frame': closing_frame, 'end_frame': math.ceil(duration * FPS),
                  'description': 'The complete supplied seaside photograph and warm Mandarin dedication'})
    plan = {'revision': 2, 'duration_seconds': duration, 'fps': FPS, 'frames': math.ceil(duration * FPS),
            'closing_start': closing_frame / FPS, 'shots': shots,
            'audio_sha256': sha256(ROOT / 'assets/bgm.wav'), 'captions_sha256': sha256(ROOT / 'captions.json'),
            'editorial_method': 'Single recipient, source-photo anchors, native24fps cadence, declared protagonist motif reprises and face-free context details.'}
    plan['memory_labels'] = [{'start': 18.4, 'end': 22.0, 'text': '拿督斯里谢惠福', 'latin': 'Hock Siew'}]
    plan['identity_coverage'] = validate_plan(plan, clips, cues, duration)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    plan = author()
    if args.write:
        write_json(ROOT / 'edit-plan-v2.json', plan)
    print({'shots': len(plan['shots']), 'frames': plan['frames'], 'coverage': plan['identity_coverage']})

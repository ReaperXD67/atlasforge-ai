"""Compile exact supplied lyrics from frozen acoustic alignment evidence.

Run after align_lyrics.py and timing-evidence/refine_onsets.py. The phrase
boundary choices below reference measured model observations; they are not a
uniform clock. Raw evidence remains available for a future listening review.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

from daily_video_factory import lyrics

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'timing-evidence'
DURATION = 196.76

# Native DTW can consume leading silence in its first token, or consume a
# syllable in punctuation. Prefer independent ASR onsets in those cases.
# Each tuple is (measured onset, evidence source, reason).
ONSETS = {
    0: (22.30, 'asr-onset-refinement.json crop 18–29.6', 'Independent cropped recognition; reject whole-track 10.86s hallucination.'),
    1: (25.64, 'asr-onset-refinement.json crop 18–29.6', 'First two place-name syllables are phonetic observations; display user-approved 浅顶.'),
    2: (29.54, 'forced-alignment-context-medium.json window 0', 'Contextual DTW punctuation boundary before 拿; exact name is user-approved.'),
    3: (33.02, 'asr-onset-refinement.json crop 29.3–43.5', 'Independent first-word onset.'),
    4: (36.90, 'asr-onset-refinement.json crop 29.3–43.5', 'Independent first-word onset; DTW punctuation absorbed first syllable.'),
    5: (40.40, 'asr-onset-refinement.json crop 29.3–43.5', 'Independent first-word onset.'),
    6: (43.48, 'asr-medium.json', 'Whole-track onset corroborated by contextual DTW.'),
    7: (47.56, 'asr-onset-refinement.json crop 43.2–58.2', 'Independent first-word onset; repair zero-duration DTW 来.'),
    8: (51.66, 'asr-onset-refinement.json crop 43.2–58.2', 'Independent first-word onset.'),
    9: (54.50, 'asr-onset-refinement.json crop 43.2–58.2', 'Independent first-word onset.'),
    10: (58.18, 'asr-medium.json', 'Whole-track onset independently corroborated by small model 58.16s.'),
    11: (62.34, 'asr-onset-refinement.json crop 58–73', 'Independent first-word onset.'),
    12: (66.00, 'asr-onset-refinement.json crop 58–73', 'Independent first-word onset.'),
    13: (69.46, 'asr-onset-refinement.json crop 58–73', 'Independent first-word onset.'),
    14: (73.40, 'asr-medium.json', 'Whole-track first-word onset; crop starts inside preceding sustain.'),
    15: (77.10, 'asr-onset-refinement.json crop 72.6–81.1', 'Independent first-word onset.'),
    16: (81.04, 'asr-onset-refinement.json crop 80.5–94.6', 'Name chant starts here; repeated syllables prevent reliable per-word karaoke.'),
    17: (84.92, 'asr-onset-refinement.json crop 80.5–94.6', 'Independent first-word onset.'),
    18: (86.78, 'asr-onset-refinement.json crop 80.5–94.6', 'Independent first-word onset.'),
    19: (88.64, 'asr-onset-refinement.json crop 80.5–94.6', 'Independent first-word onset.'),
    20: (90.42, 'asr-onset-refinement.json crop 80.5–94.6', 'Independent name-chant onset.'),
    21: (92.30, 'asr-onset-refinement.json crop 80.5–94.6', 'Phonetic first-word observation; canonical 情义 retained.'),
    22: (94.34, 'forced-alignment-context-medium.json window 4', 'Contextual punctuation boundary; whole-track ASR 94.32s.'),
    23: (97.14, 'forced-alignment-corrected-medium.json window 6', 'Acoustic DTW onset corroborated by whole-track ASR 97.08s.'),
    24: (119.42, 'asr-medium.json', 'Whole-track onset after instrumental break; cropped DTW absorbs leading silence.'),
    25: (122.90, 'asr-onset-refinement.json crop 118.8–134', 'Independent first-word onset.'),
    26: (126.64, 'asr-onset-refinement.json crop 118.8–134', 'Cropped model separates the pause from previous sustain.'),
    27: (130.50, 'asr-onset-refinement.json crop 118.8–134', 'Independent first-word onset.'),
    28: (133.96, 'asr-medium.json', 'Whole-track onset; contextual DTW punctuation swallowed first syllable.'),
    29: (137.80, 'asr-onset-refinement.json crop 133.6–148.7', 'Independent first-word onset.'),
    30: (141.26, 'asr-onset-refinement.json crop 133.6–148.7', 'Independent first-word onset.'),
    31: (144.74, 'asr-onset-refinement.json crop 133.6–148.7', 'Independent first-word onset.'),
    32: (149.32, 'asr-onset-refinement.json crop 148.5–158.5', 'Independent repeated name-chant onset.'),
    33: (152.92, 'asr-onset-refinement.json crop 148.5–158.5', 'Independent first-word onset.'),
    34: (154.80, 'asr-onset-refinement.json crop 148.5–158.5', 'Phonetic name observation; display exact supplied 拿督斯里谢惠福.'),
    35: (156.64, 'asr-onset-refinement.json crop 148.5–158.5', 'Independent first-word onset.'),
    36: (158.40, 'forced-alignment-context-medium.json window 7', 'Contextual punctuation boundary; cropped recognition agrees at 158.40s.'),
    37: (160.44, 'asr-onset-refinement.json crop 158.4–172', 'Independent first-word onset.'),
    38: (162.10, 'asr-onset-refinement.json crop 158.4–172', 'Independent first-word onset.'),
    39: (164.08, 'asr-onset-refinement.json crop 158.4–172', 'Independent first-word onset; final sustain ends at 170.10s.'),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_raw_windows(data, specs):
    """Recover word spans only by exact concatenation of supplied lexemes.

    Native Whisper sometimes groups Chinese characters or fragments Latin
    names. Character subdivision is marked estimated; Latin fragments retain
    their measured outer boundaries. Punctuation does not become a sung word.
    """
    result = {}
    for window_number, window in enumerate(data['windows']):
        pieces = []
        for word in window['words']:
            tokens = lyrics._tokens(word['text'])
            for k, token in enumerate(tokens):
                start = word['start'] + (word['end'] - word['start']) * k / len(tokens)
                end = word['start'] + (word['end'] - word['start']) * (k + 1) / len(tokens)
                pieces.append((token, start, end, word['probability'], len(tokens) > 1))
        cursor = 0
        for index in window['line_indices']:
            words = []
            for canonical in specs[index].words:
                assembled, group = '', []
                target = lyrics._normalized_word(canonical)
                while assembled != target:
                    piece = pieces[cursor]
                    cursor += 1
                    assembled += lyrics._normalized_word(piece[0])
                    group.append(piece)
                    if not target.startswith(assembled):
                        raise ValueError(f'Unexpected native tokens in line {index}: {assembled} != {target}')
                words.append({'text': canonical, 'start_seconds': group[0][1], 'end_seconds': group[-1][2],
                              'confidence': round(statistics.mean(p[3] for p in group), 4),
                              'matched': False, 'estimated_timing': any(p[4] for p in group),
                              'native_fragment_count': len(group)})
            result[index] = {'words': words, 'source_window': window_number}
        assert cursor == len(pieces)
    return result


def stamp_srt(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}'


def main():
    specs = lyrics.parse_lyrics((ROOT / 'lyrics.txt').read_text(encoding='utf-8-sig'))
    assert len(specs) == 40
    raw = canonical_raw_windows(read(EVIDENCE / 'forced-alignment-corrected-medium.json'), specs)
    context = canonical_raw_windows(read(EVIDENCE / 'forced-alignment-context-medium.json'), specs)
    anchors = read(EVIDENCE / 'corrected-unprompted-asr-anchors.json')
    # Context fixes measured token fragmentation. Avoid its first phrase, where
    # DTW would again absorb preceding silence into a supplied first token.
    use_context = set(range(6)) | set(range(6, 10)) | set(range(10, 14)) | {14, 15, 22, 23} | set(range(28, 40))
    cues = []
    for index, spec in enumerate(specs):
        selected = context[index] if index in use_context else raw[index]
        # Last-context dictionaries include duplicated context phrases. The
        # baseline first verse retains cleaner local phoneme boundaries.
        if index in {5, 9, 13, 31, 34, 35}:
            selected = raw[index]
        words = [dict(w) for w in selected['words']]
        start, source, reason = ONSETS[index]
        end = words[-1]['end_seconds']
        if index == 23:
            end = 102.92  # whole-track medium detects the final sung 地方 sustain
        elif index == 39:
            end = 170.10  # independent cropped ASR resolves the final 头 sustain
        words[0]['start_seconds'] = start
        # When DTW yields a zero first token, the independent onset supplies its
        # measured span up to the next native token boundary.
        words[0]['estimated_timing'] = True
        words[-1]['end_seconds'] = end
        if index in {10, 24, 29}:
            # 有人 / 今天 / 我们 were timestamped as two-character groups.
            # Re-subdivide their measured outer span after trimming leading
            # silence, instead of keeping the stale pre-trim midpoint.
            group_end = words[1]['end_seconds']
            midpoint = round((start + group_end) / 2, 3)
            words[0]['end_seconds'] = midpoint
            words[1]['start_seconds'] = midpoint
            words[1]['estimated_timing'] = True
        cue = {'start': start, 'end': round(end, 3), 'text': spec.text, 'section': spec.section,
               'confidence': round(statistics.mean(w['confidence'] for w in words), 4),
               'timing_source': 'whisper_medium_cross_attention_dtw_with_independent_asr_onsets',
               'words': words,
               'alignment_review': {'onset_source': source, 'onset_reason': reason,
                                    'review_status': 'model_reviewed; listening review not performed'}}
        for k, word in enumerate(words):
            anchor = anchors['lines'][index]['words'][k]
            word['matched'] = anchor['matched']
            word['start_seconds'] = round(word['start_seconds'], 3)
            word['end_seconds'] = round(word['end_seconds'], 3)
        if 'Hock Siew' in spec.text:
            cue['alignment_review']['word_timing_limit'] = 'Repeated phonetic name chant; use phrase-level captions rather than per-word karaoke.'
            for word in words:
                word['estimated_timing'] = True
                word['matched'] = False
        cues.append(cue)
    # Phrase boundaries win over incidental model overlap in held notes. Repair
    # only overlapping word extents, retaining zero/adjustment provenance.
    adjustments = []
    for index, cue in enumerate(cues):
        following = cues[index + 1]['start'] if index + 1 < len(cues) else DURATION
        if cue['end'] > following:
            adjustments.append({'line_index': index, 'old_end': cue['end'], 'new_end': following,
                                'reason': 'next independently measured phrase onset'})
            cue['end'] = following
        words = cue['words']
        for k, word in enumerate(words):
            lower = cue['start'] if k == 0 else words[k - 1]['end_seconds']
            upper = cue['end'] if k + 1 == len(words) else max(lower, words[k + 1]['start_seconds'])
            old = (word['start_seconds'], word['end_seconds'])
            word['start_seconds'] = round(max(lower, min(upper, word['start_seconds'])), 3)
            word['end_seconds'] = round(max(word['start_seconds'], min(upper, word['end_seconds'])), 3)
            if word['end_seconds'] == word['start_seconds'] and k + 1 < len(words):
                # A zero DTW phoneme is borrowed from the next measured syllable,
                # never silently admitted as exact karaoke timing.
                boundary = min(cue['end'], word['start_seconds'] + .04)
                word['end_seconds'] = round(boundary, 3)
                words[k + 1]['start_seconds'] = round(max(boundary, words[k + 1]['start_seconds']), 3)
                word['estimated_timing'] = True
            if old != (word['start_seconds'], word['end_seconds']):
                word['estimated_timing'] = True
                adjustments.append({'line_index': index, 'word': k, 'old_span': old,
                                    'new_span': [word['start_seconds'], word['end_seconds']],
                                    'reason': 'containment/zero-duration repair; phrase display is authoritative'})
        assert cue['start'] < cue['end'] <= DURATION
        assert all(cue['start'] <= w['start_seconds'] < w['end_seconds'] <= cue['end'] for w in words)
    assert all(a['end'] <= b['start'] for a, b in zip(cues, cues[1:]))
    assert [c['text'] for c in cues] == [s.text for s in specs]
    write(ROOT / 'captions.json', cues)
    (ROOT / 'captions.srt').write_text('\n\n'.join(f'{i + 1}\n{stamp_srt(c["start"])} --> {stamp_srt(c["end"])}\n{c["text"]}' for i, c in enumerate(cues)) + '\n', encoding='utf-8')
    (ROOT / 'captions.lrc').write_text('\n'.join(f'[{int(c["start"] // 60):02}:{c["start"] % 60:05.2f}]{c["text"]}' for c in cues) + '\n', encoding='utf-8')
    findings = {'status': 'corrected_user_lyrics_aligned', 'title': '有你，兄弟同心',
                'dedication': '献给拿督斯里谢惠福', 'canonical_sung_lines': 40,
                'master_audio_sha256': hash_file(ROOT / 'assets/bgm.wav'),
                'lyrics_sha256': hash_file(ROOT / 'lyrics.txt'),
                'captions_sha256': hash_file(ROOT / 'captions.json'), 'duration_seconds': DURATION,
                'vocal_start_seconds': cues[0]['start'], 'vocal_end_seconds': cues[-1]['end'],
                'independent_whole_track_asr_anchor_coverage': anchors['anchor_coverage'],
                'independent_whole_track_mean_anchor_confidence': anchors['mean_anchor_confidence'],
                'model_reviewed_weak_phrases': [1, 2, 16, 20, 22, 23, 29, 30, 32, 33, 34, 36, 39],
                'review_notes': ['Line indices are zero-based.',
                                 'Corrected user text supersedes unrelated initial 32-line request.',
                                 'Hock Siew, 浅顶 and 拿督斯里谢惠福 are exact user spellings; recognition aliases never display.',
                                 'Medium whole-track 10.86s first onset rejected; cropped independent ASR resolves 22.30s.',
                                 'Name chants have repeated phonetic syllables; phrase captions preserve supplied line text. Per-word name karaoke is approximate.',
                                 'Final sung 头 sustain is 170.10s cropped ASR versus 170.90s whole-track ASR; retain cropped boundary.',
                                 'Character subdivisions of compound native words and repaired zero spans are estimated.',
                                 'Confidence values are decoder/token agreement, not calibrated guarantees of timing accuracy.',
                                 'No human listening review was performed.'],
                'possible_instrumental_windows': [
                    {'start': 0, 'end': 22.30, 'basis': 'cropped independent first vocal onset'},
                    {'start': 103, 'end': 119.42, 'basis': 'both whole-track ASR models omit lyrics; bridge onset refined'},
                    {'start': 171.2, 'end': DURATION, 'basis': 'all observed final vocal/sustain boundaries are before this safe margin'}],
                'recommended_closing_portrait_start': 171.2,
                'final_captions_written': True, 'timing_adjustments': adjustments}
    write(EVIDENCE / 'ASR_FINDINGS.json', findings)
    write(ROOT / 'line-alignment.json', {**findings, 'method': 'Native CTranslate2 cross-attention DTW plus independently decoded onset/sustain windows', 'lines': cues})
    print(f'{len(cues)} exact lyric lines; measured vocals {cues[0]["start"]:.2f}–{cues[-1]["end"]:.2f}s; {len(adjustments)} explicit word/overlap repairs.')


if __name__ == '__main__':
    main()

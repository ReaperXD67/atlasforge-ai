"""Compile canonical line cues from local exact-text DTW and observed onsets.

The local onset_choices.json records independently measured recognition
observations and why an observation supersedes a DTW punctuation boundary.
This script never invents an evenly spaced song clock or adds unsung headings.
"""
from __future__ import annotations
import hashlib,json,statistics,sys,wave
from pathlib import Path
from daily_video_factory import lyrics
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def stamp(t):
    ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def exact_words(data,specs):
    result={}
    for windex,window in enumerate(data['windows']):
        pieces=[]
        for w in window['words']:
            tokens=lyrics._tokens(w['text'])
            for k,token in enumerate(tokens):
                pieces.append((token,w['start']+(w['end']-w['start'])*k/len(tokens),w['start']+(w['end']-w['start'])*(k+1)/len(tokens),w['probability'],len(tokens)>1))
        cursor=0
        for index in window['line_indices']:
            words=[]
            for canonical in specs[index].words:
                target=lyrics._normalized_word(canonical);assembled='';group=[]
                while assembled!=target:
                    piece=pieces[cursor];cursor+=1;group.append(piece)
                    assembled+=lyrics._normalized_word(piece[0])
                    if not target.startswith(assembled):raise ValueError(f'Unexpected native lexemes in line {index}')
                words.append(dict(text=canonical,start_seconds=group[0][1],end_seconds=group[-1][2],confidence=round(statistics.mean(x[3] for x in group),4),matched=True,estimated_timing=any(x[4] for x in group),native_fragment_count=len(group)))
            result[index]=dict(words=words,source_window=windex)
        assert cursor==len(pieces)
    return result

def main():
    evidence=ROOT/'timing-evidence';source=ROOT/'assets/bgm.wav'
    specs=lyrics.parse_lyrics((ROOT/'lyrics.txt').read_text(encoding='utf-8-sig'))
    alignment=read(evidence/'forced-alignment-medium.json')
    choices=read(evidence/'onset-choices.json')
    assert alignment['audio_sha256']==sha(source) and alignment['lyrics_sha256']==sha(ROOT/'lyrics.txt')
    with wave.open(str(source),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
    raw=exact_words(alignment,specs);onsets=[float(choices[str(i)]['start']) for i in range(len(specs))]
    assert all(b>a for a,b in zip(onsets,onsets[1:])) and onsets[0]>=0
    cues=[]
    for i,spec in enumerate(specs):
        words=raw[i]['words'];start=onsets[i];next_start=onsets[i+1] if i+1<len(specs) else duration
        end=min(max(start+.04,words[-1]['end_seconds']),next_start)
        assert start<end<=duration
        for word in words:
            original=[word['start_seconds'],word['end_seconds']]
            word['start_seconds']=round(min(end,max(start,original[0])),3)
            word['end_seconds']=round(min(end,max(word['start_seconds'],original[1])),3)
            if [word['start_seconds'],word['end_seconds']]!=original:word['estimated_timing']=True
        cues.append(dict(start=round(start,3),end=round(end,3),text=spec.text,section=spec.section,confidence=round(statistics.mean(w['confidence'] for w in words),4),timing_source='local_native_cross_attention_DTW_with_independent_cropped_ASR_onsets',onset_evidence=choices[str(i)],words=words))
    write(ROOT/'captions.json',cues)
    (ROOT/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n',encoding='utf-8')
    (ROOT/'captions.lrc').write_text('\n'.join(f'[{int(c["start"]//60):02d}:{c["start"]%60:05.2f}]{c["text"]}' for c in cues)+'\n',encoding='utf-8')
    write(evidence/'timing-validation.json',dict(audio_sha256=sha(source),lyrics_sha256=sha(ROOT/'lyrics.txt'),caption_sha256=sha(ROOT/'captions.json'),duration_seconds=duration,cues=len(cues),first_sung_cue=cues[0]['start'],last_sung_cue_end=cues[-1]['end'],ordered=True,non_overlapping=True,unsung_headers_excluded=True,word_timing_limits='Native DTW character subdivisions and clamped boundaries are flagged estimated; this is line-level timing, not verified per-syllable karaoke.',human_listening_review=False))
    for i,c in enumerate(cues):print(f'{i+1:02d} {c["start"]:.3f}-{c["end"]:.3f} {c["text"]}')

if __name__=='__main__':main()

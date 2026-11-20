"""Align supplied lyric blocks to local acoustic features, retaining raw evidence.

Run with a local timing-evidence/alignment-windows.json. Its intervals must come
from an independent recording transcription, not an evenly spaced lyric clock.
Source audio/lyrics/evidence stay local; no provider upload is performed.
"""
from __future__ import annotations
import hashlib,json,subprocess,sys,time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import pad_or_trim
from faster_whisper.tokenizer import Tokenizer
from opencc import OpenCC
from daily_video_factory import lyrics
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def main():
    evidence=ROOT/'timing-evidence'
    windows=json.loads((evidence/'alignment-windows.json').read_text(encoding='utf-8'))
    specs=lyrics.parse_lyrics((ROOT/'lyrics.txt').read_text(encoding='utf-8-sig'))
    folder=next((REPO/'models/whisper/models--Systran--faster-whisper-medium/snapshots').iterdir())
    model=WhisperModel(str(folder),device='cpu',compute_type='int8',cpu_threads=6)
    tokenizer=Tokenizer(model.hf_tokenizer,model.model.is_multilingual,task='transcribe',language='zh')
    cc=OpenCC('t2s');records=[];started=time.perf_counter()
    for record in windows:
        a,b,indices=record['start'],record['end'],record['line_indices']
        samples=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-ss',str(a),'-i',str(ROOT/'assets/bgm.wav'),'-t',str(b-a),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True).stdout,dtype=np.float32)
        features=model.feature_extractor(samples); encoder=model.encode(pad_or_trim(features))
        supplied='。'.join(specs[i].text for i in indices)
        aligned=model.find_alignment(tokenizer,[tokenizer.encode(supplied)],encoder,features.shape[-1])[0]
        words=[dict(text=cc.convert(w['word']).strip(),start=round(float(w['start'])+a,3),end=round(float(w['end'])+a,3),probability=float(w['probability'])) for w in aligned]
        records.append(dict(source_start=a,source_end=b,line_indices=indices,supplied_text=supplied,words=words))
        data=dict(model='Systran/faster-whisper-medium',revision=folder.name,method='CTranslate2 native cross-attention DTW over supplied text within independent-ASR-supported phrase windows',audio_sha256=hashlib.sha256((ROOT/'assets/bgm.wav').read_bytes()).hexdigest(),lyrics_sha256=hashlib.sha256((ROOT/'lyrics.txt').read_bytes()).hexdigest(),windows=records,elapsed_seconds=time.perf_counter()-started)
        (evidence/'forced-alignment-medium.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(records[-1],ensure_ascii=False),flush=True)

if __name__=='__main__': main()

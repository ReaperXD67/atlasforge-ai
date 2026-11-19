"""Align the corrected song lyrics against cached native Whisper acoustic features."""
from __future__ import annotations
import hashlib,json,subprocess,sys,time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import pad_or_trim
from faster_whisper.tokenizer import Tokenizer
from opencc import OpenCC
from daily_video_factory import lyrics
from daily_video_factory.config import load_settings
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
E=ROOT/'timing-evidence'
DURATION=196.76
WINDOWS=[(21.5,44,[0,1,2,3,4,5]),(40,58.4,[5,6,7,8,9]),(54,73.5,[9,10,11,12,13]),(69,81.5,[13,14,15]),(92,104,[21,22,23]),(130,149,[27,28,29,30,31]),(144.5,159,[31,32,33,34,35]),(154.5,172,[34,35,36,37,38,39])]
cc=OpenCC('t2s')
text=(ROOT/'lyrics.txt').read_text(encoding='utf-8-sig')
specs=lyrics.parse_lyrics(text)
assert len(specs)==40
folder=next(Path('models/whisper/models--Systran--faster-whisper-medium/snapshots').iterdir())
model=WhisperModel(str(folder),device='cpu',compute_type='int8',cpu_threads=8)
tokenizer=Tokenizer(model.hf_tokenizer,model.model.is_multilingual,task='transcribe',language='zh')
started=time.perf_counter();results=[]
for a,b,indices in WINDOWS:
    samples=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-ss',str(a),'-i',str(ROOT/'assets/bgm.wav'),'-t',str(b-a),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True).stdout,dtype=np.float32)
    features=model.feature_extractor(samples);encoder=model.encode(pad_or_trim(features))
    supplied='。'.join(specs[i].text for i in indices)
    tokens=tokenizer.encode(supplied)
    aligned=model.find_alignment(tokenizer,[tokens],encoder,features.shape[-1])[0]
    words=[{'text':cc.convert(w['word']).strip(),'start':round(float(w['start'])+a,3),'end':round(float(w['end'])+a,3),'probability':float(w['probability'])} for w in aligned]
    rec={'source_start':a,'source_end':b,'line_indices':indices,'supplied_text':supplied,'words':words}
    results.append(rec)
    print(json.dumps(rec,ensure_ascii=False),flush=True)
    (E/'forced-alignment-context-medium.json').write_text(json.dumps({'model':'Systran/faster-whisper-medium','revision':folder.name,'method':'CTranslate2 native cross-attention DTW over exact corrected text within ASR-supported phrase windows','audio_sha256':hashlib.sha256((ROOT/'assets/bgm.wav').read_bytes()).hexdigest(),'lyrics_sha256':hashlib.sha256((ROOT/'lyrics.txt').read_bytes()).hexdigest(),'windows':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Forced alignment seconds',time.perf_counter()-started)

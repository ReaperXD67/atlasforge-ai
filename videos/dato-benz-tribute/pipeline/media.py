"""Local media utilities; no inherited project clock, media or provider calls."""
from __future__ import annotations
import hashlib,json,subprocess,wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def run(args,timeout=1200):
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-3500:])
    return p.stdout
def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
def probe(path):return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))
def input_contract():
    intake=read_json(ROOT/'timing-evidence/intake.json');timing=read_json(ROOT/'timing-evidence/timing-validation.json')
    audio=ROOT/'assets/bgm.wav'
    assert sha256(audio)==intake['sha256']==timing['audio_sha256'],'Original recording hash changed'
    assert sha256(ROOT/'captions.json')==timing['caption_sha256'],'Frozen cue hash changed'
    assert sha256(ROOT/'lyrics.txt')==timing['lyrics_sha256'],'Canonical lyric hash changed'
    with wave.open(str(audio),'rb') as w:duration=w.getnframes()/w.getframerate();rate=w.getframerate();channels=w.getnchannels();samples=w.getnframes()
    assert abs(duration-intake['duration_seconds'])<1e-8
    return dict(duration=duration,sample_rate=rate,channels=channels,samples=samples,audio_sha256=intake['sha256'],caption_sha256=timing['caption_sha256'],cue_count=timing['cues'])
def stream_hash(path,kind):
    return run([ffmpeg(),'-v','error','-i',path,'-map',f'0:{kind}:0','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()

"""Keep the rendered picture and mux the canonical song once at 320 kbps AAC."""
from __future__ import annotations

import argparse
from pathlib import Path

from prepare_film import ffmpeg, probe, run, sha256, write_json

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'renders/v4'
AUDIO_SHA = '60ee65f074f36b2d31660bee652e111cd84538e51b74a0685cbd895291cd6547'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--picture', type=Path, default=OUT/'Hock-Siew-Image-Film-V4-picture.mp4')
    parser.add_argument('--share', action='store_true')
    args = parser.parse_args()
    source = args.picture.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    audio = ROOT/'assets/bgm.wav'
    if sha256(audio) != AUDIO_SHA:
        raise ValueError('Canonical song hash changed.')
    video = next(s for s in probe(source)['streams'] if s['codec_type']=='video')
    if (video['width'],video['height'],video['r_frame_rate']) != (1920,1080,'24/1'):
        raise ValueError('Expected a completed 1920x1080 24fps picture render.')
    OUT.mkdir(parents=True,exist_ok=True)
    master=OUT/'Hock-Siew-Image-Film-V4.mp4'
    run([ffmpeg(),'-y','-i',str(source),'-i',str(audio),'-map','0:v:0','-map','1:a:0',
         '-c:v','copy','-c:a','aac','-b:a','320k','-ar','48000','-ac','2',
         '-map_metadata','0','-metadata','title=有你，兄弟同心 · Hock Siew',
         '-movflags','+faststart',str(master)])
    outputs=[master]
    if args.share:
        share=OUT/'Hock-Siew-Image-Film-V4-720p.mp4'
        run([ffmpeg(),'-y','-i',str(master),'-map','0:v:0','-map','0:a:0',
             '-vf','scale=1280:720:flags=lanczos','-c:v','h264_nvenc','-preset','p6',
             '-rc','vbr','-cq','20','-b:v','6M','-maxrate','12M','-bufsize','24M',
             '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(share)])
        outputs.append(share)
    write_json(OUT/'finalize-receipt.json',dict(
        picture_source=str(source.relative_to(ROOT)),picture_source_sha256=sha256(source),
        picture_reencoded_for_master=False,canonical_audio_sha256=AUDIO_SHA,
        master_audio='AAC 320 kbps, 48kHz stereo, encoded directly from original WAV',
        output=[dict(path=str(p.relative_to(ROOT)),sha256=sha256(p),bytes=p.stat().st_size,
                     probe=probe(p)) for p in outputs]))
    print(master)


if __name__=='__main__':
    main()

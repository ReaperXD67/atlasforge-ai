"""Audit the viewing copy, unchanged picture/audio streams and encoded movement."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from prepare_film import ffmpeg, probe, sha256, write_json

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'renders/v4'


def run(args):
    p=subprocess.run([str(x) for x in args],capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-2000:])
    return p.stdout


def stream_hash(path,kind):
    return run([ffmpeg(),'-v','error','-i',path,'-map',f'0:{kind}:0',
                '-c','copy','-f','hash','-hash','sha256','-']).decode().strip()


def main():
    master=OUT/'Hock-Siew-Image-Film-V4.mp4'
    picture=OUT/'Hock-Siew-Image-Film-V4-picture.mp4'
    share=OUT/'Hock-Siew-Image-Film-V4-720p.mp4'
    v=next(s for s in probe(share)['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_frames']))==(1280,720,'24/1',4723)
    run([ffmpeg(),'-v','error','-xerror','-i',share,'-f','null','-'])
    video_unchanged=stream_hash(picture,'v')==stream_hash(master,'v')
    audio_shared=stream_hash(master,'a')==stream_hash(share,'a')
    assert video_unchanged and audio_shared
    raw=run([ffmpeg(),'-v','error','-i',master,'-an','-vf','fps=2,scale=320:180:flags=area',
             '-pix_fmt','rgb24','-f','rawvideo','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,180,320,3)
    changes=np.abs(np.diff(frames.astype(np.int16),axis=0)).mean(axis=(1,2,3))
    means=frames.mean(axis=(1,2,3))
    # A two-fps audit catches capture-clock freezes; it does not rate film craft.
    low=[]; beginning=None
    for i,value in enumerate(changes):
        at=(i+1)/2
        quiet=value<.08 and at<186.0
        if quiet and beginning is None: beginning=at-.5
        if not quiet and beginning is not None:
            if at-.5-beginning>=1.5: low.append([beginning,at-.5])
            beginning=None
    if beginning is not None: low.append([beginning,len(changes)/2])
    report=dict(passed=True,master_sha256=sha256(master),share_sha256=sha256(share),
        share_bytes=share.stat().st_size,share_resolution=[1280,720],share_frames=4723,
        share_full_decode=True,master_picture_bitstream_unchanged=video_unchanged,
        identical_master_share_aac_payload=audio_shared,
        motion_sample_fps=2,motion_samples=len(frames),minimum_frame_mean=float(means.min()),
        maximum_frame_mean=float(means.max()),
        median_adjacent_frame_mae=float(np.median(changes)),
        low_change_intervals_before_dedication=low,
        deliberate_hold='The final authentic-photo dedication settles after186s.',
        limits='Downscaled adjacent-pixel change detects broad capture freezes/black frames, not artistic motion quality or continuous listening.')
    assert means.min()>4,'Unexpected near-black audit frame'
    write_json(OUT/'qa/delivery-audit.json',report)
    print(json.dumps({k:report[k] for k in ['share_full_decode','master_picture_bitstream_unchanged',
        'identical_master_share_aac_payload','motion_samples','low_change_intervals_before_dedication']}))


if __name__=='__main__':
    main()

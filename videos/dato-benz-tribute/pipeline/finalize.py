"""Preserve the completed picture; encode the original song once at320kbps AAC."""
from __future__ import annotations
import argparse,math
from pathlib import Path
from media import ROOT,ffmpeg,input_contract,probe,run,sha256,stream_hash,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--picture',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'renders/Benz-Brothers-One-Heart-1080p.mp4')
    p.add_argument('--share',action='store_true');a=p.parse_args()
    contract=input_contract();picture=a.picture.resolve();master=a.output.resolve();master.parent.mkdir(parents=True,exist_ok=True)
    v=next(s for s in probe(picture)['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['r_frame_rate'])==(1920,1080,'24/1')
    assert int(v['nb_frames'])==math.ceil(contract['duration']*24)
    assert picture!=master,'Choose a new final output; preserve the picture render'
    run([ffmpeg(),'-y','-i',picture,'-i',ROOT/'assets/bgm.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','320k','-ar',contract['sample_rate'],'-ac',contract['channels'],'-map_metadata','0','-movflags','+faststart',master])
    picture_same=stream_hash(picture,'v')==stream_hash(master,'v');assert picture_same
    outputs=[master];aac_same=None
    if a.share:
        share=master.with_name(master.stem.replace('-1080p','')+'-720p.mp4')
        run([ffmpeg(),'-y','-i',master,'-map','0:v:0','-map','0:a:0','-vf','scale=1280:720:flags=lanczos','-c:v','h264_nvenc','-preset','p6','-rc','vbr','-cq','20','-b:v','6M','-maxrate','12M','-bufsize','24M','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',share])
        aac_same=stream_hash(master,'a')==stream_hash(share,'a');assert aac_same
        outputs.append(share)
    write_json(master.parent/'finalize-receipt.json',dict(input_contract=contract,picture_source=str(picture.relative_to(ROOT)),picture_source_sha256=sha256(picture),picture_reencoded_for_master=False,picture_bitstream_unchanged=picture_same,master_share_aac_payload_identical=aac_same,master_audio='AAC320kbps48kHzstereo encoded directly from canonical WAV',outputs=[dict(path=str(x.relative_to(ROOT)),sha256=sha256(x),bytes=x.stat().st_size,probe=probe(x)) for x in outputs]))
    print(master)

if __name__=='__main__':main()

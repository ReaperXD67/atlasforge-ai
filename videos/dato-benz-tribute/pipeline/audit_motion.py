"""Measure encoded picture changes and near-black samples without rating craft.

Intended for a COMPLETED master. Reads its actual dimensions/clock and the
current frozen edit plan; it never changes the renderer, recording or captions.
The final dedication's stationary framing is recognized from that plan, not a
copied timestamp from an earlier song. This is a coarse sampled signal audit,
not a smoothness, facial-likeness, listening or client-acceptance test.
"""
from __future__ import annotations

import argparse,json,math
from pathlib import Path

import numpy as np

from media import ROOT,ffmpeg,input_contract,probe,read_json,run,sha256,write_json


def close(a,b):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return abs(a-b)<1e-9
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(close(x,y) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(close(a[k],b[k]) for k in a)
    return a==b


def stationary_framing(scene):
    """Scene intent, independent of whether subtle atmosphere changes pixels."""
    if 'focalRect' in scene:
        camera_static=close(scene['focalRect'],scene.get('focalRectEnd',scene['focalRect']))
    elif scene.get('camera'):
        poses=[{k:v for k,v in point.items() if k not in ('at','ease')} for point in scene['camera']]
        camera_static=all(close(poses[0],p) for p in poses[1:])
    else:
        # An unspecified renderer camera preset is not evidence of a hold.
        camera_static=False
    moving_layers=any(not close(layer.get('from',{}),layer.get('to',layer.get('from',{}))) for layer in scene.get('layers',[]))
    return camera_static and not moving_layers


def intended_holds(plan):
    result=[]
    for index,scene in enumerate(plan['scenes']):
        explicit=scene.get('auditHold') is True
        closing=index==len(plan['scenes'])-1 and bool(scene.get('title')) and stationary_framing(scene)
        if explicit or closing:
            result.append(dict(scene=scene['id'],start=scene['start'],end=scene['end'],
                reason='Explicit per-scene auditHold in the frozen plan' if explicit else
                       'Final authored dedication with identical start/end framing and no moving foreground layer',
                note='Stationary framing is intentional; text fades or subtle atmosphere may still change pixels.'))
    return result


def runs(flags,rate,minimum_seconds,edge_offset=0):
    """Return approximate time intervals on the downsampled output clock."""
    intervals=[];begin=None
    for index,flag in enumerate([*flags,False]):
        if flag and begin is None:begin=index
        if not flag and begin is not None:
            duration=(index-begin)/rate
            if duration+1e-9>=minimum_seconds:
                intervals.append(dict(start_seconds=(begin+edge_offset)/rate,
                                      end_seconds=(index+edge_offset)/rate,
                                      duration_seconds=duration))
            begin=None
    return intervals


def audit(video,plan_path,sample_fps=2.0,width=320,low_change_mae=.08,
          minimum_still_seconds=1.5,near_black_mean=4.0,near_black_fraction=.98):
    contract=input_contract();plan=read_json(plan_path);metadata=probe(video)
    stream=next(s for s in metadata['streams'] if s['codec_type']=='video')
    frame_rate=float(stream['avg_frame_rate'].split('/')[0])/float(stream['avg_frame_rate'].split('/')[1])
    expected_frames=math.ceil(contract['duration']*plan['fps'])
    if (stream['width'],stream['height'])!=(plan['width'],plan['height']) or abs(frame_rate-plan['fps'])>1e-8:
        raise ValueError('Audit input does not match the frozen plan resolution/frame cadence')
    if int(stream.get('nb_frames',0))!=expected_frames:
        raise ValueError('Audit requires the complete frame count; partial or study videos are excluded')
    if abs(float(metadata['format']['duration'])-contract['duration'])>1/plan['fps']+.002:
        raise ValueError('Audit input does not cover the complete trimmed recording')
    if abs(plan['duration']-contract['duration'])>1e-8:
        raise ValueError('Current edit plan uses a different recording clock')
    height=round(width*plan['height']/plan['width']);height=max(2,height)
    raw=run([ffmpeg(),'-v','error','-xerror','-i',video,'-an','-sn','-dn',
             '-vf',f'fps={sample_fps:g},scale={width}:{height}:flags=area',
             '-pix_fmt','rgb24','-f','rawvideo','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,height,width,3)
    if len(frames)<2 or abs(len(frames)-round(float(metadata['format']['duration'])*sample_fps))>1:
        raise ValueError('Downsampled audit did not cover the complete picture clock')
    delta=np.abs(np.diff(frames.astype(np.int16),axis=0))
    full_mae=delta.mean(axis=(1,2,3))
    # Exclude the lower22% caption band so changing lyrics alone do not hide a
    # frozen background. Authored upper titles remain in this sampled region.
    picture_height=max(1,round(height*.78))
    picture_mae=delta[:,:picture_height,:,:].mean(axis=(1,2,3))
    rgb=frames.astype(np.float32)
    luma=rgb[:,:,:,0]*.2126+rgb[:,:,:,1]*.7152+rgb[:,:,:,2]*.0722
    means=luma.mean(axis=(1,2));dark_fraction=(luma<=8).mean(axis=(1,2))
    black=(means<=near_black_mean)&(dark_fraction>=near_black_fraction)
    holds=intended_holds(plan)
    # Difference i covers the approximate audit interval i/rate..(i+1)/rate.
    covered=np.zeros(len(picture_mae),dtype=bool)
    for i in range(len(covered)):
        left=i/sample_fps;right=(i+1)/sample_fps
        covered[i]=any(left>=h['start']-1/sample_fps and right<=h['end']+1e-7 for h in holds)
    low=picture_mae<low_change_mae
    low_all=runs(low.tolist(),sample_fps,minimum_still_seconds)
    unexpected=runs((low&~covered).tolist(),sample_fps,minimum_still_seconds)
    black_intervals=runs(black.tolist(),sample_fps,1/sample_fps)
    scene_summaries=[]
    for s in plan['scenes']:
        ix=[i for i in range(len(picture_mae)) if s['start']<=i/sample_fps<s['end']]
        if not ix:continue
        values=picture_mae[ix]
        scene_summaries.append(dict(scene=s['id'],start=s['start'],end=s['end'],
            sampled_differences=len(ix),picture_mae_min=float(values.min()),
            picture_mae_median=float(np.median(values)),picture_mae_max=float(values.max()),
            planned_stationary_framing=stationary_framing(s)))
    return dict(passed=True,stage='encoded_picture_signal_audit',file=str(video),file_sha256=sha256(video),
        plan=str(plan_path.relative_to(ROOT)),plan_sha256=sha256(plan_path),
        source_song_seconds=contract['duration'],encoded_seconds=float(metadata['format']['duration']),
        encoded_frames=expected_frames,audit_sample_fps=sample_fps,audit_dimensions=[width,height],
        audit_frame_samples=len(frames),approximate_time_resolution_seconds=1/sample_fps,
        caption_band_excluded_fraction=.22,minimum_luma_code_mean=float(means.min()),
        maximum_luma_code_mean=float(means.max()),full_frame_mae_median=float(np.median(full_mae)),
        picture_region_mae_median=float(np.median(picture_mae)),
        thresholds=dict(low_picture_mae=low_change_mae,minimum_still_seconds=minimum_still_seconds,
                        near_black_mean_luma_code=near_black_mean,near_black_fraction_luma_le8=near_black_fraction),
        intended_holds=holds,all_low_change_intervals=low_all,
        low_change_intervals_outside_intended_holds=unexpected,
        near_black_intervals=black_intervals,review_required=bool(unexpected or black_intervals),
        scene_summaries=scene_summaries,
        limits=['Pass means complete-file decoding/sampling and plan binding succeeded, not artistic approval.',
                'MAD measures code-value changes, not smoothness, meaningful motion, depth correctness or personal likeness.',
                'The picture region excludes the caption band but may contain authored upper titles.',
                'A dark artistic composition or deliberate stillness can legitimately trigger a flag; inspect flagged intervals.',
                'The coarse sampling can miss sub-frame or short flashes and does not establish continuous playback/listening.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file',type=Path,required=True,help='Completed full1080p master, never a partial/study file')
    p.add_argument('--plan',type=Path,default=ROOT/'edit-plan.json')
    p.add_argument('--output',type=Path,default=ROOT/'renders/qa/motion-audit.json')
    p.add_argument('--sample-fps',type=float,default=2.0);p.add_argument('--width',type=int,default=320)
    p.add_argument('--low-change-mae',type=float,default=.08);p.add_argument('--minimum-still-seconds',type=float,default=1.5)
    a=p.parse_args()
    if not .5<=a.sample_fps<=12 or not 160<=a.width<=1920 or a.low_change_mae<0 or a.minimum_still_seconds<=0:
        p.error('Use sample-fps0.5..12, width160..1920 and nonnegative/positive audit thresholds')
    try:
        report=audit(a.file.resolve(),a.plan.resolve(),a.sample_fps,a.width,a.low_change_mae,a.minimum_still_seconds)
    except (ValueError,OSError,KeyError,AssertionError,RuntimeError) as e:
        report=dict(passed=False,stage='encoded_picture_signal_audit',file=str(a.file),error=str(e))
    write_json(a.output.resolve(),report)
    print(json.dumps({k:report.get(k) for k in ('passed','error','audit_frame_samples','review_required','low_change_intervals_outside_intended_holds','near_black_intervals')},indent=2))
    print(a.output.resolve())
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()

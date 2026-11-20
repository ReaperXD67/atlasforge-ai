"""Verify the actual trimmed song, integrated identity contract and MP4 export.

Private recording/cues/reference PNGs stay local. A pass establishes signal,
file and sampled picture correspondence, not personal likeness or client taste.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,math,re,subprocess
from datetime import datetime,timezone
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.signal import correlate,correlation_lags
from media import ROOT,ffmpeg,input_contract,probe,read_json,run,sha256,stream_hash,write_json

RENDERER=ROOT/'pipeline/renderer';QA=ROOT/'renders/qa'
ENVIRONMENT_IDS={2,3,5,7,9,10,12,13,15,17}
IDENTITY_IDS={1,4,6,8,11,14,16,18}
VIDEO_SUFFIXES={'.mp4','.webm','.mkv','.mov','.gif','.avi'}

def require(value,message):
    if not value:raise ValueError(message)

def local(value,base=ROOT):
    require(isinstance(value,str) and not re.match(r'^[a-z]+://',value,re.I),'Remote media is excluded')
    path=(base/value).resolve()
    require(path.is_relative_to(ROOT.resolve()),f'Path escapes this project: {value}')
    return path

class CompositionHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.cues=[];self.audio=[];self.videos=[];self.root=None;self._cue=None;self._depth=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='video':self.videos.append(attrs)
        if tag=='audio':self.audio.append(attrs)
        if attrs.get('id')=='root':self.root=attrs
        if self._cue is not None:self._depth+=1
        elif tag=='div' and re.fullmatch(r'cue-\d+',attrs.get('id','')):self._cue={'attrs':attrs,'text':''};self._depth=1
    def handle_data(self,text):
        if self._cue is not None:self._cue['text']+=text
    def handle_endtag(self,tag):
        if self._cue is not None:
            self._depth-=1
            if self._depth==0:self.cues.append(self._cue);self._cue=None

def rect(value,label):
    require(isinstance(value,list) and len(value)==4 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in value),f'Invalid normalized rectangle {label}')
    x,y,w,h=value;require(x>=0 and y>=0 and w>0 and h>0 and x+w<=1.00001 and y+h<=1.00001,f'Rectangle outside image {label}')

def scene_contract(scene,depths):
    source=local(scene['src']);require(source.parent==(ROOT/'assets/art').resolve() and source.suffix.lower()=='.png','Main scene must use a finished integrated art PNG')
    number=int(source.name[:2]);identity=number in IDENTITY_IDS
    require(number in ENVIRONMENT_IDS|IDENTITY_IDS and scene.get('containsIdentity',False)==identity,f'Identity classification mismatch: {scene["id"]}')
    if identity:
        require(not scene.get('depthSrc') and not scene.get('depthStrength'),f'Identity plate must remain rigid: {scene["id"]}')
        rect(scene.get('faceBounds'),f'{scene["id"]}.faceBounds')
        if scene.get('subjectBounds'):rect(scene['subjectBounds'],f'{scene["id"]}.subjectBounds')
    if scene.get('depthSrc'):
        require(number in ENVIRONMENT_IDS,'Depth forbidden on an identity plate')
        record=depths.get(source.stem);require(record is not None,'No frozen artwork depth provenance')
        require(record['source_sha256']==sha256(source) and record['depth_sha256']==sha256(local(scene['depthSrc'])),'Artwork/depth bytes differ from provenance')
    for layer in scene.get('layers',[]):
        require(layer.get('kind','art') in ('art','foreground') and not layer.get('containsIdentity') and not layer.get('faceBounds'),'Human/photo card overlays are excluded')
        require(not layer.get('border') and not layer.get('frameColor'),'Framed photo layer is excluded')
        require(local(layer['src']).suffix.lower()=='.png','Foreground layer must be local PNG art')
    return identity

def preflight():
    contract=input_contract();plan_path=ROOT/'edit-plan.json';plan=read_json(plan_path);cues=read_json(ROOT/'captions.json')
    duration=contract['duration'];fps=plan['fps'];frames=math.ceil(duration*fps)
    require(plan['width']==1920 and plan['height']==1080 and fps==24,'Expected1080p/24fps contract')
    require(abs(plan['duration']-duration)<1e-8 and len(cues)==contract['cue_count'],'Inherited song duration/cue count detected')
    require(len(cues)==32 and cues[0]['start']>0,'Trimmed recording requires32 canonical sung lines, with measured initial instrumental')
    require(all(a['end']<=b['start'] for a,b in zip(cues,cues[1:])),'Canonical cues overlap')
    require(all(0<=c['start']<c['end']<=duration for c in cues),'Invalid cue intervals')
    depths=read_json(ROOT/'depth-provenance.json')['depths'];end=0;used=set();identity=[]
    for scene in plan['scenes']:
        require(abs(scene['start']-end)<1e-8 and scene['end']>scene['start'],'Scene gap/overlap')
        end=scene['end'];has_identity=scene_contract(scene,depths)
        if has_identity:identity.append(scene['id'])
        for key in ('src','depthSrc'):
            if scene.get(key):used.add(scene[key])
        used.update(x['src'] for x in scene.get('layers',[]))
        if scene.get('transition',{}).get('mask'):used.add(scene['transition']['mask'])
    require(abs(end-duration)<1e-8,'Shots do not cover the complete recording')
    coverage=[]
    for cue in [c for c in cues if 'Dato Benz' in c['text']]:
        cursor=cue['start'];spans=[]
        for scene in plan['scenes']:
            if scene['end']<=cursor or scene['start']>=cue['end']:continue
            require(scene.get('containsIdentity'),f'Name cue lacks integrated Benz: {cue["start"]}')
            cursor=min(cue['end'],scene['end']);spans.append(scene['id'])
        require(abs(cursor-cue['end'])<1e-8,'Name cue coverage incomplete');coverage.append(dict(start=cue['start'],end=cue['end'],scenes=spans))
    receipt=read_json(RENDERER/'build-receipt.json')
    require(receipt['plan_sha256']==sha256(plan_path) and receipt['scene_count']==len(plan['scenes']) and receipt['cue_count']==len(cues),'Build receipt stale')
    copies={};frozen=[]
    for item in receipt['inputs']:
        original=local(item['source']);require(original.suffix.lower() not in VIDEO_SUFFIXES,'Video input in image-only build')
        require(sha256(original)==item['sha256'] and original.stat().st_size==item['bytes'],'Source hash/size changed after build')
        if item.get('local'):
            require(sha256(local(item['local'],RENDERER))==item['sha256'],'Frozen media copy differs');copies[item['source']]=item['local']
        frozen.append(dict(source=item['source'],sha256=item['sha256']))
    require(used|{plan['audio'],plan['captions']} <= {x['source'] for x in receipt['inputs']},'Unfrozen plan media')
    for item in receipt['vendors']+receipt['sources']:require(sha256(local(item['path'],RENDERER))==item['sha256'],'Renderer/vendor changed after build')
    html=(RENDERER/'index.html').read_text(encoding='utf-8');parsed=CompositionHTML();parsed.feed(html)
    require(len(parsed.cues)==len(cues) and len(parsed.audio)==1 and not parsed.videos,'DOM audio/cue/image-only contract failed')
    for i,(node,cue) in enumerate(zip(parsed.cues,cues)):
        a=node['attrs'];require(a['id']==f'cue-{i}' and node['text']==cue['text'] and abs(float(a['data-start'])-cue['start'])<1e-8 and abs(float(a['data-duration'])-(cue['end']-cue['start']))<1e-8,f'DOM canonical lyric differs at{i}')
    require(parsed.audio[0]['src']==copies[plan['audio']] and float(parsed.audio[0]['data-start'])==0 and abs(float(parsed.audio[0]['data-duration'])-duration)<1e-8,'Original soundtrack DOM binding differs')
    embedded,_=json.JSONDecoder().raw_decode(html.split('window.BENZ_PLAN=',1)[1]);expected=copy.deepcopy(plan)
    expected.setdefault('background','#071319');expected['audio']=copies[plan['audio']];expected['captions']=cues
    for scene in expected['scenes']:
        for key in ('src','depthSrc'):
            if scene.get(key):scene[key]=copies[scene[key]]
        for layer in scene.get('layers',[]):layer['src']=copies[layer['src']]
        if scene.get('transition',{}).get('mask'):scene['transition']['mask']=copies[scene['transition']['mask']]
    require(embedded==expected,'Embedded execution plan differs from source')
    candidates=[RENDERER/'smoke-result.json',RENDERER/'targeted-result.json',RENDERER/'renders/bindings/result.json']
    candidates += list((RENDERER/'renders').glob('*/result.json'))
    current=[(f,read_json(f)) for f in candidates if f.is_file()]
    current=[(f,d) for f,d in current if d.get('build_plan_sha256')==sha256(plan_path)]
    require(current,'No current browser framing/seek receipt for this exact plan')
    smoke_path,smoke=max(current,key=lambda pair:pair[0].stat().st_mtime_ns)
    require(not smoke['errors'] and smoke['repeat_seek_identical'],'Current browser/seek receipt failed')
    face=smoke['contracts']['face'];framing=smoke['contracts']['coverage']
    require(face and {x['scene'] for x in face}>=set(identity) and all(x['passed'] for x in face),'Integrated identity framing failed')
    require(all(x['passed'] or x.get('allow_matte') for x in framing),'Image-plane coverage failed')
    return plan,cues,dict(passed=True,stage='source_plan_build_preflight',input_contract=contract,shots=len(plan['scenes']),caption_cues=len(cues),expected_frames=frames,fps=fps,duration_seconds=duration,plan_sha256=sha256(plan_path),build_receipt_sha256=sha256(RENDERER/'build-receipt.json'),dom_cue_text_time_exact=True,embedded_plan_exact=True,identity_scenes=identity,identity_depth_prohibited=True,literal_photo_overlays=False,framing_receipt=smoke_path.relative_to(ROOT).as_posix(),face_framing_checks=len(face),coverage_checks=len(framing),name_cue_coverage=coverage,frozen_inputs=frozen,semantic_limits='Metadata and safe framing do not algorithmically establish likeness, natural anatomy or client approval; inspect the finished artworks/encoded samples.')

def stereo(path,rate):return np.frombuffer(run([ffmpeg(),'-v','error','-xerror','-i',path,'-map','0:a:0','-vn','-ac','2','-ar',rate,'-f','f32le','-']),dtype='<f4').reshape(-1,2)

def audio_check(video,contract):
    rate=contract['sample_rate'];original=stereo(ROOT/'assets/bgm.wav',rate);encoded=stereo(video,rate)
    require(len(original)==contract['samples'] and abs(len(original)-len(encoded))<=1024,'Original/encoded sample clock differs beyond AAC padding')
    n=min(len(original),len(encoded));corr=[];gain=[]
    for c in range(2):
        x=original[:n,c].astype(np.float64);y=encoded[:n,c].astype(np.float64);corr.append(float(np.corrcoef(x,y)[0,1]));g=float(np.dot(x,y)/np.dot(x,x));gain.append(20*math.log10(g) if g>0 else float('-inf'))
    require(all(x>=.98 for x in corr) and all(abs(x)<=.15 for x in gain),'Canonical soundtrack correlation/gain differs')
    duration=contract['duration'];lags=[]
    for t in [14.,duration*.40,duration*.72,duration-15.]:
        for c in range(2):
            a,b=round(t*rate),round((t+3)*rate);x=original[a:b,c].astype(np.float64);y=encoded[a:b,c].astype(np.float64);x-=x.mean();y-=y.mean()
            response=correlate(y,x,mode='full',method='fft');lag=correlation_lags(len(y),len(x),mode='full');valid=np.abs(lag)<=2400;best=int(lag[valid][np.argmax(response[valid])]);require(abs(best)<=1,f'Audio offset {best}samples at{t}s');lags.append(dict(start_seconds=t,channel=c,best_lag_samples=best))
    return dict(per_channel_correlation=corr,per_channel_gain_db=gain,compared_samples=n,original_samples=len(original),encoded_samples=len(encoded),lag_checks=lags,lag_tolerance_samples=1,encoded_aac_stream_hash=stream_hash(video,'a'),limits='Signal comparison/local lag, not a listening review or independent proof of every vocal onset.')

def frame(video,t):return Image.open(io.BytesIO(run([ffmpeg(),'-v','error','-ss',f'{t:.9f}','-i',video,'-frames:v','1','-f','image2pipe','-c:v','png','-']))).convert('RGB')

def picture_binding(video,plan):
    manifest=RENDERER/'renders/bindings/reference-bindings.json'
    if not manifest.exists():return dict(available=False,tested=False,limits='No exact-frame reference manifest supplied')
    d=read_json(manifest);require(d['plan_sha256']==sha256(ROOT/'edit-plan.json') and d['build_receipt_sha256']==sha256(RENDERER/'build-receipt.json'),'Binding references stale')
    require(d['resolution']==[1920,1080] and d['fps']==plan['fps'] and abs(d['duration']-plan['duration'])<1e-8 and not d['errors'],'Invalid binding capture contract')
    for s in d.get('build_sources',[]):require(s['expected_sha256']==s['actual_sha256']==sha256(local(s['path'],RENDERER)),'Binding renderer-source hash differs')
    refs=sorted(d['references'],key=lambda x:x['frame']);require(len(refs)==len({x['frame'] for x in refs})==9,'Nine unique picture references required')
    for r in refs:
        require(abs(r['time_seconds']-r['frame']/plan['fps'])<1e-8 and sha256(local(r['path'],manifest.parent))==r['sha256'],'Reference frame/time/hash mismatch')
    directory=QA/'picture-binding';directory.mkdir(parents=True,exist_ok=True)
    selection='+'.join(f'eq(n\\,{r["frame"]})' for r in refs)
    run([ffmpeg(),'-y','-v','error','-xerror','-i',video,'-an','-vf',f'select={selection}','-fps_mode','passthrough','-frames:v',len(refs),'-start_number','1',directory/'encoded-%02d.png'])
    result=[]
    for i,r in enumerate(refs,1):
        original=local(r['path'],manifest.parent);encoded=directory/f'encoded-{i:02d}.png'
        with Image.open(original) as a,Image.open(encoded) as b:
            require(a.size==b.size==(1920,1080),'Full-size reference comparison required');delta=np.asarray(a.convert('RGB'),dtype=np.float32)-np.asarray(b.convert('RGB'),dtype=np.float32)
        mae=float(np.abs(delta).mean());mse=float(np.square(delta).mean());psnr=10*math.log10(255**2/mse) if mse else 99.;passed=psnr>=25 and mae<=5
        result.append(dict(frame=r['frame'],time_seconds=r['time_seconds'],scene=r['scene'],psnr_db=psnr,mean_absolute_error_0_255=mae,passed=passed))
    report=dict(available=True,tested=True,passed=all(x['passed'] for x in result),thresholds=dict(minimum_psnr_db=25,maximum_mae=5),samples=result,limits='Nine exact-frame RGB comparisons without resize/alignment/colour fitting; not every-frame semantics or likeness approval.')
    write_json(QA/'picture-binding.json',report);require(report['passed'],'Encoded picture binding failed');return report

def contact_sheets(video,plan,cues):
    font_path=RENDERER/'assets/fonts/NotoSerifCJKsc-Regular.otf';font=ImageFont.truetype(str(font_path),18)
    pages=[]
    for page,start in enumerate(range(0,len(plan['scenes']),16),1):
        sheet=Image.new('RGB',(1920,1340),'#071319');draw=ImageDraw.Draw(sheet)
        for j,s in enumerate(plan['scenes'][start:start+16]):
            t=(s['start']+s['end'])/2;im=frame(video,t);im.thumbnail((480,270));x=(j%4)*480;y=(j//4)*335;sheet.paste(im,(x,y));draw.text((x+6,y+274),f'{s["id"]} / {t:.3f}s',font=font,fill='#f1d9b2')
            cue=next((c['text'] for c in cues if c['start']<=t<c['end']),'[instrumental / dedication]');draw.text((x+6,y+301),cue,font=font,fill='#eef1ec')
        path=QA/f'shot-midpoints-{page:02d}.png';sheet.save(path);pages.append(path.relative_to(ROOT).as_posix())
    names=[c for c in cues if 'Dato Benz' in c['text']];anchors=[]
    for i,c in enumerate(names,1):
        for label,t in [('first',c['start']+.12),('middle',(c['start']+c['end'])/2),('last',c['end']-.12)]:
            path=QA/f'name-anchor-{i:02d}-{label}.png';frame(video,t).save(path);anchors.append(dict(cue_start=c['start'],position=label,time_seconds=t,path=path.relative_to(ROOT).as_posix()))
    frame(video,1.5).save(QA/'opening.png');frame(video,plan['duration']-4).save(QA/'closing-dedication.png')
    return dict(sampled_shots=len(plan['scenes']),shot_midpoint_sheets=pages,name_anchors=anchors,limits='Encoded still samples, not continuous playback or client acceptance.')

def verify(video,contacts=False,share=None):
    plan,cues,source=preflight();contract=source['input_contract'];frames=source['expected_frames'];fps=plan['fps'];duration=plan['duration']
    metadata=probe(video);v=next(s for s in metadata['streams'] if s['codec_type']=='video');a=next(s for s in metadata['streams'] if s['codec_type']=='audio')
    require((v['width'],v['height'],v['codec_name'],v['pix_fmt'])==(1920,1080,'h264','yuv420p') and Fraction(v['avg_frame_rate'])==fps,'Master picture format differs')
    require(int(v['nb_frames'])==frames and abs(float(metadata['format']['duration'])-duration)<=1/fps+.001,'Master frame count/duration differs')
    require(abs(float(v.get('start_time',0)))<1e-6 and abs(float(a.get('start_time',0)))<1e-6,'Master A/V start offset')
    progress=run([ffmpeg(),'-v','error','-xerror','-i',video,'-progress','pipe:1','-nostats','-f','null','-']).decode();decoded=re.findall(r'^frame=(\d+)$',progress,re.M)
    require(decoded and int(decoded[-1])==frames and 'progress=end' in progress,'Complete master decode failed')
    audio=audio_check(video,contract);binding=picture_binding(video,plan)
    result=dict(passed=True,stage='full_encoded_verification',verified_at_utc=datetime.now(timezone.utc).isoformat(),file=str(video),sha256=sha256(video),bytes=video.stat().st_size,width=1920,height=1080,fps=fps,frames=frames,duration_seconds=float(metadata['format']['duration']),source_song_seconds=duration,full_video_audio_decode=True,audio=audio,picture_binding=binding,preflight=source,native_ai_video=False,identity_treatment='Integrated main scene plates; no photo cards and no identity depth deformation',acceptance='Pending user/boss review',ffmpeg_version=run([ffmpeg(),'-version']).decode().splitlines()[0],limits=['Metadata/guard checks do not establish facial likeness or anatomy correctness.','Sound is measured, not heard.','Technical verification and sampled images do not prove creative acceptance.'])
    if contacts:result['encoded_visual_samples']=contact_sheets(video,plan,cues)
    if share:
        sv=next(s for s in probe(share)['streams'] if s['codec_type']=='video');require((sv['width'],sv['height'],int(sv['nb_frames']))==(1280,720,frames),'Viewing copy format differs')
        run([ffmpeg(),'-v','error','-xerror','-i',share,'-f','null','-']);same=stream_hash(video,'a')==stream_hash(share,'a');require(same,'Viewing copy AAC differs')
        result['share']=dict(path=str(share),sha256=sha256(share),bytes=share.stat().st_size,full_decode=True,identical_master_aac=True)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preflight',action='store_true');p.add_argument('--file',type=Path);p.add_argument('--share',type=Path);p.add_argument('--contact-sheets',action='store_true');a=p.parse_args()
    if not a.preflight and not a.file:p.error('Use --preflight or --file completed-master.mp4')
    QA.mkdir(parents=True,exist_ok=True)
    try:result=preflight()[2] if a.preflight else verify(a.file.resolve(),a.contact_sheets,a.share.resolve() if a.share else None)
    except (OSError,ValueError,KeyError,AssertionError,RuntimeError,subprocess.TimeoutExpired,IndexError) as error:result=dict(passed=False,error=str(error),file=str(a.file) if a.file else None)
    target=QA/('source-preflight.json' if a.preflight else 'technical-verification.json');write_json(target,result)
    print(json.dumps({key:result.get(key) for key in ['passed','stage','error','shots','caption_cues','frames']},indent=2));print(target)
    raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__':main()

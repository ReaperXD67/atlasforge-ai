/** Build-time paths and motion timing. Node builtins only; no render side effects. */
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

export function projectFile(project, name) {
  if(typeof name!=='string'||!name||/[\\:\0]/.test(name)||path.posix.isAbsolute(name)||path.win32.isAbsolute(name)||name.split('/').includes('..')) {
    throw new Error('Asset must use a project-relative POSIX path');
  }
  const root=fs.realpathSync(project),target=fs.realpathSync(path.resolve(root,name));
  const relative=path.relative(root,target);
  if(!relative||relative==='..'||relative.startsWith(`..${path.sep}`)||path.isAbsolute(relative)||!fs.statSync(target).isFile()) {
    throw new Error(`Missing or escaping project asset: ${name}`);
  }
  return target;
}

export function assetUrl(project, name) {
  projectFile(project,name);
  // Encode URL metacharacters as well as spaces; HTML escaping alone cannot
  // preserve a literal #, ?, % or & in a local filename.
  return name.split('/').map(segment=>encodeURIComponent(segment)).join('/');
}

function positive(value) {
  const parsed=typeof value==='number'?value:Number(value);
  return Number.isFinite(parsed)&&parsed>0?parsed:null;
}

function rational(value) {
  if(typeof value!=='string')return positive(value);
  if(!/^\d+(?:\.\d+)?(?:\/\d+(?:\.\d+)?)?$/.test(value))return null;
  const [numerator,denominator='1']=value.split('/').map(Number);
  return positive(numerator/denominator);
}

export function motionClipTiming(shot, fps, media) {
  const frames=shot.display_end_frame-shot.display_start_frame;
  if(!Number.isInteger(shot.display_start_frame)||shot.display_start_frame<0||!Number.isInteger(shot.display_end_frame)||frames<=0||!Number.isInteger(fps)||fps<=0) {
    throw new Error(`Invalid displayed frame range for ${shot.id}`);
  }
  const streams=(media?.streams||[]).filter(stream=>stream.codec_type==='video');
  if(streams.length!==1)throw new Error(`Motion source ${shot.asset} needs exactly one selected video stream`);
  const stream=streams[0];
  // Container duration can be extended by a longer audio stream. Never use it
  // to infer how long the picture moves, even for a muted video element.
  let sourceDuration=positive(stream.duration),basis='video-stream';
  if(sourceDuration===null){
    const count=positive(stream.nb_read_frames)||positive(stream.nb_frames);
    const rate=rational(stream.avg_frame_rate)||rational(stream.r_frame_rate);
    if(count&&Number.isInteger(count)&&rate){sourceDuration=count/rate;basis='video-frame-count';}
  }
  if(sourceDuration===null)throw new Error(`Motion source ${shot.asset} has no reliable video duration`);
  const duration=frames/fps,rate=Math.min(1,sourceDuration/duration);
  if(rate<0.8-1e-10)throw new Error(`Shot ${shot.id} needs more motion media; refusing to freeze or slow it beyond 20%`);
  // Round down to the same precision emitted in HTML, avoiding source overrun.
  const playbackRate=Math.max(0.8,Math.floor((rate+1e-12)*1e8)/1e8);
  if(duration*playbackRate>sourceDuration+1e-7)throw new Error(`Rounded motion rate overruns source ${shot.asset}`);
  return {shot:shot.id,asset:shot.asset,source_duration_seconds:sourceDuration,
    source_duration_basis:basis,edit_duration_seconds:duration,playback_rate:playbackRate,
    source_consumed_seconds:duration*playbackRate,source_stream:stream};
}

export function probeMotionSource(file) {
  const probe=spawnSync('ffprobe',['-v','error','-select_streams','v:0','-count_frames',
    '-show_entries','stream=codec_type,duration,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames',
    '-of','json',file],{encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
  if(probe.error||probe.status!==0)throw new Error(`Cannot probe motion source ${path.basename(file)}`);
  try{return JSON.parse(probe.stdout);}catch{throw new Error(`Invalid ffprobe result for ${path.basename(file)}`);}
}

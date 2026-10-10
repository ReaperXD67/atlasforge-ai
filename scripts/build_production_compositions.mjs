#!/usr/bin/env node
/** Build deterministic Repair Lab scenes from frozen narration/ASR artifacts.
 * No provider calls, voice guesses, or hand-spaced caption timings happen here.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const INK = '#17191c';
const CREAM = '#f4eedf';
const GOLD = '#efc66a';
const GREEN = '#bce5bd';
const RED = '#ffad9d';
const MUTED = '#b3b0a8';
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const json = value => JSON.stringify(value).replaceAll('<', '\\u003c');
const num = value => Number(value).toFixed(3);
const slug = value => String(value).replace(/[^a-zA-Z0-9-]/g, '-');

export function captionGroups(words, maxWords = 4, maxChars = 27) {
  const groups = [];
  let group = [];
  const flush = () => {
    if (!group.length) return;
    groups.push({ start: group[0].start, end: group.at(-1).end, words: group });
    group = [];
  };
  for (const word of words) {
    if (!word.text?.trim() || !Number.isFinite(word.start) || !Number.isFinite(word.end) || word.end <= word.start) continue;
    const size = [...group, word].map(item => item.text).join(' ').length;
    if (group.length >= maxWords || size > maxChars || (group.length && word.start - group.at(-1).end > 0.45)) flush();
    group.push({ text: word.text.trim(), start: word.start, end: word.end });
    if (/[.!?]$/.test(word.text.trim())) flush();
  }
  flush();
  // A word's acoustic end may precede the next word slightly; a short hold is
  // readable, but a genuine pause must remain empty instead of inventing speech.
  for (let index = 0; index < groups.length; index++) {
    groups[index].end = Math.min(groups[index].end + 0.08, groups[index + 1]?.start ?? Infinity);
  }
  return groups;
}

export function cueBeats(cue, displayCount) {
  const duration = Number(cue.end) - Number(cue.start);
  if (!(duration > 0)) throw new Error(`Invalid measured cue duration: ${cue.id}`);
  const starts = (cue.beats ?? []).map(beat => typeof beat === 'number' ? beat : Number(beat.at ?? beat.start ?? beat.local_seconds ?? beat.time));
  if (starts.some(beat => !Number.isFinite(beat) || beat < 0 || beat >= duration)) throw new Error(`Invalid local ASR beat: ${cue.id}`);
  if (!starts.length) throw new Error(`Missing measured beats: ${cue.id}`);
  const boundaries = [...new Set([0, ...starts.slice(1)])].sort((left, right) => left - right);
  return Array.from({ length: displayCount }, (_, index) => {
    if (index < boundaries.length) return boundaries[index];
    const last = boundaries.at(-1);
    return Math.min(duration - 0.4, last + (duration - last) * (index - boundaries.length + 1) / (displayCount - boundaries.length + 1));
  });
}

export function alignedDisplayBeats(cue, words) {
  const beats = cueBeats(cue, cue.display.length);
  const normal = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
  const local = words.filter(word => word.start >= cue.start && word.start < cue.end);
  cue.display.forEach((text, displayIndex) => {
    if (displayIndex === 0) return; // Immediate first-frame recognition is deliberate.
    const target = normal(text).split(/\s+/).filter(Boolean);
    if (!target.length) return;
    for (let wordIndex = 0; wordIndex < local.length - target.length + 1; wordIndex++) {
      if (target.every((token, offset) => normal(local[wordIndex + offset].text) === token)) {
        beats[displayIndex] = local[wordIndex].start - cue.start;
        break;
      }
    }
  });
  return beats;
}

function fontStyles(prefix = '') {
  return `@font-face{font-family:Montserrat;src:url('${prefix}assets/fonts/Montserrat.ttf') format('truetype');font-weight:100 900;font-display:block}
@font-face{font-family:'IBM Plex Mono';src:url('${prefix}assets/fonts/PlexMono.ttf') format('truetype');font-weight:400 700;font-display:block}`;
}

function itemStatus(cue, text, index, treatment) {
  if (cue.id === '01-before' || cue.id === '03-original') return 'bad';
  if (/^\d+\s*\//.test(text) || /^Hello\s/i.test(text) || /Fictional Sunny/i.test(text)) return 'neutral';
  if (treatment === 'warning') return /fake app|trust bait/i.test(text) ? 'bad' : 'neutral';
  if (/deposit to unlock|book a meeting\?|schedule a call\?|creative solutions|amazing services|passionate digital expert|help your business grow|please book/i.test(text)) return 'bad';
  if (/stop|guarantee|not |≠|no |science|test|who\?|what\?|next\?|validate|verify|permission|honour|respect/i.test(text)) return 'neutral';
  if (treatment === 'message' && cue.id === '01-trap') return 'neutral';
  return 'good';
}

function lineItem(id, text, index, treatment, cue, statusOverride) {
  const label = /^\d+\s*\//.test(text) ? 'SECTION' : cue.id === '14-assembled' ? ['OBSERVATION', 'DEFINED WORK', 'HONEST SAMPLE', 'SMALL QUESTION'][index] : treatment === 'offer' ? ['FOR / DELIVERABLE', 'INCLUDES', 'DETAIL / SCOPE', 'NEXT STEP'][index] : treatment === 'message' ? ['OBSERVATION', 'DELIVERABLE', 'ASK', 'BOUNDARY'][index] : `0${index + 1}`;
  const status = statusOverride ?? itemStatus(cue, text, index, treatment);
  return `<div class="item item-${index} status-${status}" id="${id}-item-${index}"><div class="item-top"><span class="item-label">${status === 'bad' ? 'ISSUE / ' + String(index + 1).padStart(2, '0') : label}</span><svg class="tick" viewBox="0 0 48 38" aria-hidden="true"><path id="${id}-tick-${index}" d="${status === 'bad' ? 'M9 5 L39 33 M39 5 L9 33' : 'M5 19 L17 31 L42 5'}"/></svg></div><div class="item-text">${esc(text)}</div></div>`;
}

function objectMarkup(id, cue, treatment, index) {
  const display = cue.display ?? [];
  if (!display.length || display.length > 4) throw new Error(`Expected 1–4 display strings: ${cue.id}`);
  const items = display.map((text, itemIndex) => lineItem(id, text, itemIndex, treatment, cue));
  const descriptor = treatment === 'message' ? 'MESSAGE WORKSPACE' : treatment === 'offer' ? 'ONE-PAGE OFFER' : treatment === 'compare' ? 'BEFORE / REPAIR' : treatment === 'warning' ? 'RISK CHECK' : treatment === 'checklist' ? 'CLARITY CHECK' : 'WORKING RECIPE';
  const badge = treatment === 'warning' ? 'VERIFY FIRST' : treatment === 'compare' ? 'SHOW THE DIFFERENCE' : 'FICTIONAL / TEACHING EXAMPLE';
  const menuProof = /^(08-proof|08-sample)$/.test(cue.id);
  let content = items.join('');
  if (menuProof) {
    content = `<div class="comparison-half before"><div class="half-label">CROWDED / CONCEPT</div><div class="tiny-menu"><span>SUNNY CAFÉ</span><span>Tea ₹80 · Coffee ₹120 · Sandwich ₹150</span><span>Illustrative menu, not client work</span></div></div><div class="comparison-half after"><div class="half-label">READABLE / CONCEPT</div>${items.map((item, itemIndex) => itemIndex === 0 ? item.replace('status-good', 'status-neutral') : item).join('')}</div>`;
  } else if (treatment === 'compare') {
    const split = cue.id === '01-payoff' && /Creative solutions/i.test(display[0]) ? 1 : 2;
    content = `<div class="comparison-half before"><div class="half-label">BEFORE / ISSUE</div>${display.slice(0, split).map((text, itemIndex) => lineItem(id, text, itemIndex, treatment, cue, 'bad')).join('')}</div><div class="comparison-half after"><div class="half-label">REPAIR / CLEARER</div>${display.slice(split).map((text, itemIndex) => lineItem(id, text, itemIndex + split, treatment, cue, 'good')).join('')}</div>`;
  }
  return `<div class="object object-${menuProof ? 'compare menu-proof' : treatment}" id="${id}-object">
  <div class="object-bar"><span>${descriptor}</span><span class="window-dots" aria-hidden="true">● ● ●</span></div>
  <div class="object-content">${content}</div>
  <div class="object-footer"><span>${badge}</span><span>${String(index + 1).padStart(2, '0')}</span></div>
  </div>`;
}

function sceneCss(id, portrait, treatment, index) {
  const width = portrait ? 1080 : 1920;
  const alternate = index % 2 === 1;
  const warning = treatment === 'warning';
  return `${fontStyles('../../')}
#${id},#${id} *{box-sizing:border-box}
#${id}{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:${INK};color:${CREAM};font-family:Montserrat,sans-serif}
#${id} .scene-inner{position:absolute;inset:0;padding:${portrait ? '98px 100px 390px 76px' : '68px 96px 240px'};display:flex;flex-direction:${portrait ? 'column' : alternate ? 'row-reverse' : 'row'};gap:${portrait ? '46px' : '72px'};align-items:${portrait ? 'stretch' : 'center'}}
#${id} .case-header{position:absolute;left:${portrait ? '76px' : '96px'};right:${portrait ? '100px' : '96px'};top:${portrait ? '64px' : '48px'};display:flex;justify-content:space-between;color:${MUTED};font:400 ${portrait ? '25px' : '24px'}/1.2 'IBM Plex Mono',monospace;letter-spacing:.04em}
#${id} .story{flex:${portrait ? '0 0 auto' : '0 0 620px'};padding-top:${portrait ? '88px' : '28px'};position:relative;z-index:2}
#${id} .chapter{display:inline-flex;gap:18px;align-items:center;font:400 ${portrait ? '27px' : '25px'}/1.4 'IBM Plex Mono',monospace;color:${warning ? RED : GOLD};margin-bottom:26px}
#${id} .chapter-num{font-size:${portrait ? '50px' : '44px'};font-weight:700}
#${id} h1{font-size:${portrait ? '84px' : '80px'};line-height:1.05;letter-spacing:-.045em;margin:0;font-weight:900;max-width:100%;overflow-wrap:break-word}
#${id} .story-rule{margin-top:32px;height:6px;width:170px;background:${warning ? RED : GOLD};transform-origin:left center}
#${id} .story-note{font:400 ${portrait ? '27px' : '26px'}/1.4 'IBM Plex Mono',monospace;color:${MUTED};max-width:${portrait ? '780px' : '590px'};margin-top:26px}
#${id} .object{position:relative;flex:${portrait ? '0 0 auto' : '1'};display:flex;flex-direction:column;min-width:0;max-width:${portrait ? '904px' : '970px'};background:${CREAM};color:${INK};border:3px solid ${GOLD};border-radius:16px;z-index:2;overflow:hidden;align-self:${portrait ? 'stretch' : 'center'};transform-origin:center center}
#${id} .object-bar{display:flex;justify-content:space-between;align-items:center;padding:${portrait ? '24px 30px' : '22px 30px'};background:${INK};color:${CREAM};font:400 ${portrait ? '25px' : '24px'}/1.3 'IBM Plex Mono',monospace;border-bottom:3px solid ${GOLD}}
#${id} .window-dots{font-size:18px;color:${GOLD};letter-spacing:.2em}
#${id} .object-content{display:${treatment === 'compare' ? 'flex' : 'grid'};flex:1;gap:${portrait ? '17px' : '16px'};padding:${portrait ? '28px' : '26px'};min-height:${portrait ? '320px' : '420px'};align-content:center}
#${id} .item{min-width:0;display:flex;flex-direction:column;justify-content:center;padding:${portrait ? '20px 23px' : '18px 24px'};background:${treatment === 'warning' ? RED : treatment === 'message' ? GREEN : CREAM};border:${treatment === 'offer' ? '0' : '2px solid ' + INK};border-bottom:${treatment === 'offer' ? '2px solid ' + INK : ''};border-radius:${treatment === 'message' ? '16px 16px 16px 0' : '2px'};opacity:1;position:relative}
#${id} .item-top{display:flex;justify-content:space-between;align-items:center;gap:14px;min-height:30px;margin-bottom:${portrait ? '12px' : '8px'}}
#${id} .item-label{font:400 ${portrait ? '23px' : '22px'}/1.2 'IBM Plex Mono',monospace;letter-spacing:.025em}
#${id} .item-text{font:700 ${portrait ? '42px' : '38px'}/1.17 Montserrat,sans-serif;letter-spacing:-.025em;overflow-wrap:break-word}
#${id} .tick{width:${portrait ? '36px' : '33px'};height:29px;flex:none;overflow:visible}
#${id} .tick path{stroke:${INK};stroke-width:5px;fill:none;stroke-linecap:round;stroke-linejoin:round}
#${id} .item.status-bad{background:${RED}}
#${id} .item.status-neutral{background:${CREAM}}
#${id} .status-neutral .tick{opacity:0}
#${id} .object-footer{display:flex;justify-content:space-between;gap:16px;padding:${portrait ? '24px 30px' : '19px 30px'};background:${GOLD};color:${INK};font:400 ${portrait ? '22px' : '21px'}/1.3 'IBM Plex Mono',monospace}
#${id} .comparison-half{width:50%;display:flex;flex-direction:column;gap:16px;min-width:0}
#${id} .comparison-half .item{flex:1;background:${CREAM};padding:${portrait ? '18px 14px' : '18px 20px'}}
#${id} .comparison-half.before .item{background:${RED}}
#${id} .comparison-half.after .item{background:${GREEN}}
#${id} .comparison-half.after .item.status-neutral{background:${CREAM}}
#${id} .half-label{font:700 ${portrait ? '22px' : '22px'}/1.3 'IBM Plex Mono',monospace;min-height:58px}
#${id} .object-compare .item-text{font-size:${portrait ? '37px' : '34px'}}
#${id} .object-compare .item-label{font-size:${portrait ? '22px' : '21px'}}
#${id} .tiny-menu{padding:34px 18px;background:${CREAM};border:2px solid ${INK};min-height:330px;display:flex;gap:16px;flex-direction:column;justify-content:center;font:400 24px/1.6 'IBM Plex Mono',monospace;text-align:center}
#${id} .tiny-menu span:first-child{font:900 36px/1.2 Montserrat,sans-serif}
#${id} .menu-proof .object-content{min-height:560px}
#${id} .menu-proof .after .item{padding:10px 16px}
#${id} .menu-proof .after .item-top{margin-bottom:4px}
#${id} .menu-proof .after .item-text{font-size:32px}
#${id} .object-checklist .object-content,#${id} .object-steps .object-content{gap:20px}
#${id} .object-steps .item{border:0;border-bottom:2px solid ${INK};background:${CREAM};padding-left:76px}
#${id} .object-steps .item-label{position:absolute;left:20px;top:20px;font-size:32px;font-weight:700;color:${INK}}
#${id} .back-label{position:absolute;right:40px;bottom:${portrait ? '390px' : '160px'};font:900 ${portrait ? '350px' : '290px'}/1 Montserrat,sans-serif;color:${GOLD};opacity:.1;pointer-events:none;z-index:0}
#${id} .register{position:absolute;left:0;bottom:${portrait ? '450px' : '150px'};width:${width}px;height:3px;background:${GOLD};opacity:.18;z-index:0;transform-origin:left center}
`;
}

function sceneHtml(cue, episode, index) {
  const portrait = episode.format === 'shorts';
  const id = `frame-${String(index + 1).padStart(2, '0')}-${slug(cue.id)}`;
  const duration = Number(cue.end) - Number(cue.start);
  const hasRealComparison = ['01-payoff', '04-problem', '08-proof', '08-sample'].includes(cue.id);
  const treatment = cue.kind === 'recap' ? 'steps' : cue.kind === 'compare' && cue.id === '03-ask' ? 'checklist' : cue.kind === 'compare' && !hasRealComparison ? 'offer' : cue.kind;
  const beats = cueBeats(cue, cue.display.length);
  const note = episode.id === 'pay-first-job-warning' ? (index === 0 || index === episode.segments.length - 1 ? 'Illustrative example. FTC sources in description.' : 'VERIFY THE SOURCE / NOT THE SCREENSHOT') : index === 0 || index === episode.segments.length - 1 ? 'Fictional example. No promised replies or clients.' : cue.kind === 'recap' || cue.kind === 'checklist' ? 'YOUR TURN / CHECK THE WORK' : cue.kind === 'message' ? 'TRY THIS LINE / KEEP IT TRUTHFUL' : cue.kind === 'warning' ? 'KNOW THE BOUNDARY' : 'BEFORE → REPAIR / MAKE IT CONCRETE';
  const shortTitle = index === 0 && portrait ? episode.thumbnail_headline : episode.id === 'pay-first-job-warning' && cue.id === '04-rule' ? 'WAGES, NOT DEPOSITS' : cue.title;
  const registrations = cue.display.map((_, itemIndex) => {
    const time = itemIndex === 0 ? 0 : beats[itemIndex];
    return `tl.fromTo('#${id}-item-${itemIndex}', {x:${itemIndex % 2 ? 28 : -28},y:${treatment === 'steps' ? 16 : 0},opacity:${itemIndex === 0 ? 1 : 0}}, {x:0,y:0,opacity:1,duration:.35,ease:'${itemIndex % 3 === 0 ? 'power3.out' : itemIndex % 3 === 1 ? 'power4.out' : 'power2.out'}'}, ${num(time)});
var tick${itemIndex}=document.getElementById('${id}-tick-${itemIndex}');var len${itemIndex}=tick${itemIndex}.getTotalLength();tick${itemIndex}.style.strokeDasharray=len${itemIndex};
tl.fromTo(tick${itemIndex},{strokeDashoffset:len${itemIndex}},{strokeDashoffset:0,duration:.34,ease:'power2.out'},${num(Math.min(duration - .4, time + .35))});`;
  }).join('\n');
  const meaningfulLater = Math.max(...beats);
  const emphasisAt = Math.min(duration - .65, Math.max(meaningfulLater, duration * .68));
  return { id, duration, beats, html: `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(cue.title)}</title></head><body><template>
<style>${sceneCss(id, portrait, treatment, index)}${cue.id === '14-assembled' ? `#${id} .item-text{font-size:30px;line-height:1.2;font-weight:700}#${id} .object-content{padding:20px;gap:12px}#${id} .item{padding:15px 22px}` : ''}</style>
<div id="${id}" data-composition-id="${id}" data-width="${portrait ? 1080 : 1920}" data-height="${portrait ? 1920 : 1080}" data-duration="${num(duration)}">
<div class="back-label" id="${id}-back" data-layout-ignore>${String(index + 1).padStart(2, '0')}</div><div class="register" id="${id}-register" data-layout-ignore></div>
<div class="case-header"><span>BIZNEX / REPAIR LAB</span><span>${episode.format === 'shorts' ? 'QUICK REPAIR' : 'WORKED EXAMPLE'}</span></div>
<div class="scene-inner"><div class="story"><div class="chapter"><span class="chapter-num">${String(index + 1).padStart(2, '0')}</span><span>${esc(treatment.toUpperCase())}</span></div><h1>${esc(shortTitle)}</h1><div class="story-rule" id="${id}-rule"></div><div class="story-note">${esc(note)}</div></div>${objectMarkup(id, cue, treatment, index)}</div>
</div>
<script>(function(){var tl=gsap.timeline({paused:true});
tl.fromTo('#${id}-object',{scale:.98,rotation:${index % 2 ? '.45' : '-.45'}},{scale:1,rotation:0,duration:.45,ease:'power3.out'},0);
tl.fromTo('#${id}-rule',{scaleX:0},{scaleX:1,duration:.42,ease:'power2.out'},.12);
${registrations}
tl.fromTo('#${id}-object',{borderColor:'${GOLD}'},{borderColor:'${treatment === 'warning' ? RED : GREEN}',duration:.32,ease:'power1.out',immediateRender:false},${num(emphasisAt)});
tl.fromTo('#${id}-register',{scaleX:.82},{scaleX:1,duration:${num(duration)},ease:'none'},0);
window.__timelines['${id}']=tl;
})();</script></template></body></html>` };
}

function indexHtml(episode, audio, scenes) {
  const portrait = episode.format === 'shorts';
  const width = portrait ? 1080 : 1920;
  const height = portrait ? 1920 : 1080;
  const duration = Number(audio.total_duration_s);
  const words = audio.voices.flatMap(voice => voice.words ?? []);
  const groups = captionGroups(words, 4, portrait ? 26 : 36);
  if (!groups.length) throw new Error(`${episode.id}: no ASR word timings for captions`);
  const voice = audio.voices[0];
  if (audio.voices.length !== 1) throw new Error(`${episode.id}: expected a single continuous narration file`);
  const scenesMarkup = scenes.map((scene, index) => `<div id="el-${scene.id}" class="clip" data-composition-id="${scene.id}" data-composition-src="compositions/frames/${esc(audio.cues[index].id)}.html" data-start="${num(audio.cues[index].start)}" data-duration="${num(scene.duration)}" data-track-index="${index % 2 + 1}" data-width="${width}" data-height="${height}"></div>`).join('\n');
  const sfx = (audio.sfx ?? []).map((effect, index) => `<audio id="sfx-${index}" src="${esc(effect.file)}" data-start="${num(effect.offset_s)}" data-duration="${num(effect.duration_s)}" data-track-index="13" data-volume="${effect.volume ?? .14}"></audio>`).join('\n');
  const bgm = audio.bgm ? `<audio id="bgm" src="${esc(audio.bgm.path)}" data-start="0" data-duration="${num(Math.min(duration, audio.bgm.duration_s))}" data-track-index="11" data-volume="${audio.bgm.volume ?? .10}"></audio>` : '';
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(episode.title)}</title><script src="assets/vendor/gsap.min.js"></script>
<style>${fontStyles()}
*{box-sizing:border-box}html,body{margin:0;background:${INK};width:100%;height:100%;overflow:hidden}#root{position:relative;width:100%;height:100%;overflow:hidden;background:${INK};color:${CREAM}}
#root>.clip[data-composition-src]{position:absolute;inset:0;width:100%;height:100%}
#caption-track{position:absolute;inset:0;pointer-events:none;z-index:30}
#caption-box{position:absolute;left:${portrait ? '76px' : '180px'};right:${portrait ? '112px' : '180px'};bottom:${portrait ? '292px' : '95px'};min-height:${portrait ? '132px' : '90px'};display:flex;justify-content:center;align-items:center}
#caption-line{max-width:100%;padding:${portrait ? '18px 24px' : '12px 24px'};background:${INK};border:2px solid ${CREAM};border-radius:8px;font:900 ${portrait ? '55px' : '48px'}/1.18 Montserrat,sans-serif;letter-spacing:-.025em;text-align:center}
#caption-line span{display:inline;color:${CREAM};padding:2px 4px;border-radius:4px}
#caption-line span.active{background:${GOLD};color:${INK}}
#runtime-progress{position:absolute;left:${portrait ? '76px' : '96px'};right:${portrait ? '100px' : '96px'};bottom:${portrait ? '250px' : '46px'};height:5px;background:${MUTED};z-index:31}
#progress-fill{width:100%;height:100%;background:${GOLD};transform-origin:left center}
#caption-placeholder{font-size:inherit}
</style></head><body><div id="root" data-composition-id="main" data-width="${width}" data-height="${height}" data-duration="${num(duration)}">
${scenesMarkup}
<div id="caption-track" class="clip" data-start="0" data-duration="${num(duration)}" data-track-index="5"><div id="caption-box"><div id="caption-line"><span id="caption-placeholder">${esc(groups[0].words.map(word => word.text).join(' '))}</span></div></div></div>
<div id="runtime-progress" data-layout-ignore><div id="progress-fill"></div></div>
<audio id="voiceover" src="${esc(voice.path)}" data-start="0" data-duration="${num(voice.duration_s)}" data-track-index="10" data-volume="1"></audio>
${bgm}\n${sfx}
</div><script>(function(){
var groups=${json(groups)};var driver={t:0};var lastGroup=-2;var lastWord=-2;var line=document.getElementById('caption-line');var spans=[];
function updateCaption(){var time=driver.t;var low=0,high=groups.length-1,found=-1;while(low<=high){var middle=(low+high)>>1;if(groups[middle].start<=time){found=middle;low=middle+1}else high=middle-1;}
if(found>=0&&time>groups[found].end)found=-1;
if(found!==lastGroup){line.textContent='';spans=[];if(found>=0){groups[found].words.forEach(function(word,index){if(index)line.appendChild(document.createTextNode(' '));var span=document.createElement('span');span.textContent=word.text;line.appendChild(span);spans.push(span);});}line.style.opacity=found<0?'0':'1';lastGroup=found;lastWord=-2;}
if(found>=0){var wordIndex=-1;groups[found].words.forEach(function(word,index){if(time>=word.start&&time<=word.end)wordIndex=index;});if(wordIndex!==lastWord){spans.forEach(function(span,index){span.className=index===wordIndex?'active':'';});lastWord=wordIndex;}}
}
var tl=gsap.timeline({paused:true});tl.fromTo(driver,{t:0},{t:${num(duration)},duration:${num(duration)},ease:'none',onUpdate:updateCaption},0);
tl.fromTo('#progress-fill',{scaleX:0},{scaleX:1,duration:${num(duration)},ease:'none'},0);
window.__timelines['main']=tl;
})();</script></body></html>`;
}

function thumbnailHtml(episode, headline) {
  const portrait = episode.format === 'shorts';
  const warning = episode.id === 'pay-first-job-warning';
  const offer = episode.id.includes('offer');
  const labels = warning ? ['TASKS COMPLETE', 'DEPOSIT TO UNLOCK', 'DO NOT PAY'] : offer ? ['Creative solutions?', 'One café menu page', 'NOW IT IS CLEAR'] : ['Amazing services?', 'A clearer menu sample', 'A SMALLER ASK'];
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(headline)}</title><style>${fontStyles()}
*{box-sizing:border-box}html,body{margin:0;width:${portrait ? 1080 : 1280}px;height:${portrait ? 1920 : 720}px;overflow:hidden;background:${INK};color:${CREAM};font-family:Montserrat,sans-serif}
.thumb{position:absolute;inset:0;padding:${portrait ? '100px 86px 260px' : '58px 66px'};display:flex;flex-direction:${portrait ? 'column' : 'row'};gap:${portrait ? '72px' : '46px'};align-items:${portrait ? 'stretch' : 'center'}}
.heading{flex:${portrait ? '0 0 auto' : '0 0 540px'};position:relative;z-index:2}.eyebrow{font:400 ${portrait ? '29px' : '22px'}/1.3 'IBM Plex Mono',monospace;color:${GOLD};letter-spacing:.025em;margin-bottom:34px}
h1{margin:0;font-weight:900;font-size:${portrait ? '144px' : '99px'};line-height:.98;letter-spacing:-.055em;overflow-wrap:break-word;max-width:100%}.underline{margin-top:38px;width:180px;height:9px;background:${warning ? RED : GOLD}}
.example{position:relative;flex:${portrait ? '0 0 auto' : '1'};display:flex;flex-direction:column;min-width:0;border:3px solid ${GOLD};border-radius:16px;background:${CREAM};color:${INK};overflow:hidden;z-index:2}
.bar{padding:${portrait ? '30px' : '20px 24px'};font:400 ${portrait ? '28px' : '21px'}/1.2 'IBM Plex Mono',monospace;background:${INK};color:${CREAM};border-bottom:3px solid ${GOLD}}
.content{flex:1;padding:${portrait ? '40px' : '28px'};display:grid;gap:${portrait ? '38px' : '24px'}}.bubble{padding:${portrait ? '40px 30px' : '24px 22px'};border:3px solid ${INK};border-radius:8px;font:700 ${portrait ? '55px' : '36px'}/1.12 Montserrat,sans-serif;letter-spacing:-.025em;background:${RED}}
.bubble.good{background:${warning ? RED : GREEN}}.arrow{text-align:center;font:900 ${portrait ? '104px' : '70px'}/1 Montserrat,sans-serif;color:${INK}}
.stamp{padding:${portrait ? '32px' : '24px'};font:900 ${portrait ? '43px' : '28px'}/1.1 Montserrat,sans-serif;background:${warning ? RED : GOLD};color:${INK}}
.credit{position:absolute;left:${portrait ? '86px' : '66px'};bottom:${portrait ? '216px' : '30px'};font:400 ${portrait ? '26px' : '20px'}/1.2 'IBM Plex Mono',monospace;color:${MUTED}}
</style></head><body><div class="thumb"><div class="heading"><div class="eyebrow">BIZNEX / REPAIR LAB</div><h1>${esc(headline)}</h1><div class="underline"></div></div><div class="example"><div class="bar">${warning ? 'FICTIONAL TASK APP' : offer ? 'OFFER REPAIR' : 'MESSAGE REPAIR'}</div><div class="content"><div class="bubble">${esc(labels[0])}</div><div class="arrow">↓</div><div class="bubble good">${esc(labels[1])}</div></div><div class="stamp">${esc(labels[2])}</div></div></div><div class="credit">${warning ? 'FTC-BASED WARNING · ILLUSTRATIVE EXAMPLE' : 'BEFORE → AFTER · FICTIONAL EXAMPLE'}</div></body></html>`;
}

export function buildEpisode(project, episode) {
  const read = file => JSON.parse(fs.readFileSync(path.join(project, file), 'utf8'));
  const audio = read('audio_meta.json');
  if (audio.cues.length !== episode.segments.length) throw new Error(`${episode.id}: cue/scene count mismatch`);
  const words = audio.voices.flatMap(voice => voice.words ?? []);
  const scenes = audio.cues.map((timing, index) => {
    const cue = { ...episode.segments[index], ...timing };
    if (cue.id === '14-assembled') cue.display = [
      'Hello Sunny Café, I noticed your menu prices are difficult to read on mobile.',
      'I build simple menu pages with clear prices.',
      'I made a labelled concept sample showing a cleaner layout.',
      'Would you like me to send it?',
    ];
    const beats = alignedDisplayBeats(cue, words);
    const slotEnd = audio.cues[index + 1]?.start ?? audio.total_duration_s;
    return sceneHtml({ ...cue, end: slotEnd, beats: [0, ...beats.slice(1)] }, episode, index);
  });
  const compositions = path.join(project, 'compositions', 'frames');
  fs.mkdirSync(compositions, { recursive: true });
  for (let index = 0; index < scenes.length; index++) {
    const scene = scenes[index];
    const filename = slug(audio.cues[index].id);
    fs.writeFileSync(path.join(compositions, `${filename}.html`), scene.html);
    fs.writeFileSync(path.join(compositions, `${filename}.motion.json`), JSON.stringify({
      frame_id: scene.id, duration: scene.duration,
      rules: ['dynamic-content-sequencing', 'discrete-text-sequence', 'svg-path-draw'],
      entry: { direction: index % 2 ? 'right' : 'left', duration: .45 }, exit: { type: 'hard-cut', duration: 0 },
      assertions: [
        { kind: 'appearsBy', selector: `#${scene.id}-object`, bySec: .5 },
        { kind: 'staysInFrame', selector: `#${scene.id}-object` },
        ...scene.beats.map((beat, itemIndex) => ({ kind: 'appearsBy', selector: `#${scene.id}-item-${itemIndex}`, bySec: Math.min(scene.duration - .05, beat + .5) })),
      ],
      reveal_times: scene.beats,
      note: 'First object/title present at t=0; subsequent object fields reveal on measured ASR anchors. No breathing loop substitutes for explanation.'
    }, null, 2) + '\n');
  }
  let index = indexHtml(episode, audio, scenes);
  // Captions are a proper composition, not an opaque nested Studio track. The
  // child owns its ASR driver; the main timeline owns only its progress strip.
  const captionStart = index.indexOf('<div id="caption-track"');
  const captionEnd = index.indexOf('<div id="runtime-progress"', captionStart);
  const captionMarkup = index.slice(captionStart, captionEnd).replace(/ class="clip" data-start="[^"]*" data-duration="[^"]*" data-track-index="5"/, '');
  const cssStart = index.indexOf('#caption-track{');
  const cssEnd = index.indexOf('</style>', cssStart);
  const captionCss = index.slice(cssStart, cssEnd);
  const scriptStart = index.indexOf('<script>(function(){\nvar groups=');
  const scriptEnd = index.indexOf('</script>', scriptStart) + '</script>'.length;
  const captionScript = index.slice(scriptStart, scriptEnd)
    .replace(/tl\.fromTo\('#progress-fill'[^\n]*\n/, '')
    .replace("window.__timelines['main']=tl;", "window.__timelines['captions']=tl;");
  const portrait = episode.format === 'shorts';
  fs.writeFileSync(path.join(project, 'compositions', 'captions.html'), `<!doctype html><html><head><meta charset="utf-8"></head><body><template><style>${fontStyles('../')}#captions{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}${captionCss}</style><div id="captions" data-composition-id="captions" data-width="${portrait ? 1080 : 1920}" data-height="${portrait ? 1920 : 1080}" data-duration="${num(audio.total_duration_s)}">${captionMarkup}</div>${captionScript}</template></body></html>`);
  index = index.slice(0, scriptStart) + `<script>(function(){var tl=gsap.timeline({paused:true});tl.fromTo('#progress-fill',{scaleX:0},{scaleX:1,duration:${num(audio.total_duration_s)},ease:'none'},0);window.__timelines['main']=tl;})();</script>` + index.slice(scriptEnd);
  index = index.slice(0, captionStart) + `<div id="el-captions" class="clip" style="z-index:30;pointer-events:none" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="${num(audio.total_duration_s)}" data-track-index="5" data-track-kind="captions" data-width="${portrait ? 1080 : 1920}" data-height="${portrait ? 1920 : 1080}"></div>\n` + index.slice(captionEnd);
  fs.writeFileSync(path.join(project, 'index.html'), index);
  const headline = fs.readFileSync(path.join(project, 'THUMBNAIL_COPY.txt'), 'utf8').trim();
  fs.writeFileSync(path.join(project, 'THUMBNAIL.html'), thumbnailHtml(episode, headline));
  const storyboardPath = path.join(project, 'STORYBOARD.md');
  if (fs.existsSync(storyboardPath)) {
    fs.writeFileSync(storyboardPath, fs.readFileSync(storyboardPath, 'utf8').replace(/^- status: outline$/gm, '- status: animated'));
  }
  fs.mkdirSync(path.join(project, '.hyperframes'), { recursive: true });
  fs.writeFileSync(path.join(project, '.hyperframes', 'animation-map.md'), `# Repair Lab motion ledger\n\nMeasured voice and ASR determine every slot and reveal; the reusable caption driver writes only on phrase/word changes. Hard cuts preserve readable templates.\n\n| Scene | Start | Duration | Reveal times (local seconds) | Treatment |\n| --- | ---: | ---: | --- | --- |\n${scenes.map((scene, index) => `| ${scene.id} | ${num(audio.cues[index].start)} | ${num(scene.duration)} | ${scene.beats.map(num).join(', ')} | ${episode.segments[index].kind} |`).join('\n')}\n`);
  console.log(`${episode.id}: ${scenes.length} measured scenes, ${num(audio.total_duration_s)}s, ${episode.format}`);
  return { id: episode.id, scenes: scenes.length, duration: audio.total_duration_s };
}

function main() {
  const argv = process.argv.slice(2);
  const flag = argv.indexOf('--creative');
  const creativePath = flag >= 0 ? argv[flag + 1] : 'config/batches/biznex-repair-lab.creative.json';
  if (!creativePath) throw new Error('--creative requires a file path');
  const creative = JSON.parse(fs.readFileSync(creativePath, 'utf8'));
  const requested = argv.includes('--only') ? argv[argv.indexOf('--only') + 1] : null;
  for (const item of creative.episodes) {
    if (requested && requested !== item.id) continue;
    const project = path.resolve(item.project);
    const prepared = JSON.parse(fs.readFileSync(path.join(project, 'EPISODE.json'), 'utf8'));
    if (prepared.id !== item.id) throw new Error(`${item.id}: prepared episode identity mismatch`);
    buildEpisode(project, prepared);
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) main();

#!/usr/bin/env node
/** Story-first illustrated HyperFrames renderer. Provider-free, measured and seek-safe.
 * Registry provenance: the sender-corner message pop and bounded three-dot indicator
 * adapt compositions/components/chat-message.html and typing-indicator.html installed
 * in biznex-unsent-message. Their sample timing, remote scripts and padding tweens
 * are deliberately NOT copied: every narrative change below uses measured speech.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { captionGroups } from './build_production_compositions.mjs';

export const PALETTE = Object.freeze({ cream: '#f6efdf', ink: '#282425', red: '#be4f3c', teal: '#316b67', gold: '#e6bd70' });
const { cream, ink, red, teal, gold } = PALETTE;
export const WORLD_TYPES = Object.freeze(['room', 'phone', 'cupboard', 'paper', 'calendar', 'split']);
export const escapeHtml = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const esc = escapeHtml;
const js = value => JSON.stringify(value).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029');
const n = value => Number(value).toFixed(3);
const slug = value => String(value).replace(/[^a-zA-Z0-9-]/g, '-');
const normal = value => String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[’']/g, '').replace(/[^a-z0-9]+/g, ' ').trim();

/** Returns LOCAL seconds from a literal, contiguous measured word sequence.
 * Never falls back to a percentage or an estimated segment duration.
 */
export function phraseTime(cue, words, phrase, occurrence = 0) {
  if (typeof phrase !== 'string' || !normal(phrase)) throw new Error(`${cue.id}: a non-empty literal at_phrase is required`);
  const target = normal(phrase).split(' ');
  const tokens = words.filter(word => Number.isFinite(word.start) && Number.isFinite(word.end) && word.end > word.start && word.start >= Number(cue.start) - .035 && word.start < Number(cue.end))
    .flatMap(word => normal(word.text).split(' ').filter(Boolean).map(text => ({ text, start: word.start })));
  let seen = 0;
  for (let index = 0; index <= tokens.length - target.length; index++) {
    if (target.every((token, offset) => token === tokens[index + offset].text) && seen++ === occurrence) return Math.max(0, tokens[index].start - Number(cue.start));
  }
  throw new Error(`${cue.id}: literal speech anchor not found: ${phrase}`);
}

export function sceneEvents(cue, words) {
  const visual = cue.visual;
  if (!visual || !WORLD_TYPES.includes(visual.type)) throw new Error(`${cue.id}: unsupported or missing story visual type`);
  if (visual.expression && !['thinking', 'concerned', 'relieved'].includes(visual.expression)) throw new Error(`${cue.id}: unsupported expression`);
  if (visual.camera && !['wide', 'close', 'over-shoulder'].includes(visual.camera)) throw new Error(`${cue.id}: unsupported camera`);
  if (!['none', 'delete', 'reveal', 'send', 'sort', 'close', 'wait'].includes(visual.action ?? 'none')) throw new Error(`${cue.id}: unsupported action`);
  const events = (visual.messages ?? []).map((message, index) => {
    if (!['Asha', 'Mira', 'draft'].includes(message.sender)) throw new Error(`${cue.id}: unsupported message sender`);
    if (!String(message.text ?? '').trim() || String(message.text).length > 150) throw new Error(`${cue.id}: message needs 1–150 readable characters`);
    return { kind: 'message', index, at: message.at_phrase ? phraseTime(cue, words, message.at_phrase) : index === 0 ? 0 : (() => { throw new Error(`${cue.id}: later message lacks at_phrase`); })(), phrase: message.at_phrase ?? '', ...message };
  });
  if ((visual.action ?? 'none') !== 'none') {
    events.push({ kind: 'action', action: visual.action, at: phraseTime(cue, words, visual.action_phrase), phrase: visual.action_phrase });
    // A locked "recommendation. Delete. explanation. Delete." is two actions,
    // not one deletion followed by a magically disappearing second draft.
    if (visual.action === 'delete' && normal(visual.action_phrase) === 'delete' && (visual.messages ?? []).filter(message => message.sender === 'draft').length > 1) {
      const occurrences = words.filter(word => word.start >= Number(cue.start) && word.start < Number(cue.end)).flatMap(word => normal(word.text).split(' ')).filter(token => token === 'delete').length;
      for (let index = 1; index < Math.min(occurrences, visual.messages.length); index++) events.push({ kind: 'action', action: 'delete', at: phraseTime(cue, words, visual.action_phrase, index), phrase: visual.action_phrase });
    }
  }
  return events.sort((left, right) => left.at - right.at || (left.kind === 'message' ? -1 : 1));
}

function fonts(prefix = '') {
  return `@font-face{font-family:Fraunces;src:url('${prefix}assets/fonts/Fraunces.ttf') format('truetype');font-weight:100 900;font-display:block}
@font-face{font-family:Montserrat;src:url('${prefix}assets/fonts/Montserrat.ttf') format('truetype');font-weight:100 900;font-display:block}`;
}

/** An original single silhouette, not a jointed puppet. Identity is stable across worlds. */
export function characterSvg(name = 'Mira', expression = 'thinking', prefix = 'person') {
  const asha = name === 'Asha';
  const top = asha ? red : teal;
  const mouth = expression === 'relieved' ? 'M142 158 Q160 177 179 157' : expression === 'concerned' ? 'M145 169 Q160 157 176 168' : 'M149 165 Q161 168 174 164';
  const brow = expression === 'concerned' ? 'M121 123 L140 127 M177 127 L196 122' : 'M121 124 Q130 120 140 124 M178 124 Q187 120 197 125';
  return `<svg class="character-portrait" viewBox="0 0 320 470" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${name}, ${expression}"><g id="${prefix}-silhouette"><path d="M77 211 Q39 294 51 449 L271 449 Q287 284 237 213 Q218 188 203 188 L118 188 Q91 193 77 211" fill="${top}" stroke="${ink}" stroke-width="5"/><path d="M117 199 Q162 239 204 199 L195 187 L123 186Z" fill="#b9704f"/><path d="M91 87 Q93 21 157 20 Q232 20 231 95 L223 191 Q246 216 234 254 Q217 242 208 208 L103 207 Q74 232 69 259 Q49 187 80 147Z" fill="${ink}"/>${asha ? '' : `<circle cx="227" cy="43" r="35" fill="${ink}"/><path d="M207 21 Q243 24 245 55" fill="none" stroke="${gold}" stroke-width="6"/>`}<ellipse cx="160" cy="120" rx="65" ry="83" fill="#c8825c" stroke="${ink}" stroke-width="4"/><path d="M95 106 Q92 33 156 30 Q215 31 226 103 Q184 101 168 61 Q145 104 95 106" fill="${ink}"/><path d="${brow}" fill="none" stroke="${ink}" stroke-width="5" stroke-linecap="round"/><ellipse cx="132" cy="136" rx="5" ry="7" fill="${ink}"/><ellipse cx="187" cy="136" rx="5" ry="7" fill="${ink}"/><path d="M159 139 L153 154 L162 155" fill="none" stroke="#8b4f39" stroke-width="3" stroke-linecap="round"/><path d="${mouth}" fill="none" stroke="${ink}" stroke-width="4" stroke-linecap="round"/><circle cx="100" cy="155" r="6" fill="${gold}"/><circle cx="220" cy="155" r="6" fill="${gold}"/><path d="M86 286 Q105 315 129 337 M231 287 Q206 321 183 337" fill="none" stroke="${ink}" stroke-width="5" stroke-linecap="round"/><path d="M111 342 Q130 327 156 339 L194 339 Q205 354 186 366 L131 366 Q111 365 111 342" fill="#c8825c" stroke="${ink}" stroke-width="4"/><path d="M66 445 L66 468 M253 445 L253 468" fill="none" stroke="${ink}" stroke-width="7"/></g></svg>`;
}

function roomSvg(id, name = 'Mira', expression = 'thinking') {
  return `<svg class="room-art" viewBox="0 0 1000 900" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M0 720H1000V900H0Z" fill="${gold}"/><path d="M0 720H1000 M110 720L15 900 M310 720L255 900 M520 720V900 M730 720L785 900 M910 720L995 900" fill="none" stroke="${ink}" stroke-opacity=".17" stroke-width="4"/><rect x="510" y="58" width="368" height="332" rx="110" fill="${teal}" stroke="${ink}" stroke-width="7"/><circle cx="774" cy="133" r="41" fill="${cream}"/><path d="M694 133L702 125 M604 203L613 195 M817 254L826 246 M548 128L557 120" stroke="${gold}" stroke-width="7" stroke-linecap="round"/><path d="M694 58V390 M510 230H878" stroke="${ink}" stroke-width="7"/><path d="M473 31Q490 250 472 421 M913 31Q893 250 913 421" stroke="${red}" stroke-width="34" fill="none"/><rect x="50" y="447" width="520" height="322" rx="54" fill="${red}" stroke="${ink}" stroke-width="6"/><rect x="39" y="582" width="548" height="131" rx="44" fill="${red}" stroke="${ink}" stroke-width="6"/><path d="M84 766V804 M531 766V804" stroke="${ink}" stroke-width="15"/><path d="M68 524Q174 483 268 525 M287 524Q395 483 503 524" fill="none" stroke="${cream}" stroke-opacity=".45" stroke-width="4"/><path d="M754 548H922V571H754Z M789 571L770 780 M888 571L908 780" fill="${teal}" stroke="${ink}" stroke-width="5"/><path d="M835 549V318 M781 318H891L866 240H806Z" fill="${gold}" stroke="${ink}" stroke-width="5"/><path d="M914 704Q945 625 940 568 M940 630Q889 581 914 557Q949 576 940 630 M942 606Q983 561 990 593Q988 623 943 642" fill="${teal}" stroke="${ink}" stroke-width="4"/><path d="M910 689H978L967 772H925Z" fill="${red}" stroke="${ink}" stroke-width="4"/><path d="M656 653H716V708Q681 731 656 708Z M716 660Q750 650 742 686Q735 700 717 689" fill="${cream}" stroke="${ink}" stroke-width="5"/><path id="${id}-steam" d="M675 640Q659 625 675 610 M698 640Q682 625 698 610" fill="none" stroke="${ink}" stroke-width="3" stroke-opacity=".5"/></svg><div class="room-character" id="${id}-character">${characterSvg(name, expression, `${id}-${name.toLowerCase()}`)}</div>`;
}

function messagesMarkup(id, visual, events, compact = false) {
  const messages = visual.messages ?? [];
  const content = messages.length ? messages.map((message, index) => `<div class="message-state sender-${message.sender.toLowerCase()}" id="${id}-message-${index}"><div class="sender-name">${message.sender === 'draft' ? 'MIRA / UNSENT DRAFT' : esc(message.sender)}</div><div class="message-bubble">${esc(message.text)}</div><div class="receipt">${message.sender === 'draft' ? 'DRAFT · NOT SENT' : message.sender === 'Asha' ? 'RECEIVED' : 'MIRA’S MESSAGE'}</div></div>`).join('') : `<div class="message-state" id="${id}-message-empty"><div class="sender-name">MIRA</div><div class="message-bubble">${esc(visual.screen_title || visual.note || 'A moment to think.')}</div></div>`;
  const prior = visual.prior_draft ? `<div class="message-state sender-draft" id="${id}-prior-draft"><div class="sender-name">MIRA / UNSENT DRAFT</div><div class="message-bubble">${esc(visual.prior_draft)}</div><div class="receipt">DRAFT · NOT SENT</div></div>` : '';
  const call = /call/i.test(visual.action_phrase ?? '') || /^Call /i.test(visual.screen_title ?? '');
  const control = call ? `<svg viewBox="0 0 48 48" width="35" height="35" aria-hidden="true"><path d="M11 7L18 6L23 18L18 23Q23 32 31 34L36 28L45 34L43 42Q22 47 7 22Q3 14 11 7Z" fill="${cream}"/></svg>` : '↑';
  return `<div class="story-phone ${compact ? 'compact-phone' : ''}" id="${id}-phone"><div class="phone-top"><span class="phone-camera" aria-hidden="true"></span><span>${esc(visual.screen_title || 'Asha + Mira')}</span></div><div class="phone-content">${content}${prior}<div class="typing-indicator" id="${id}-typing" aria-label="Pause, no new message"><span></span><span></span><span></span></div></div><div class="phone-controls"><span id="${id}-control-label">${call ? 'CALL' : messages.some(message => message.sender === 'draft') ? 'UNSENT' : 'CONVERSATION'}</span><span class="send-control" id="${id}-send">${control}</span></div><div class="phone-bottom" aria-hidden="true"></div></div>`;
}

function cupboardMarkup(id, visual) {
  const items = visual.items?.length ? visual.items : [{ label: 'Already here', quantity: 1 }, { label: 'Check first', quantity: 1 }, { label: 'Enough for now', quantity: 1 }];
  if (items.length > 6) throw new Error(`${id}: cupboard supports at most six named supply groups`);
  return `<div class="cupboard ${items.length <= 3 ? 'single-shelf-groups' : ''}" id="${id}-cupboard"><div class="cupboard-cornice"></div><div class="cupboard-back"><div class="shelf-lines" aria-hidden="true"><i></i><i></i><i></i></div>${items.map((item, index) => {
    const quantity = Number(item.quantity ?? 1);
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 7) throw new Error(`${id}: visible quantity must be 1–7`);
    const objects = Array.from({ length: quantity }, (_, objectIndex) => `<g class="supply-object" transform="translate(${objectIndex * 150} 0)"><path d="${/tube/i.test(item.label) ? 'M38 12H126L116 143H48Z M48 143H116V157H48Z' : 'M25 35H135V150H25Z M47 9H113V36H47Z'}" fill="${index % 2 ? gold : cream}" stroke="${ink}" stroke-width="5"/><path d="M44 54H116V119H44Z" fill="${index % 2 ? cream : teal}"/><path d="M59 73H102 M59 89H102 M59 105H90" stroke="${index % 2 ? teal : cream}" stroke-width="6"/></g>`).join('');
    return `<div class="supply supply-${index}" id="${id}-supply-${index}"><svg viewBox="0 0 ${quantity * 150 + 10} 160" aria-hidden="true">${objects}</svg><div class="supply-label">${esc(item.label)}</div><div class="supply-count">${quantity} here</div></div>`;
  }).join('')}</div><div class="cupboard-door" id="${id}-door"><div class="door-panel"></div><i></i></div></div><div class="inventory-note" id="${id}-inventory"><span>BEFORE ADDING MORE</span><strong>Use what we have first.</strong><svg class="inventory-underline" viewBox="0 0 480 24" aria-hidden="true"><path id="${id}-inventory-stroke" d="M6 15Q232 4 472 15"/></svg></div><div class="cart-slip" id="${id}-cart"><span>SHOPPING LIST</span><strong>${esc(visual.screen_title || 'Check first')}</strong><span id="${id}-cart-state">OPEN</span></div>`;
}

function paperMarkup(id, visual) {
  const lines = visual.messages?.length ? visual.messages.map(message => message.text) : visual.screen_title === 'The fridge note' ? ['Use what we have first.'] : visual.items?.length ? visual.items.map(item => `${item.label}${item.quantity === undefined ? '' : ': ' + item.quantity}`) : [visual.screen_title || 'One small question.'];
  return `<div class="table-surface"></div><div class="paper-sheet" id="${id}-paper"><div class="paper-holes" aria-hidden="true"><i></i><i></i><i></i></div><div class="paper-title">${esc(visual.screen_title || 'Mira’s note')}</div>${lines.slice(0, 3).map((line, index) => `<div class="paper-line" id="${id}-paper-line-${index}">${esc(line)}<svg class="strike-svg" viewBox="0 0 700 80" preserveAspectRatio="none" aria-hidden="true"><path id="${id}-strike-${index}" d="M10 58Q310 4 685 30"/></svg></div>`).join('')}<div class="paper-rule"></div><div class="hand-note" id="${id}-hand-note">${visual.screen_title?.includes('Shopping') || visual.screen_title === 'The fridge note' ? 'Use what we have first.' : 'A person, not a pitch.'}</div></div><div class="pencil" id="${id}-pencil" aria-hidden="true"></div><div class="tea-cup" aria-hidden="true"><i></i></div>`;
}

function calendarMarkup(id, visual) {
  return `<div class="calendar-page" id="${id}-calendar"><div class="calendar-rings" aria-hidden="true"><i></i><i></i></div><div class="calendar-kicker">SAVE THE TIME</div><div class="calendar-day">Saturday</div><div class="calendar-line"></div><div class="calendar-plan">Lunch with Asha</div><svg class="calendar-circle" viewBox="0 0 700 230" preserveAspectRatio="none" aria-hidden="true"><path id="${id}-circle" d="M640 131C608 13 108 12 57 103C-13 234 625 251 653 140"/></svg><div class="calendar-note">Just lunch. Just friends.</div><div class="calendar-date">MIRA + ASHA</div></div><div class="lunch-plate" aria-hidden="true"><i></i><i></i></div><div class="lunch-cup" aria-hidden="true"></div><div class="calendar-reply" id="${id}-calendar-reply">${messagesMarkup(id, visual, [], true)}</div>`;
}

/** Reserve room for sender, acoustic message state, receipt and controls. Longer
 * authored dialogue gets a taller foreground phone rather than clipped receipts.
 * Final font/geometry is still checked against the actual browser pixels.
 */
export function phoneContentFit(visual, portrait) {
  const characters = Math.max(0, ...(visual.messages ?? []).map(message => [...String(message.text)].length));
  const extended = characters > 42;
  return { characters, heightPercent: extended ? 75 : 67, topPercent: extended ? 20 : 27, fontPx: portrait ? extended ? 36 : 41 : extended ? 38 : 43 };
}

export function worldMarkup(id, visual, events = []) {
  if (visual.type === 'room') return `<div class="room-setting">${roomSvg(id, 'Mira', visual.expression)}</div><div class="room-conversation">${messagesMarkup(id, visual, events, true)}</div>`;
  if (visual.type === 'phone') return `<div class="phone-scene-lines" aria-hidden="true"></div><div class="phone-portrait">${characterSvg('Mira', visual.expression, `${id}-mira`)}</div>${messagesMarkup(id, visual, events)}`;
  if (visual.type === 'cupboard') return cupboardMarkup(id, visual);
  if (visual.type === 'paper') return paperMarkup(id, visual);
  if (visual.type === 'calendar') return calendarMarkup(id, visual);
  if (visual.type === 'split') return `<div class="split-room mira-room"><div class="split-window" aria-hidden="true"></div><div class="split-person">${characterSvg('Mira', visual.expression, `${id}-mira`)}</div><span>Mira</span></div><div class="split-room asha-room"><div class="split-window" aria-hidden="true"></div><div class="split-person">${characterSvg('Asha', visual.expression === 'relieved' ? 'relieved' : 'thinking', `${id}-asha`)}</div><span>Asha</span></div><div class="split-conversation">${messagesMarkup(id, visual, events, true)}</div>`;
  throw new Error(`Unknown story world: ${visual.type}`);
}

function sceneCss(id, portrait, visual = {}) {
  const calendarFit = phoneContentFit(visual, portrait);
  return `${fonts('../../')}
#${id},#${id} *{box-sizing:border-box}#${id}{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:${cream};color:${ink};font-family:Montserrat,sans-serif}
#${id} .fiction-label{position:absolute;left:${portrait ? 80 : 88}px;top:${portrait ? 208 : 54}px;font-size:${portrait ? 26 : 25}px;line-height:1.2;font-weight:700;letter-spacing:.045em;z-index:8;padding:10px 0;border-bottom:3px solid ${red}}
#${id} .episode-mark{position:absolute;right:${portrait ? 160 : 88}px;top:${portrait ? 210 : 56}px;font-size:${portrait ? 23 : 24}px;font-weight:700;z-index:8;color:${teal}}
#${id} .story-heading{position:absolute;left:${portrait ? 80 : 90}px;top:${portrait ? 299 : 190}px;width:${portrait ? 830 : 650}px;z-index:5}
#${id} h1{margin:0;font:900 ${portrait ? 80 : 92}px/1.04 Fraunces,serif;letter-spacing:-.035em;overflow-wrap:break-word;max-width:100%}
#${id} .scene-note{font:400 ${portrait ? 30 : 32}px/1.35 Montserrat,sans-serif;max-width:${portrait ? 795 : 590}px;margin-top:${portrait ? 22 : 38}px;color:${ink}}
#${id} .world-viewport{position:absolute;left:${portrait ? 65 : 775}px;top:${portrait ? 565 : 165}px;width:${portrait ? 875 : 1050}px;height:${portrait ? 850 : 675}px;overflow:hidden;border-radius:38px;border:3px solid ${ink};background:${cream}}
#${id} .world{position:absolute;inset:0;transform-origin:50% 50%;overflow:visible}
#${id} .world-room,#${id} .world-split{background:${cream}}
#${id} .room-setting{position:absolute;inset:0}.room-art{width:100%;height:100%;display:block}
#${id} .room-character{position:absolute;left:7%;top:28%;width:42%;height:66%}.character-portrait{display:block;width:100%;height:100%}
#${id} .room-conversation{position:absolute;left:48%;top:24%;width:48%;height:63%}
#${id} .story-phone{position:absolute;left:19%;top:4%;width:62%;height:92%;border:8px solid ${ink};border-radius:44px;background:${cream};overflow:hidden;display:flex;flex-direction:column}
#${id} .phone-top{flex:none;padding:27px 23px 21px;border-bottom:3px solid ${ink};font-size:${portrait ? 28 : 29}px;line-height:1.1;font-weight:700;text-align:center;display:flex;flex-direction:column;gap:17px;align-items:center}
#${id} .phone-camera{display:block;width:92px;height:13px;border-radius:10px;background:${ink}}
#${id} .phone-content{position:relative;flex:1;min-height:0;padding:28px 24px}
#${id} .message-state{position:absolute;left:25px;right:25px;top:28px;transform-origin:left bottom}
#${id} .sender-mira,#${id} .sender-draft{transform-origin:right bottom}
#${id} .sender-name{font-size:${portrait ? 23 : 23}px;line-height:1.2;font-weight:700;margin-bottom:13px}
#${id} .message-bubble{background:${gold};border:3px solid ${ink};border-radius:23px 23px 23px 3px;padding:24px 21px;font-size:${portrait ? 43 : 44}px;line-height:1.16;font-weight:700;overflow-wrap:break-word}
#${id} .sender-mira .message-bubble{background:${teal};color:${cream};border-radius:23px 23px 3px 23px}
#${id} .sender-draft .message-bubble{background:${cream};border-style:dashed;border-radius:23px 23px 3px 23px}
#${id} .receipt{font-size:${portrait ? 20 : 20}px;line-height:1.3;font-weight:700;margin-top:13px}
#${id} .phone-controls{margin:0 20px;flex:none;border-top:3px solid ${ink};padding:15px 0;display:flex;justify-content:space-between;align-items:center;font-size:${portrait ? 22 : 23}px;font-weight:700}
#${id} .send-control{display:flex;width:58px;height:58px;align-items:center;justify-content:center;background:${teal};color:${cream};border-radius:50%;font-size:48px;line-height:1}
#${id} .phone-bottom{width:112px;height:8px;background:${ink};border-radius:9px;flex:none;margin:3px auto 14px}
#${id} .compact-phone{left:0;top:0;width:100%;height:100%;border-width:6px;border-radius:30px}
#${id} .compact-phone .phone-top{font-size:${portrait ? 25 : 27}px;padding:15px 13px;gap:10px}
#${id} .compact-phone .phone-camera{width:65px;height:9px}
#${id} .compact-phone .message-state{left:17px;right:17px;top:18px}
#${id} .compact-phone .message-bubble{font-size:${portrait ? 36 : 38}px;padding:19px 16px;line-height:1.15}
#${id} .compact-phone .sender-name{font-size:21px;margin-bottom:10px}
#${id} .compact-phone .receipt{font-size:18px;margin-top:10px}
#${id} .compact-phone .phone-controls{font-size:20px;padding:10px 0;margin:0 14px}
#${id} .compact-phone .send-control{width:42px;height:42px;font-size:35px}
#${id} .typing-indicator{position:absolute;left:26px;bottom:34px;width:122px;height:64px;border:3px solid ${ink};border-radius:35px;display:flex;justify-content:center;align-items:center;gap:9px;background:${gold}}
#${id} .typing-indicator span{display:block;width:15px;height:15px;border-radius:50%;background:${ink}}
#${id} .phone-portrait{position:absolute;left:-7%;bottom:-3%;width:34%;height:47%}
#${id} .phone-scene-lines{position:absolute;left:6%;right:6%;top:15%;bottom:14%;border-top:3px solid ${teal};border-bottom:3px solid ${red}}
#${id} .cupboard{position:absolute;left:8%;top:5%;width:80%;height:81%;border:7px solid ${ink};background:${teal};border-radius:8px}
#${id} .cupboard-cornice{position:absolute;left:-4%;right:-4%;top:-4%;height:7%;background:${gold};border:5px solid ${ink};border-radius:7px}
#${id} .cupboard-back{position:absolute;inset:0;overflow:hidden}
#${id} .shelf-lines{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:space-evenly;padding-top:12%}
#${id} .shelf-lines i{display:block;height:11px;background:${gold};border-top:3px solid ${ink};border-bottom:3px solid ${ink}}
#${id} .supply{position:absolute;width:43%;height:25%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;color:${cream}}
#${id} .supply:nth-of-type(even){left:5%}#${id} .supply:nth-of-type(odd){left:51%}
${Array.from({ length: 6 }, (_, index) => `#${id} .supply-${index}{left:${index % 2 ? 51 : 5}%;top:${5 + Math.floor(index / 2) * 29}%}`).join('')}
#${id} .supply svg{display:block;width:61%;height:62%;flex:none}
#${id} .single-shelf-groups .supply{left:5%;width:90%;height:28%}#${id} .single-shelf-groups .supply svg{width:86%;height:62%}
${Array.from({ length: 3 }, (_, index) => `#${id} .single-shelf-groups .supply-${index}{top:${3 + index * 29}%}`).join('')}
#${id} .supply-label{font-size:${portrait ? 29 : 30}px;line-height:1.1;font-weight:700;text-align:center;background:${cream};color:${ink};padding:4px 9px;max-width:100%}
#${id} .supply-count{font-size:${portrait ? 26 : 27}px;line-height:1.3;font-weight:700}
#${id} .cupboard-door{position:absolute;left:0;top:0;bottom:0;width:100%;background:${red};border:3px solid ${ink};transform-origin:left center}
#${id} .door-panel{position:absolute;inset:8%;border:4px solid ${gold}}
#${id} .cupboard-door>i{position:absolute;right:9%;top:47%;width:20px;height:52px;border-radius:8px;background:${gold};border:3px solid ${ink}}
#${id} .inventory-note{position:absolute;left:3%;bottom:3%;width:58%;padding:20px;background:${cream};border:3px solid ${ink};display:flex;flex-direction:column;gap:12px;transform-origin:left bottom}
#${id} .inventory-note span{font-size:23px;font-weight:700}#${id} .inventory-note strong{font:900 ${portrait ? 43 : 42}px/1.08 Fraunces,serif}
#${id} .inventory-underline{width:100%;height:17px;display:block}#${id} .inventory-underline path{fill:none;stroke:${red};stroke-width:7;stroke-linecap:round}
#${id} .cart-slip{position:absolute;right:2%;bottom:3%;width:34%;padding:20px;border:3px solid ${ink};background:${gold};display:flex;flex-direction:column;gap:14px}
#${id} .cart-slip span{font-size:23px;font-weight:700}#${id} .cart-slip strong{font-size:32px;line-height:1.1}
#${id} .table-surface{position:absolute;inset:0;background:${gold};border-top:22px solid ${red}}
#${id} .paper-sheet{position:absolute;left:8%;top:8%;width:79%;height:81%;background:${cream};border:3px solid ${ink};padding:8% 7% 4%;border-radius:4px}
#${id} .paper-holes{position:absolute;left:3%;top:10%;bottom:9%;display:flex;flex-direction:column;justify-content:space-between}
#${id} .paper-holes i{display:block;width:16px;height:16px;border:3px solid ${ink};border-radius:50%;background:${gold}}
#${id} .paper-title{font-size:${portrait ? 29 : 30}px;line-height:1.1;font-weight:700;margin-bottom:36px;color:${teal}}
#${id} .paper-line{font-size:${portrait ? 45 : 45}px;line-height:1.17;font-weight:700;position:relative;margin-bottom:28px;overflow-wrap:break-word}
#${id} .strike-svg{position:absolute;left:0;top:12%;width:100%;height:100%;pointer-events:none;overflow:visible}
#${id} .strike-svg path{fill:none;stroke:${red};stroke-width:9px;stroke-linecap:round}
#${id} .paper-rule{height:3px;background:${teal};margin-top:10px}
#${id} .hand-note{font:900 ${portrait ? 43 : 45}px/1.09 Fraunces,serif;color:${teal};margin-top:30px}
#${id} .pencil{position:absolute;right:7%;top:17%;width:22px;height:62%;background:${red};border:3px solid ${ink};border-radius:4px}
#${id} .tea-cup{position:absolute;right:-7%;bottom:-6%;width:28%;height:29%;background:${cream};border:7px solid ${ink};border-radius:50%;padding:20px}
#${id} .tea-cup i{display:block;width:100%;height:100%;background:${teal};border-radius:50%;border:4px solid ${ink}}
#${id} .calendar-page{position:absolute;left:4%;top:8%;width:55%;height:82%;padding:5% 5% 4%;border:5px solid ${ink};background:${cream};border-top:28px solid ${red}}
#${id} .calendar-rings{position:absolute;left:18%;right:18%;top:-50px;display:flex;justify-content:space-between}
#${id} .calendar-rings i{display:block;width:24px;height:60px;border:5px solid ${ink};border-radius:18px;background:${gold}}
#${id} .calendar-kicker{font-size:24px;font-weight:700;color:${teal}}
#${id} .calendar-day{font:900 75px/1.05 Fraunces,serif;margin-top:20px}
#${id} .calendar-line{height:4px;background:${ink};margin:22px 0}
#${id} .calendar-plan{font-size:44px;line-height:1.13;font-weight:700;max-width:100%;overflow-wrap:break-word;position:relative;z-index:2}
#${id} .calendar-circle{position:absolute;left:4%;top:34%;width:88%;height:31%;overflow:visible}
#${id} .calendar-circle path{fill:none;stroke:${red};stroke-width:9;stroke-linecap:round}
#${id} .calendar-note{font-size:31px;line-height:1.2;margin-top:28px;color:${teal};font-weight:700;max-width:100%;overflow-wrap:break-word}
#${id} .calendar-date{position:absolute;left:10%;bottom:6%;font-size:24px;font-weight:700}
#${id} .lunch-plate{position:absolute;right:-5%;bottom:-13%;width:39%;height:44%;border-radius:50%;border:7px solid ${ink};background:${gold};display:flex;align-items:center;justify-content:center;gap:4%}
#${id} .lunch-plate i{display:block;width:30%;height:40%;background:${cream};border:5px solid ${ink};border-radius:8px}
#${id} .lunch-cup{position:absolute;right:4%;top:8%;width:14%;height:18%;border:6px solid ${ink};border-radius:50%;background:${teal}}
#${id} .calendar-reply{position:absolute;right:3%;top:${calendarFit.topPercent}%;width:40%;height:${calendarFit.heightPercent}%}
#${id} .calendar-reply .compact-phone .message-bubble{font-size:${calendarFit.fontPx}px}
#${id} .split-room{position:absolute;top:0;width:50%;height:100%;border-right:4px solid ${ink}}
#${id} .mira-room{left:0;background:${gold}}#${id} .asha-room{left:50%;background:${cream};border-right:0}
#${id} .split-window{position:absolute;left:14%;top:7%;width:69%;height:36%;background:${teal};border:5px solid ${ink};border-radius:50% 50% 0 0}
#${id} .asha-room .split-window{background:${red}}
#${id} .split-person{position:absolute;left:7%;top:20%;width:87%;height:72%}
#${id} .split-room>span{position:absolute;left:12%;bottom:5%;font:900 46px/1 Fraunces,serif}
#${id} .split-conversation{position:absolute;left:27%;top:29%;width:48%;height:58%}
`;
}

function eventScript(id, cue, events, duration) {
  const visual = cue.visual;
  const messages = events.filter(event => event.kind === 'message');
  const hasPhone = ['phone', 'room', 'calendar', 'split'].includes(visual.type);
  let code = `var tl=gsap.timeline({paused:true});\n`;
  const worldSelector = `#${id}-world`;
  // Whole-world camera; fixed geometry, one transform writer, no per-frame measurement.
  const camEvent = events.find(event => event.at > .25)?.at ?? Math.min(1.2, duration / 3);
  const scale = visual.camera === 'close' ? 1.065 : visual.camera === 'over-shoulder' ? 1.04 : 1.025;
  const x = visual.camera === 'over-shoulder' ? -10 : 0;
  code += `var world=document.getElementById('${id}-world');var camera={scale:1,x:0,y:0};function applyCamera(){world.style.transform='translate('+camera.x+'px,'+camera.y+'px) scale('+camera.scale+')';}\napplyCamera();tl.to(camera,{scale:${scale},x:${x},y:0,duration:${n(Math.min(1.45, Math.max(.35, duration - camEvent - .2)))},ease:'power2.inOut',onUpdate:applyCamera},${n(camEvent)});\n`;
  if (messages.length && hasPhone) {
    messages.forEach((event, index) => {
      const selector = `#${id}-message-${event.index}`;
      const next = messages[index + 1]?.at;
      code += `tl.set('${selector}',{opacity:0},0);\n`;
      if (event.at === 0) code += `tl.set('${selector}',{opacity:1,scale:1,y:0},0);\n`;
      else code += `tl.fromTo('${selector}',{scale:.75,opacity:0,y:12},{scale:1,opacity:1,y:0,duration:.22,ease:'power2.out',immediateRender:false},${n(event.at)});\n`;
      const calling = /call/i.test(visual.action_phrase ?? '') || /^Call /i.test(visual.screen_title ?? '');
      const status = calling ? 'CALL' : event.sender === 'draft' ? 'UNSENT' : event.sender === 'Mira' ? 'SENT' : 'CONVERSATION';
      code += `tl.set('#${id}-control-label',{textContent:'${status}'},${n(event.at)});\n`;
      if (next !== undefined) code += `tl.set('${selector}',{opacity:0},${n(next)});\n`;
    });
  }
  if (hasPhone) code += `tl.set('#${id}-typing',{opacity:0},0);\n`;
  const cupboard = visual.type === 'cupboard';
  if (cupboard) code += `tl.set('#${id}-door',{scaleX:${visual.action === 'reveal' ? 1 : 0}},0);var inventoryStroke=document.getElementById('${id}-inventory-stroke');var inventoryLength=inventoryStroke.getTotalLength();inventoryStroke.style.strokeDasharray=inventoryLength;tl.set(inventoryStroke,{strokeDashoffset:inventoryLength},0);\n`;
  if (visual.type === 'paper') {
    const count = visual.messages?.length || visual.items?.length || 1;
    for (let index = 0; index < Math.min(3, count); index++) code += `var strike${index}=document.getElementById('${id}-strike-${index}');var length${index}=strike${index}.getTotalLength();strike${index}.style.strokeDasharray=length${index};tl.set(strike${index},{strokeDashoffset:length${index}},0);\n`;
    // Physical note lines follow the same measured message anchors as a phone, not a second estimate.
    messages.forEach(event => { if (event.index < 3) code += `tl.fromTo('#${id}-paper-line-${event.index}',{opacity:0,y:18},{opacity:1,y:0,duration:.32,ease:'power3.out'},${n(event.at)});\n`; });
  }
  if (visual.type === 'calendar') code += `var circle=document.getElementById('${id}-circle');var circleLength=circle.getTotalLength();circle.style.strokeDasharray=circleLength;tl.set(circle,{strokeDashoffset:circleLength},0);\n`;
  for (const event of events.filter(item => item.kind === 'action')) {
    const at = n(event.at);
    code += `tl.addLabel('action-${event.action}',${at});\n`;
    if (event.action === 'delete') {
      if (visual.type === 'paper') {
        code += `tl.to('#${id}-strike-0',{strokeDashoffset:0,duration:.42,ease:'power2.out'},${at});\ntl.fromTo('#${id}-pencil',{x:0,y:0},{x:-48,y:32,duration:.42,ease:'power2.out'},${at});\n`;
      } else if (hasPhone && messages.length) {
        const draft = [...messages].reverse().find(item => item.sender === 'draft' && item.at <= event.at) ?? [...messages].reverse().find(item => item.at <= event.at);
        if (draft) code += `tl.to('#${id}-message-${draft.index}',{x:62,y:-18,opacity:0,scale:.92,duration:.36,ease:'power2.in'},${at});\n`;
        else if (visual.prior_draft) code += `tl.to('#${id}-prior-draft',{x:62,y:-18,opacity:0,scale:.92,duration:.36,ease:'power2.in'},${at});\n`;
        code += `tl.set('#${id}-control-label',{textContent:'DRAFT DELETED'},${n(event.at + .38)});\n`;
      }
    } else if (event.action === 'send' && hasPhone) {
      const calling = /call/i.test(event.phrase);
      code += `tl.to('#${id}-send',{scale:.82,duration:.10,ease:'power2.in'},${at});tl.to('#${id}-send',{scale:1,duration:.22,ease:'power3.out'},${n(event.at + .10)});tl.set('#${id}-control-label',{textContent:'${calling ? 'CALL CONNECTING' : 'SENT'}'},${n(event.at + .1)});\n`;
    } else if (event.action === 'reveal' && cupboard) {
      code += `tl.fromTo('#${id}-door',{scaleX:1},{scaleX:0,duration:.62,ease:'power3.inOut',immediateRender:false},${at});tl.fromTo('#${id}-inventory',{scale:.87,opacity:0},{scale:1,opacity:1,duration:.4,ease:'power3.out'},${n(event.at + .35)});tl.to(inventoryStroke,{strokeDashoffset:0,duration:.5,ease:'power2.out'},${n(event.at + .65)});\n`;
    } else if (event.action === 'sort' && cupboard) {
      (visual.items ?? []).forEach((_, index) => { code += `tl.fromTo('#${id}-supply-${index}',{x:${index % 2 ? 35 : -35},y:0},{x:0,y:0,duration:.45,ease:'power3.out'},${n(event.at + index * .055)});\n`; });
      code += `tl.fromTo('#${id}-inventory',{scale:.87,opacity:0},{scale:1,opacity:1,duration:.4,ease:'power3.out'},${at});tl.to(inventoryStroke,{strokeDashoffset:0,duration:.5,ease:'power2.out'},${n(event.at + .3)});\n`;
    } else if (event.action === 'close' && cupboard) {
      if (/cupboard/.test(event.phrase)) code += `tl.to('#${id}-door',{scaleX:1,duration:.62,ease:'power3.inOut'},${at});\n`;
      else code += `tl.to('#${id}-cart',{y:75,scale:.92,opacity:0,duration:.45,ease:'power2.in'},${at});\n`;
    } else if (event.action === 'close' && hasPhone) {
      code += `tl.to('#${id}-phone',{y:30,scale:.96,duration:.45,ease:'power2.inOut'},${at});tl.set('#${id}-control-label',{textContent:'PUT AWAY'},${at});\n`;
    } else if (event.action === 'wait' && hasPhone) {
      // Waiting is Mira's pause, not evidence that Asha is typing. Keep the
      // registry indicator hidden unless the locked narration actually says so.
      if (/typing/i.test(cue.text ?? '') && !/no .*typing|not .*typing/i.test(cue.text ?? '')) {
        const waitEnd = Math.min(duration - .2, Math.max(event.at + 1, messages.find(item => item.at > event.at)?.at ?? event.at + 2.4));
        code += `tl.fromTo('#${id}-typing',{scale:.6,opacity:0},{scale:1,opacity:1,duration:.1,ease:'power2.out'},${at});tl.set('#${id}-typing',{opacity:0},${n(waitEnd)});\n`;
      } else code += `tl.fromTo('#${id}-send',{backgroundColor:'${teal}'},{backgroundColor:'${ink}',duration:.35,ease:'power1.out',immediateRender:false},${at});\n`;
    } else if (visual.type === 'calendar') {
      code += `tl.to('#${id}-circle',{strokeDashoffset:0,duration:.65,ease:'power2.out'},${at});\n`;
    } else if (visual.type === 'paper') {
      code += `tl.fromTo('#${id}-hand-note',{scale:.94,opacity:0},{scale:1,opacity:1,duration:.4,ease:'power3.out'},${at});\n`;
    } else if (hasPhone) {
      code += `tl.to('#${id}-phone',{scale:1.025,duration:.22,ease:'power2.out',yoyo:true,repeat:1},${at});\n`;
    }
  }
  // No scene exit fade: the runtime hard cut owns lifecycle; last state holds.
  code += `window.__timelines['${id}']=tl;`;
  return code;
}

export function buildScene(cue, episode, index, words) {
  const portrait = episode.format === 'shorts';
  const duration = Number(cue.end) - Number(cue.start);
  if (!(duration > .5)) throw new Error(`${cue.id}: scene must have a positive measured slot`);
  const id = `story-${String(index + 1).padStart(2, '0')}-${slug(cue.id)}`;
  cue = { ...cue, visual: { ...cue.visual } };
  let events = sceneEvents(cue, words);
  const deleteEvent = events.find(event => event.kind === 'action' && event.action === 'delete');
  if (deleteEvent && deleteEvent.at < (events.find(event => event.kind === 'message')?.at ?? Infinity) && ['room', 'phone', 'split'].includes(cue.visual.type)) {
    const previous = episode.segments.slice(0, index).flatMap(segment => segment.visual?.messages ?? []).filter(message => message.sender === 'draft').at(-1);
    cue.visual.prior_draft = previous?.text ?? 'The unsent recommendation';
  }
  if (events.some(event => event.at >= duration - .04)) throw new Error(`${cue.id}: action or message lands beyond its visible slot`);
  const visual = cue.visual;
  const headline = visual.headline || cue.title;
  if (!String(headline || '').trim()) throw new Error(`${cue.id}: story heading required`);
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(cue.title)}</title></head><body><template><style>${sceneCss(id, portrait, visual)}</style>
<div id="${id}" data-composition-id="${id}" data-width="${portrait ? 1080 : 1920}" data-height="${portrait ? 1920 : 1080}" data-duration="${n(duration)}" data-story-world="${visual.type}">
<div class="fiction-label">ORIGINAL FICTIONAL STORY</div><div class="episode-mark">BIZNEX / UNSENT</div><div class="story-heading"><h1>${esc(headline)}</h1></div>
<div class="world-viewport" id="${id}-viewport"><div class="world world-${visual.type}" id="${id}-world" data-layout-allow-overflow>${worldMarkup(id, visual, events)}</div></div></div>
<script>(function(){${eventScript(id, cue, events, duration)}})();</script></template></body></html>`;
  return { id, cueId: cue.id, type: visual.type, duration, start: Number(cue.start), events, html };
}

function captionsHtml(audio, portrait) {
  const groups = captionGroups(audio.voices.flatMap(voice => voice.words ?? []), 4, portrait ? 26 : 38);
  if (!groups.length) throw new Error('Measured ASR words required for story captions');
  const duration = Number(audio.total_duration_s);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body><template><style>${fonts('../')}
#captions{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;font-family:Montserrat,sans-serif}
#story-caption-box{position:absolute;left:${portrait ? 80 : 175}px;right:${portrait ? 160 : 175}px;bottom:${portrait ? 290 : 79}px;min-height:${portrait ? 130 : 100}px;display:flex;align-items:center;justify-content:center}
#story-caption-line{max-width:100%;padding:${portrait ? '18px 23px' : '14px 26px'};font:900 ${portrait ? 54 : 47}px/1.2 Montserrat,sans-serif;letter-spacing:-.018em;text-align:center;background:${ink};color:${cream};border:3px solid ${cream};border-radius:13px}
#story-caption-line span{display:inline;color:${cream};padding:2px 3px;border-radius:3px}#story-caption-line span.active{background:${gold};color:${ink}}
</style><div id="captions" data-composition-id="captions" data-width="${portrait ? 1080 : 1920}" data-height="${portrait ? 1920 : 1080}" data-duration="${n(duration)}"><div id="story-caption-box"><div id="story-caption-line">${esc(groups[0].words.map(word => word.text).join(' '))}</div></div></div>
<script>(function(){var groups=${js(groups)};var driver={t:0};var previous=-2;var lastWord=-2;var line=document.getElementById('story-caption-line');var spans=[];function updateCaption(){var time=driver.t;var lo=0,hi=groups.length-1,found=-1;while(lo<=hi){var mid=(lo+hi)>>1;if(groups[mid].start<=time){found=mid;lo=mid+1;}else hi=mid-1;}if(found>=0&&time>groups[found].end)found=-1;if(found!==previous){line.textContent='';spans=[];if(found>=0)groups[found].words.forEach(function(word,index){if(index)line.appendChild(document.createTextNode(' '));var span=document.createElement('span');span.textContent=word.text;line.appendChild(span);spans.push(span);});line.style.opacity=found<0?'0':'1';previous=found;lastWord=-2;}if(found>=0){var active=-1;groups[found].words.forEach(function(word,index){if(time>=word.start&&time<=word.end)active=index;});if(active!==lastWord){spans.forEach(function(span,index){span.className=index===active?'active':'';});lastWord=active;}}}var tl=gsap.timeline({paused:true});tl.fromTo(driver,{t:0},{t:${n(duration)},duration:${n(duration)},ease:'none',onUpdate:updateCaption},0);window.__timelines['captions']=tl;})();</script></template></body></html>`;
}

function rootHtml(episode, audio, scenes) {
  const portrait = episode.format === 'shorts';
  const width = portrait ? 1080 : 1920, height = portrait ? 1920 : 1080;
  if (audio.voices.length !== 1) throw new Error(`${episode.id}: expected one continuous approved narration`);
  const voice = audio.voices[0];
  const duration = Number(audio.total_duration_s);
  const hosts = scenes.map((scene, index) => `<div id="el-${scene.id}" class="clip" data-composition-id="${scene.id}" data-composition-src="compositions/frames/${slug(scene.cueId)}.html" data-start="${n(scene.start)}" data-duration="${n(scene.duration)}" data-track-index="${index % 2 + 1}" data-width="${width}" data-height="${height}"></div>`).join('\n');
  const bgm = audio.bgm ? `<audio id="bgm" src="${esc(audio.bgm.path)}" data-start="0" data-duration="${n(Math.min(duration, Number(audio.bgm.duration_s)))}" data-track-index="11" data-volume="${audio.bgm.volume ?? .08}"></audio>` : '';
  const effects = (audio.story_sfx ?? []).map((effect, index) => `<audio id="story-sfx-${index}" src="${esc(effect.file)}" data-start="${n(effect.offset_s)}" data-duration="${n(effect.duration_s)}" data-track-index="13" data-volume="${effect.volume ?? .08}"></audio>`).join('\n');
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(episode.title)}</title><script src="assets/vendor/gsap.min.js"></script><style>${fonts()}*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:${cream}}#root{position:relative;width:100%;height:100%;overflow:hidden;background:${cream}}#root>.clip[data-composition-src]{position:absolute;inset:0;width:100%;height:100%}#story-progress{position:absolute;left:${portrait ? 80 : 88}px;right:${portrait ? 160 : 88}px;bottom:${portrait ? 253 : 42}px;height:4px;background:${gold};z-index:32}#story-progress-fill{width:100%;height:100%;background:${teal};transform-origin:left center}</style></head><body><div id="root" data-composition-id="main" data-width="${width}" data-height="${height}" data-duration="${n(duration)}">
${hosts}<div id="el-captions" class="clip" style="z-index:30;pointer-events:none" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="${n(duration)}" data-track-index="5" data-track-kind="captions" data-width="${width}" data-height="${height}"></div><div id="story-progress" data-layout-ignore><div id="story-progress-fill"></div></div>
<audio id="voiceover" src="${esc(voice.path)}" data-start="0" data-duration="${n(voice.duration_s)}" data-track-index="10" data-volume="1"></audio>${bgm}${effects}</div><script>(function(){var tl=gsap.timeline({paused:true});tl.fromTo('#story-progress-fill',{scaleX:0},{scaleX:1,duration:${n(duration)},ease:'none'},0);window.__timelines['main']=tl;})();</script></body></html>`;
}

function phoneThumbnailHtml(episode) {
  const portrait = episode.format === 'shorts';
  const messages = episode.segments.flatMap(segment => segment.visual?.messages ?? []);
  const turn = episode.segments.find(segment => segment.id === episode.story?.turn_segment || segment.narrative_role === 'turn');
  const incoming = turn?.visual?.messages?.find(message => message.sender === 'Asha') ?? messages.find(message => message.sender === 'Asha');
  const draft = messages.find(message => message.sender === 'draft');
  const choice = episode.segments.find(segment => segment.narrative_role === 'choice' && segment.visual?.messages?.some(message => message.sender === 'Mira'));
  const reply = choice?.visual.messages.find(message => message.sender === 'Mira') ?? messages.find(message => message.sender === 'Mira');
  const incomingText = incoming?.text ?? 'A message from Asha';
  const draftText = draft?.text ?? 'An unsent recommendation';
  const replyText = reply?.text ?? 'Room for a different answer.';
  const id = 'thumbnail-story';
  const body = portrait ? `<div class="thumb-person">${characterSvg('Mira', 'concerned', 'thumb-mira')}</div><div class="thumb-phone"><div class="thumb-phone-top"><i></i><strong>Asha</strong></div><div class="thumb-chat"><div class="thumb-incoming"><span>ASHA / EARLIER</span><strong>${esc(incomingText)}</strong></div><div class="thumb-draft"><span>MIRA / UNSENT DRAFT</span><strong>${esc(draftText)}</strong><small>NOT SENT</small></div></div><div class="thumb-phone-control"><span>UNSENT</span><i>↑</i></div></div>` : `<div class="thumb-person">${characterSvg('Mira', 'concerned', 'thumb-mira')}</div><div class="thumb-edit"><div class="thumb-incoming"><span>THE MESSAGE ABOVE IT</span><strong>${esc(incomingText)}</strong></div><div class="thumb-deleted"><span>THE DRAFT SHE REMOVED</span><strong>${esc(draftText)}</strong><svg viewBox="0 0 580 110" preserveAspectRatio="none" aria-hidden="true"><path d="M8 93L567 16 M13 21L566 92"/></svg></div><div class="thumb-reply"><span>THE MESSAGE SHE SENT</span><strong>${esc(replyText)}</strong></div></div>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(episode.thumbnail_headline)}</title><style>${fonts()}
*{box-sizing:border-box}html,body{margin:0;width:${portrait ? 1080 : 1280}px;height:${portrait ? 1920 : 720}px;overflow:hidden;background:${cream};color:${ink};font-family:Montserrat,sans-serif}
#${id}{position:absolute;inset:0;overflow:hidden;background:${cream}}
.fiction-label{position:absolute;left:${portrait ? 80 : 55}px;top:${portrait ? 208 : 34}px;padding-bottom:12px;border-bottom:4px solid ${red};font-size:${portrait ? 27 : 20}px;line-height:1.2;font-weight:700;letter-spacing:.03em}
.story-heading{position:absolute;left:${portrait ? 80 : 56}px;top:${portrait ? 306 : 143}px;width:${portrait ? 830 : 510}px}
h1{margin:0;font:900 ${portrait ? 124 : 98}px/1.01 Fraunces,serif;letter-spacing:-.045em;overflow-wrap:break-word}
.thumb-person{position:absolute;left:${portrait ? -30 : 88}px;top:${portrait ? 888 : 391}px;width:${portrait ? 510 : 310}px;height:${portrait ? 760 : 455}px;z-index:3}.character-portrait{display:block;width:100%;height:100%}
.thumb-phone{position:absolute;left:356px;top:659px;width:607px;height:1002px;border:9px solid ${ink};border-radius:49px;background:${cream};overflow:hidden;display:flex;flex-direction:column;z-index:2}
.thumb-phone-top{display:flex;flex-direction:column;align-items:center;gap:17px;padding:24px 20px 22px;border-bottom:4px solid ${ink};font-size:34px}.thumb-phone-top i{display:block;width:100px;height:13px;border-radius:10px;background:${ink}}
.thumb-chat{flex:1;min-height:0;padding:30px 30px;display:flex;flex-direction:column;gap:36px}
.thumb-incoming,.thumb-draft,.thumb-deleted,.thumb-reply{position:relative;display:flex;flex-direction:column;gap:${portrait ? 18 : 12}px}
.thumb-incoming span,.thumb-draft span,.thumb-deleted span,.thumb-reply span{font-size:${portrait ? 25 : 20}px;font-weight:700;line-height:1.2}
.thumb-incoming strong,.thumb-draft strong,.thumb-deleted strong,.thumb-reply strong{display:block;font-size:${portrait ? 49 : 39}px;line-height:1.14;padding:${portrait ? '23px 22px' : '19px 22px'};border:3px solid ${ink};border-radius:23px 23px 23px 3px;overflow-wrap:break-word;background:${gold}}
.thumb-draft strong{background:${cream};border-style:dashed;border-radius:23px 23px 3px 23px}.thumb-draft small{font-size:23px;font-weight:700}
.thumb-phone-control{display:flex;justify-content:space-between;align-items:center;padding:17px 24px;margin:0 22px;border-top:3px solid ${ink};font-size:27px;font-weight:700}.thumb-phone-control i{font-style:normal;display:flex;width:65px;height:65px;align-items:center;justify-content:center;border-radius:50%;background:${teal};color:${cream};font-size:51px}
.thumb-edit{position:absolute;left:623px;right:55px;top:83px;bottom:52px;display:flex;flex-direction:column;gap:25px}
.thumb-edit .thumb-incoming strong{font-size:38px;padding:16px 22px}.thumb-edit .thumb-deleted strong{background:${cream};border-style:dashed}.thumb-edit .thumb-deleted svg{position:absolute;left:10px;right:10px;bottom:7px;width:96%;height:72%;pointer-events:none}.thumb-edit .thumb-deleted path{fill:none;stroke:${red};stroke-width:8;stroke-linecap:round}
.thumb-reply strong{background:${teal};color:${cream};border-radius:23px 23px 3px 23px;font-size:40px}
.thumb-brand{position:absolute;left:${portrait ? 80 : 56}px;bottom:${portrait ? 196 : 32}px;font-size:${portrait ? 26 : 19}px;font-weight:700;line-height:1.25;background:${cream};padding:9px 0;z-index:5}
</style></head><body><div id="${id}" data-thumbnail-treatment="${portrait ? 'human-stakes-thread' : 'deleted-draft-and-human-reply'}"><div class="fiction-label">ORIGINAL FICTIONAL STORY</div><div class="story-heading"><h1>${esc(episode.thumbnail_headline)}</h1></div>${body}<div class="thumb-brand">BIZNEX / THE UNSENT STORIES</div></div></body></html>`;
}

export function thumbnailHtml(episode) {
  const portrait = episode.format === 'shorts';
  const template = episode.segments.find(segment => segment.visual?.type === episode.thumbnail_visual?.type)?.visual ?? episode.segments[0].visual;
  const visual = { ...template, ...episode.thumbnail_visual };
  if (!WORLD_TYPES.includes(visual.type)) throw new Error(`${episode.id}: unsupported thumbnail world`);
  const headline = episode.thumbnail_headline;
  if (!String(headline || '').trim()) throw new Error(`${episode.id}: thumbnail promise is required`);
  if (visual.type === 'phone') return phoneThumbnailHtml(episode);
  const id = 'thumbnail-story';
  const width = portrait ? 1080 : 1280, height = portrait ? 1920 : 720;
  const fullCss = sceneCss(id, portrait);
  // Same authored objects as the story, captured in a static proof pose; not a new claim.
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(headline)}</title><style>${fonts()}${fullCss.replaceAll('../../assets/', 'assets/')}
html,body{margin:0;width:${width}px;height:${height}px;overflow:hidden;background:${cream}}
#${id}{width:${width}px;height:${height}px}
#${id} .fiction-label{top:${portrait ? 210 : 34}px;left:${portrait ? 80 : 55}px;font-size:${portrait ? 27 : 20}px}
#${id} .episode-mark{display:none}#${id} .story-heading{top:${portrait ? 320 : 136}px;left:${portrait ? 80 : 56}px;width:${portrait ? 820 : 540}px}
#${id} h1{font-size:${portrait ? 119 : 95}px;line-height:1.02;letter-spacing:-.045em}
#${id} .world-viewport{left:${portrait ? 65 : 642}px;top:${portrait ? 770 : 99}px;width:${portrait ? 875 : 580}px;height:${portrait ? 795 : 536}px;border-width:4px}
#${id} .message-bubble{font-size:${portrait ? 43 : 32}px}#${id} .phone-top{font-size:${portrait ? 28 : 22}px}#${id} .sender-name{font-size:${portrait ? 23 : 19}px}#${id} .receipt{font-size:${portrait ? 20 : 16}px}#${id} .phone-controls{font-size:${portrait ? 22 : 17}px}
#${id} .compact-phone .message-bubble{font-size:${portrait ? 36 : 28}px}#${id} .compact-phone .phone-top{font-size:${portrait ? 25 : 20}px}
#${id} .message-state{opacity:0}#${id} .message-state:last-of-type{opacity:1}#${id} .message-state:first-child{opacity:1}#${id} .message-state:not(:first-child){display:none}
#${id} .typing-indicator,#${id} .cupboard-door{display:none}#${id} .final-mark{position:absolute;bottom:${portrait ? 230 : 40}px;left:${portrait ? 80 : 56}px;font:700 ${portrait ? 27 : 21}px/1.2 Montserrat,sans-serif;max-width:${portrait ? 820 : 540}px}
#${id} .calendar-day{font-size:${portrait ? 88 : 57}px}#${id} .calendar-plan{font-size:${portrait ? 52 : 36}px}#${id} .calendar-note{font-size:${portrait ? 35 : 25}px}#${id} .supply-label{font-size:${portrait ? 29 : 24}px}#${id} .supply-count{font-size:${portrait ? 26 : 22}px}#${id} .inventory-note strong{font-size:${portrait ? 43 : 29}px}#${id} .paper-line{font-size:${portrait ? 45 : 31}px}#${id} .hand-note{font-size:${portrait ? 43 : 31}px}
</style></head><body><div id="${id}"><div class="fiction-label">ORIGINAL FICTIONAL STORY</div><div class="story-heading"><h1>${esc(headline)}</h1></div><div class="world-viewport"><div class="world world-${visual.type}">${worldMarkup(id, visual)}</div></div><div class="final-mark">BIZNEX / THE UNSENT STORIES</div></div></body></html>`;
}

export function buildEpisode(project, episode) {
  const audio = JSON.parse(fs.readFileSync(path.join(project, 'audio_meta.json'), 'utf8'));
  if (!audio.cues?.length || audio.cues.length !== episode.segments?.length) throw new Error(`${episode.id}: measured cue/segment count mismatch`);
  if (Math.abs(Number(audio.cues[0].start)) > .001) throw new Error(`${episode.id}: first scene must start at zero`);
  const words = audio.voices.flatMap(voice => voice.words ?? []);
  const scenes = audio.cues.map((timing, index) => {
    if (timing.id !== episode.segments[index].id) throw new Error(`${episode.id}: measured cue identity mismatch`);
    const end = Number(audio.cues[index + 1]?.start ?? audio.total_duration_s);
    return buildScene({ ...episode.segments[index], ...timing, end }, episode, index, words);
  });
  // Existing generic setup chimes are not story actions. Replace them in the
  // assembled mix with sparse measured send/delete accents, using real WAV size.
  const clickPath = path.join(project, 'assets', 'sfx', 'click-soft.wav');
  audio.story_sfx = [];
  if (fs.existsSync(clickPath)) {
    const bytes = fs.readFileSync(clickPath);
    let rate = 0, size = 0;
    for (let offset = 12; offset + 8 <= bytes.length;) {
      const chunk = bytes.toString('ascii', offset, offset + 4), length = bytes.readUInt32LE(offset + 4);
      if (chunk === 'fmt ' && length >= 16 && offset + 20 <= bytes.length) rate = bytes.readUInt32LE(offset + 16);
      if (chunk === 'data') { size = Math.min(length, bytes.length - offset - 8); break; }
      offset += 8 + length + (length % 2);
    }
    if (!(rate > 0 && size > 0)) throw new Error(`${episode.id}: invalid local click WAV`);
    const actualDuration = size / rate;
    audio.story_sfx = scenes.flatMap(scene => scene.events.filter(event => event.kind === 'action' && ['delete', 'send'].includes(event.action)).map(event => ({ file: 'assets/sfx/click-soft.wav', offset_s: scene.start + event.at, duration_s: Math.min(actualDuration, Number(audio.total_duration_s) - scene.start - event.at), volume: .08 }))).slice(0, episode.format === 'shorts' ? 3 : 8);
  }
  const frames = path.join(project, 'compositions', 'frames');
  fs.mkdirSync(frames, { recursive: true });
  for (const scene of scenes) {
    fs.writeFileSync(path.join(frames, `${slug(scene.cueId)}.html`), scene.html);
    fs.writeFileSync(path.join(frames, `${slug(scene.cueId)}.motion.json`), JSON.stringify({
      frame_id: scene.id, duration: scene.duration, rules: ['discrete-text-sequence', 'viewport-change', 'spring-pop-entrance', 'svg-path-draw'],
      entry: { direction: 'held-established-state', duration: 0 }, exit: { type: 'hard-cut', duration: 0 },
      assertions: [{ kind: 'appearsBy', selector: `#${scene.id}-viewport`, bySec: .1 }, { kind: 'staysInFrame', selector: `#${scene.id}-viewport` }],
      reveal_times: scene.events.map(event => event.at), events: scene.events.map(event => ({ kind: event.kind, action: event.action, at: event.at, phrase: event.phrase })),
      note: 'Literal measured speech drives message and action states. Original illustrated still characters; active props, not fake jointed performance. Final state holds without black.'
    }, null, 2) + '\n');
  }
  fs.writeFileSync(path.join(project, 'compositions', 'captions.html'), captionsHtml(audio, episode.format === 'shorts'));
  fs.writeFileSync(path.join(project, 'index.html'), rootHtml(episode, audio, scenes));
  fs.writeFileSync(path.join(project, 'THUMBNAIL.html'), thumbnailHtml(episode));
  fs.writeFileSync(path.join(project, 'THUMBNAIL_COPY.md'), `# Thumbnail\n\n${episode.thumbnail_headline}\n\nProof pose: ${episode.thumbnail_visual?.type ?? episode.segments[0].visual.type}. Original fictional story; no outcome, product-performance or earnings claim.\n`);
  const storyboard = path.join(project, 'STORYBOARD.md');
  if (fs.existsSync(storyboard)) fs.writeFileSync(storyboard, fs.readFileSync(storyboard, 'utf8').replace(/^- status: outline$/gm, '- status: animated'));
  const hidden = path.join(project, '.hyperframes');
  fs.mkdirSync(hidden, { recursive: true });
  fs.writeFileSync(path.join(hidden, 'expanded-prompt.md'), `# Illustrated story treatment\n\n${episode.title}\n\nWarm human-scale rooms, a consistent original Mira/Asha pair, physically legible decisions and an ordinary noncommercial ending. The film labels fiction on every frame. ${new Set(scenes.map(scene => scene.type)).size} distinct world structures are used.\n\nThe phone, supplies, paper and calendar are active subjects. Camera reframing follows literal measured speech; no fabricated word timing, earnings proof, product imagery, testimonial or CTA. Registry message/typing geometry is adapted from installed chat-message and typing-indicator primitives.\n`);
  fs.writeFileSync(path.join(hidden, 'animation-map.md'), `# Unsent Stories motion ledger\n\nEvery authored message and action uses the original literal speech anchor. The first established state is meaningful at zero; only the runtime ends each slot. Final visual remains readable and nonblack. Captions use four-word measured groups and preserve real pauses.\n\n| Scene | Start | Duration | World | Measured events |\n| --- | ---: | ---: | --- | --- |\n${scenes.map(scene => `| ${scene.id} | ${n(scene.start)} | ${n(scene.duration)} | ${scene.type} | ${scene.events.map(event => `${n(event.at)}: ${event.kind === 'action' ? event.action : event.sender}`).join('; ')} |`).join('\n')}\n`);
  return { id: episode.id, scenes: scenes.length, duration: Number(audio.total_duration_s), worlds: [...new Set(scenes.map(scene => scene.type))] };
}

function main() {
  const args = process.argv.slice(2);
  const flag = args.indexOf('--creative');
  if (flag < 0 || !args[flag + 1]) throw new Error('--creative <frozen-story-spec.json> is required');
  const creative = JSON.parse(fs.readFileSync(args[flag + 1], 'utf8'));
  const only = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;
  if (!Array.isArray(creative.episodes) || !creative.episodes.length) throw new Error('Creative spec must contain episodes');
  const episodes = creative.episodes.filter(episode => !only || episode.id === only);
  if (!episodes.length) throw new Error(`Requested episode not found: ${only}`);
  for (const item of episodes) {
    const project = path.resolve(item.project);
    const prepared = JSON.parse(fs.readFileSync(path.join(project, 'EPISODE.json'), 'utf8'));
    if (prepared.id !== item.id) throw new Error(`${item.id}: prepared identity mismatch`);
    console.log(JSON.stringify(buildEpisode(project, prepared)));
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))) main();

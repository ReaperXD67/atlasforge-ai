import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { WORLD_TYPES, escapeHtml, phraseTime, sceneEvents, buildScene, worldMarkup, characterSvg, thumbnailHtml, buildEpisode, phoneContentFit } from '../scripts/build_story_compositions.mjs';

const words = [
  { text: 'Mira', start: 10, end: 10.4 },
  { text: 'read', start: 10.5, end: 10.8 },
  { text: 'the', start: 10.9, end: 11.1 },
  { text: 'message.', start: 11.2, end: 11.7 },
  { text: 'No', start: 12.2, end: 12.4 },
  { text: 'thanks.', start: 12.5, end: 12.9 },
  { text: 'She', start: 14, end: 14.3 },
  { text: 'pressed', start: 14.4, end: 14.8 },
  { text: 'call.', start: 14.9, end: 15.3 },
];
const cue = {
  id: 'test-scene', title: 'A friend, not an audience', start: 10, end: 18, text: 'Mira read the message. No thanks. She pressed call.',
  visual: { type: 'phone', expression: 'thinking', headline: 'One ordinary choice', screen_title: 'Asha', messages: [{ sender: 'Asha', text: 'No thanks.', at_phrase: 'No thanks.' }], action: 'send', action_phrase: 'pressed call', note: 'PRODUCTION DIRECTION MUST NOT APPEAR', camera: 'close' },
};
const episode = { id: 'story-fixture', title: 'She chose a conversation', format: 'shorts', thumbnail_headline: "DON'T HIT SEND", thumbnail_visual: { type: 'phone' }, segments: [cue] };

test('literal anchors preserve real acoustic offsets and punctuation', () => {
  assert.ok(Math.abs(phraseTime(cue, words, 'No thanks.') - 2.2) < .000001);
  assert.equal(phraseTime(cue, words, 'pressed call'), 4.4);
  assert.equal(phraseTime(cue, words, 'Mira read the message'), 0);
});

test('anchors do not match partial words, another cue, or invented speech', () => {
  assert.throws(() => phraseTime(cue, words, 'thank'), /not found/);
  assert.throws(() => phraseTime(cue, words, 'she typed'), /not found/);
  assert.throws(() => phraseTime(cue, [{ text: 'outside', start: 9, end: 9.5 }], 'outside'), /not found/);
  assert.throws(() => phraseTime(cue, words, ''), /non-empty/);
});

test('contractions are normalized without discarding the real word timestamp', () => {
  assert.equal(phraseTime({ id: 'one', start: 0, end: 4 }, [{ text: 'I’m', start: 1, end: 1.3 }, { text: 'here.', start: 1.4, end: 1.9 }], "I'm here"), 1);
});

test('literal anchors may begin or end inside a measured ASR bundle', () => {
  const bundled = [{ text: 'Yes,', start: 1.16, end: 1.4 }, { text: 'please. Mira', start: 2.58, end: 2.7 }, { text: 'pressed call.', start: 3, end: 3.8 }];
  const localCue = { id: 'bundle', start: 0, end: 5 };
  assert.equal(phraseTime(localCue, bundled, 'Yes, please.'), 1.16);
  assert.equal(phraseTime(localCue, bundled, 'Mira pressed call.'), 2.58);
  assert.equal(phraseTime(localCue, bundled, 'call'), 3, 'use the measured bundle, not an invented narrower time');
  assert.throws(() => phraseTime(localCue, [{ text: 'border', start: 0, end: 1 }], 'order'), /not found/);
});

test('message and action events resolve separately against measured speech', () => {
  assert.deepEqual(sceneEvents(cue, words).map(event => [event.kind, Number(event.at.toFixed(6))]), [['message', 2.2], ['action', 4.4]]);
});

test('only an initial established message may omit a speech anchor', () => {
  const value = structuredClone(cue);
  value.visual.messages = [{ sender: 'Mira', text: 'Already here.' }];
  assert.equal(sceneEvents(value, words)[0].at, 0);
  value.visual.messages.push({ sender: 'Asha', text: 'A second event.' });
  assert.throws(() => sceneEvents(value, words), /lacks at_phrase/);
});

test('schema errors stop authoring instead of selecting arbitrary fallback motion', () => {
  for (const [key, invalid] of [['type', 'sales-cards'], ['expression', 'testimonial'], ['camera', 'random'], ['action', 'sell']]) {
    const value = structuredClone(cue); value.visual[key] = invalid;
    assert.throws(() => sceneEvents(value, words), /unsupported/);
  }
});

test('sequential Delete words create two independent measured removals', () => {
  const localWords = ['Recommendation', 'Delete.', 'Explanation', 'Delete.'].map((text, index) => ({ text, start: index, end: index + .6 }));
  const value = { id: 'deletions', start: 0, end: 5, visual: { type: 'phone', action: 'delete', action_phrase: 'Delete.', messages: [{ sender: 'draft', text: 'Recommendation', at_phrase: 'Recommendation' }, { sender: 'draft', text: 'Explanation', at_phrase: 'Explanation' }] } };
  assert.deepEqual(sceneEvents(value, localWords).filter(event => event.kind === 'action').map(event => event.at), [1, 3]);
});

test('all six worlds have genuinely different structural subjects', () => {
  const roots = new Set();
  for (const type of WORLD_TYPES) {
    const html = worldMarkup(`fixture-${type}`, { ...cue.visual, type, items: [{ label: 'Bottles', quantity: 3 }, { label: 'Tubes', quantity: 4 }] });
    roots.add(html.match(/class="([^"]+)"/)?.[1]);
    assert.ok(!html.includes('comparison-half'));
    assert.ok(!html.includes('REPAIR LAB'));
  }
  assert.equal(roots.size, 6);
});

test('original character identity remains stable without synthetic limb animation', () => {
  const mira = characterSvg('Mira', 'concerned', 'mira');
  const asha = characterSvg('Asha', 'relieved', 'asha');
  assert.ok(mira.includes('fill="#316b67"'));
  assert.ok(asha.includes('fill="#be4f3c"'));
  assert.ok(mira.includes('single') === false);
  assert.ok(!mira.includes('class="arm"'));
  assert.ok(!mira.includes('<script'));
});

test('cupboard visibly draws every specified object, not just numeric labels', () => {
  const html = worldMarkup('shelf', { type: 'cupboard', items: [{ label: 'Bottles', quantity: 3 }, { label: 'Tubes', quantity: 4 }] });
  assert.equal((html.match(/class="supply-object"/g) ?? []).length, 7);
  assert.ok(html.includes('3 here'));
  assert.ok(html.includes('4 here'));
  assert.throws(() => worldMarkup('bad', { type: 'cupboard', items: [{ label: 'Bottles', quantity: 100 }] }), /quantity/);
});

test('calendar reserves distinct readable text and phone zones and grows for longer dialogue', () => {
  const short = phoneContentFit({ messages: [{ text: 'Same place for lunch?' }] }, false);
  const longer = phoneContentFit({ messages: [{ text: 'A much longer question that needs more room before its receipt and conversation control.' }] }, false);
  assert.equal(short.fontPx, 43);
  assert.ok(short.heightPercent >= 67);
  assert.ok(longer.heightPercent > short.heightPercent);
  assert.ok(longer.topPercent < short.topPercent);
  assert.ok(longer.fontPx >= 38);
  const value = structuredClone(cue); value.visual.type = 'calendar'; value.visual.action = 'reveal'; value.visual.action_phrase = 'pressed call';
  const { html } = buildScene(value, { ...episode, format: 'youtube' }, 0, words);
  assert.ok(html.includes('.calendar-page{position:absolute;left:4%;top:8%;width:55%;height:82%'));
  assert.ok(html.includes('.calendar-note{font-size:31px;line-height:1.2;margin-top:28px;color:#316b67;font-weight:700;max-width:100%'));
  assert.ok(html.includes('.calendar-reply{position:absolute;right:3%;top:27%;width:40%;height:67%'));
  assert.ok(!html.includes('data-layout-allow-occlusion'));
});

test('narrative directions never become visible dialogue or explanatory cards', () => {
  const { html } = buildScene(cue, episode, 0, words);
  assert.ok(!html.includes('PRODUCTION DIRECTION MUST NOT APPEAR'));
  assert.ok(html.includes('ORIGINAL FICTIONAL STORY'));
  assert.ok(html.includes('CALL CONNECTING'));
  assert.ok(!html.includes('textContent:\'SENT\''));
});

test('fiction disclosure and meaningful world are established in static frame-zero HTML', () => {
  const result = buildScene(cue, episode, 0, words);
  assert.ok(result.html.includes('class="world-viewport"'));
  assert.ok(result.html.includes('<h1>One ordinary choice</h1>'));
  assert.ok(result.html.includes('ORIGINAL FICTIONAL STORY'));
  assert.ok(result.html.includes(`window.__timelines['${result.id}']=tl`));
  assert.ok(!result.html.includes('tl.play('));
  assert.ok(!result.html.includes('visibility:'));
  assert.ok(!result.html.includes('Math.random'));
  assert.ok(!result.html.includes('class="final-mark"'), 'no redundant footer may overlay a character');
  assert.ok(!result.html.includes('class="phone-note"'), 'phone control has no floating name label over it');
  assert.equal((result.html.match(/data-layout-allow-overflow/g) ?? []).length, 1, 'only the deliberately cropped moving world is exempt');
  assert.ok(result.html.includes('id="story-01-test-scene-world" data-layout-allow-overflow'));
  assert.ok(!result.html.includes('data-layout-allow-overlap'));
});

test('new draft and sent states reset the prior deletion status at measured arrival', () => {
  const value = structuredClone(cue);
  value.visual.action = 'delete'; value.visual.action_phrase = 'Mira read';
  value.visual.messages = [{ sender: 'draft', text: 'A human reply', at_phrase: 'No thanks.' }, { sender: 'Mira', text: 'A human reply', at_phrase: 'pressed call' }];
  const html = buildScene(value, { ...episode, segments: [value] }, 0, words).html;
  const changes = [];
  const timeline = { set(selector, props, at = 0) { if (String(selector).endsWith('-control-label')) changes.push({ value: props.textContent, at }); return this; }, fromTo() { return this; }, to() { return this; }, addLabel() { return this; } };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], { gsap: { timeline: () => timeline }, document: { getElementById: () => ({ style: {} }) }, window: { __timelines: {} } });
  const at = time => changes.filter(change => change.at <= time).sort((left, right) => left.at - right.at).at(-1)?.value;
  assert.equal(at(1), 'DRAFT DELETED');
  assert.equal(at(2.3), 'UNSENT');
  assert.equal(at(4.5), 'SENT', 'Mira arrival is sufficient even when scene action was delete, not send');
});

test('last scene does not disappear, reset or end on black', () => {
  const result = buildScene(cue, episode, 0, words);
  assert.equal(result.duration, 8);
  assert.ok(!result.html.includes('background:#000'));
  assert.ok(!result.html.includes('fade-to-black'));
  assert.ok(!result.html.includes('visibility:"hidden"'));
  assert.ok(!result.html.includes('opacity:0,duration:8'));
});

test('waiting does not fabricate a typing notification from the other person', () => {
  const value = structuredClone(cue); value.visual.action = 'wait'; value.visual.action_phrase = 'No thanks.';
  const html = buildScene(value, episode, 0, words).html;
  assert.ok(html.includes("tl.set('#story-01-test-scene-typing',{opacity:0},0)"));
  assert.ok(!html.includes("{scale:.6,opacity:0},{scale:1,opacity:1"));
});

test('an empty conversation is a quiet UI state, never an invented message or receipt', () => {
  const empty = worldMarkup('empty', { type: 'room', screen_title: 'Asha', messages: [], expression: 'relieved' });
  assert.ok(empty.includes('No new draft'));
  assert.ok(empty.includes('class="conversation-empty"'));
  assert.ok(!empty.includes('class="sender-name"'));
  assert.ok(!empty.includes('class="message-bubble"'));
  assert.ok(!empty.includes('class="receipt"'));
  const shopping = worldMarkup('shopping', { type: 'room', screen_title: 'Shopping list closed', messages: [], expression: 'relieved' });
  assert.ok(shopping.includes('Shopping list closed'));
  assert.ok(!shopping.includes('No new draft'), 'shopping status remains a list, not a chat');
});

test('deleting an old draft does not delete the later human replacement', () => {
  const value = structuredClone(cue); value.visual.action = 'delete'; value.visual.action_phrase = 'Mira read';
  const prior = { ...cue, id: 'prior', visual: { ...cue.visual, messages: [{ sender: 'draft', text: 'An old recommendation' }] } };
  const html = buildScene(value, { ...episode, segments: [prior, value] }, 1, words).html;
  assert.ok(html.includes('An old recommendation'));
  assert.ok(html.includes("-prior-draft',{x:0,y:0,opacity:1,scale:1},{x:62"));
  assert.ok(!html.includes("-message-0',{x:0,y:0,opacity:1,scale:1},{x:62"));
});

test('established first draft survives zero seek, holds before deletion and is removed afterwards', () => {
  const exports = {};
  const runtime = { module: { exports }, exports, setTimeout, clearTimeout, Date, console };
  vm.runInNewContext(fs.readFileSync(new URL('../videos/biznex-sales-message-repair/assets/vendor/gsap.min.js', import.meta.url), 'utf8'), runtime);
  const { gsap } = exports;
  const localWords = ['At', 'eleven', 'Mira', 'deleted', 'a', 'message'].map((text, index) => ({ text, start: index * .6, end: index * .6 + .45 }));
  const value = { id: 'opening', title: 'The unsent draft', start: 0, end: 5, text: 'At eleven Mira deleted a message', visual: { type: 'phone', headline: 'DON’T HIT SEND', screen_title: 'Asha', expression: 'concerned', camera: 'close', messages: [{ sender: 'draft', text: 'Could I show you some products?', at_phrase: 'At eleven' }], action: 'delete', action_phrase: 'deleted a message' } };
  const html = buildScene(value, { ...episode, format: 'youtube', segments: [value] }, 0, localWords).html;
  const nodes = new Map();
  const target = selector => {
    if (typeof selector !== 'string') return selector;
    if (!nodes.has(selector)) nodes.set(selector, { opacity: 1, x: 0, y: 0, scale: 1, textContent: 'UNSENT', style: {} });
    return nodes.get(selector);
  };
  let real;
  const timeline = { set(selector, props, at) { real.set(target(selector), props, at); return this; }, fromTo(selector, from, to, at) { real.fromTo(target(selector), from, to, at); return this; }, to(selector, to, at) { real.to(target(selector), to, at); return this; }, addLabel(label, at) { real.addLabel(label, at); return this; } };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], { gsap: { timeline: () => { real = gsap.timeline({ paused: true }); return timeline; } }, document: { getElementById: id => target('#' + id) }, window: { __timelines: {} } });
  const draft = target('#story-01-opening-message-0');
  try {
    real.seek(0); assert.equal(draft.opacity, 1);
    real.seek(1.2); assert.equal(draft.opacity, 1);
    real.seek(1.79); assert.equal(draft.opacity, 1);
    real.seek(2.6); assert.equal(draft.opacity, 0);
    real.seek(0); assert.equal(draft.opacity, 1, 'backward seek restores the established message');
  } finally { real.kill(); gsap.ticker.sleep(); }
});

test('thumbnail promise is the authored title and uses actual episode props', () => {
  const html = thumbnailHtml(episode);
  assert.ok(html.includes('DON&#39;T HIT SEND'));
  assert.ok(html.includes('No thanks.'));
  assert.ok(html.includes('ORIGINAL FICTIONAL STORY'));
  assert.ok(!html.includes('REPAIR LAB'));
  assert.ok(!html.includes('Amazing services'));
  assert.ok(!html.includes('<script'));
  assert.throws(() => thumbnailHtml({ ...episode, thumbnail_headline: '' }), /promise/);
});

test('phone thumbnails put the human message beside the draft, not alone in a blank phone', () => {
  const draft = { ...cue, visual: { ...cue.visual, messages: [{ sender: 'draft', text: 'Could I show you some products?' }] } };
  const turn = { ...cue, id: 'turn', narrative_role: 'turn', visual: { ...cue.visual, messages: [{ sender: 'Asha', text: 'Can we talk?' }] } };
  const choice = { ...cue, narrative_role: 'choice', visual: { ...cue.visual, messages: [{ sender: 'Mira', text: 'I’m here. Do you still want to talk?' }] } };
  const source = { ...episode, segments: [draft, turn, choice], story: { turn_segment: 'turn' } };
  const short = thumbnailHtml(source), full = thumbnailHtml({ ...source, format: 'youtube' });
  assert.ok(short.includes('human-stakes-thread'));
  assert.ok(short.includes('Can we talk?') && short.includes('Could I show you some products?'));
  assert.ok(short.includes('class="thumb-person"'));
  assert.ok(full.includes('deleted-draft-and-human-reply'));
  assert.ok(full.includes('THE DRAFT SHE REMOVED') && full.includes('THE MESSAGE SHE SENT'));
  assert.ok(full.includes('I’m here. Do you still want to talk?'));
  assert.ok(!short.includes('THE MESSAGE SHE SENT'), 'Short and full thumbnail composition are distinct');
  assert.ok(full.includes('DON&#39;T HIT SEND'));
});

test('untrusted authored text is escaped in both ordinary and thumbnail HTML', () => {
  assert.equal(escapeHtml('<script>"x"&\'y\''), '&lt;script&gt;&quot;x&quot;&amp;&#39;y&#39;');
  const injected = structuredClone(episode); injected.thumbnail_headline = '</h1><script>oops()</script>';
  const html = thumbnailHtml(injected);
  assert.ok(!html.includes('<script>oops()'));
  assert.ok(html.includes('&lt;script&gt;'));
});

test('full assembly covers pauses and the complete final measured tail', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'story-composition-'));
  try {
    const first = structuredClone(cue); first.id = 'first'; first.start = 0; first.end = 7;
    const second = structuredClone(cue); second.id = 'last'; second.start = 8; second.end = 15;
    const sourceWords = words.map(word => ({ ...word, start: word.start - 10, end: word.end - 10 }));
    const measured = { total_duration_s: 16.32, cues: [first, second], voices: [{ path: 'assets/voice/01.wav', duration_s: 16.32, words: [...sourceWords, ...sourceWords.map(word => ({ ...word, start: word.start + 8, end: word.end + 8 }))] }], sfx: [{ file: 'assets/sfx/chime.wav', offset_s: 8.2, duration_s: .57 }] };
    fs.writeFileSync(path.join(project, 'audio_meta.json'), JSON.stringify(measured));
    fs.writeFileSync(path.join(project, 'STORYBOARD.md'), '- status: outline\n');
    const result = buildEpisode(project, { ...episode, segments: [first, second] });
    assert.equal(result.duration, 16.32);
    const index = fs.readFileSync(path.join(project, 'index.html'), 'utf8');
    assert.ok(index.includes('data-duration="16.320"'));
    assert.ok(index.includes('data-start="0.000" data-duration="8.000"'));
    assert.ok(index.includes('data-start="8.000" data-duration="8.320"'));
    assert.ok(index.includes('id="voiceover"'));
    assert.ok(index.includes('data-track-kind="captions"'));
    assert.ok(!index.includes('assets/sfx/chime.wav'), 'a fixed setup chime is not a narrative action');
    const caption = fs.readFileSync(path.join(project, 'compositions', 'captions.html'), 'utf8');
    assert.ok(caption.includes('54px/1.2'));
    assert.ok(caption.includes('time>groups[found].end'));
    const sidecar = JSON.parse(fs.readFileSync(path.join(project, 'compositions', 'frames', 'last.motion.json'), 'utf8'));
    assert.equal(sidecar.duration, 8.32);
    assert.ok(sidecar.assertions.every(assertion => ['appearsBy', 'staysInFrame'].includes(assertion.kind)));
    assert.equal(fs.readFileSync(path.join(project, 'STORYBOARD.md'), 'utf8'), '- status: animated\n');
    assert.ok(fs.existsSync(path.join(project, '.hyperframes', 'expanded-prompt.md')));
    assert.ok(fs.existsSync(path.join(project, '.hyperframes', 'animation-map.md')));
    assert.ok(fs.existsSync(path.join(project, 'THUMBNAIL_COPY.md')));
  } finally { fs.rmSync(project, { recursive: true, force: true }); }
});

test('assembly rejects misordered cue identities and uncovered opening time', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'story-composition-errors-'));
  try {
    const audio = { total_duration_s: 20, cues: [{ ...cue, start: 1 }], voices: [{ words }] };
    fs.writeFileSync(path.join(project, 'audio_meta.json'), JSON.stringify(audio));
    assert.throws(() => buildEpisode(project, episode), /start at zero/);
    audio.cues[0].start = 0; audio.cues[0].id = 'different';
    fs.writeFileSync(path.join(project, 'audio_meta.json'), JSON.stringify(audio));
    assert.throws(() => buildEpisode(project, episode), /identity mismatch/);
  } finally { fs.rmSync(project, { recursive: true, force: true }); }
});

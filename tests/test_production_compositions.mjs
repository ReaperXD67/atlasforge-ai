import test from 'node:test';
import assert from 'node:assert/strict';
import { captionGroups, cueBeats, alignedDisplayBeats } from '../scripts/build_production_compositions.mjs';

test('captions use measured words, bounded reading groups and real pauses', () => {
  const groups = captionGroups([
    { text: 'One', start: 0, end: .2 },
    { text: 'small', start: .25, end: .5 },
    { text: 'question.', start: .6, end: .9 },
    { text: 'Next', start: 2, end: 2.3 },
    { text: 'step', start: 2.4, end: 2.8 },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].start, 0);
  assert.equal(groups[1].start, 2);
  assert.ok(groups[0].end < 2, 'genuine acoustic pause stays empty');
  assert.equal(groups[1].words[1].end, 2.8);
});

test('caption group cannot grow beyond word/character budget', () => {
  const words = Array.from({ length: 20 }, (_, index) => ({ text: 'measured', start: index, end: index + .8 }));
  for (const group of captionGroups(words, 4, 27)) {
    assert.ok(group.words.length <= 4);
    assert.ok(group.words.map(word => word.text).join(' ').length <= 27);
  }
});

test('empty or invalid ASR word intervals do not fabricate captions', () => {
  assert.deepEqual(captionGroups([{ text: '', start: 0, end: 1 }, { text: 'bad', start: 4, end: 2 }]), []);
});

test('cue display timings preserve acoustic anchors and require measured data', () => {
  assert.deepEqual(cueBeats({ id: 'demo', start: 10, end: 20, beats: [1, 4, 7] }, 3), [0, 4, 7]);
  assert.throws(() => cueBeats({ id: 'missing', start: 0, end: 4 }, 3), /Missing measured/);
  assert.throws(() => cueBeats({ id: 'bad', start: 0, end: 4, beats: [5] }, 3), /Invalid local/);
});

test('a literal display phrase wins over generic segment fallback timing', () => {
  const cue = { id: 'literal', start: 10, end: 20, beats: [0, 2, 7], display: ['Sample', 'Deliverable', 'Small question'] };
  const words = [
    { text: 'One', start: 12.7, end: 13 },
    { text: 'deliverable.', start: 13, end: 13.5 },
    { text: 'small', start: 17.1, end: 17.5 },
    { text: 'question.', start: 17.5, end: 18 },
  ];
  const beats = alignedDisplayBeats(cue, words);
  assert.equal(beats[0], 0, 'first-frame subject is immediately visible');
  assert.equal(beats[1], 3, 'actual deliverable word replaces fallback2s');
  assert.ok(Math.abs(beats[2] - 7.1) < .0001);
});

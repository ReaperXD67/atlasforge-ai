const test = require("node:test");
const assert = require("node:assert/strict");
const { focusCameraAt, matchCutAt, easePeak, captionAtFrame } = require("../scripts/lib/cinematic_primitives.js");

test("camera clamp covers viewport even at edge anchors and maximum drift", () => {
  for (const anchor of [0, 25, 50, 75, 100]) {
    for (let frame = 0; frame <= 180; frame += 1) {
      const pose = focusCameraAt(frame, { startFrame: 0, endFrame: 180, anchorX: anchor, anchorY: 100 - anchor,
        endZoom: 2, driftX: 2, driftY: 2 });
      const limit = 50 * (pose.scale - 1);
      assert.ok(Math.abs(pose.xPercent) <= limit + 1e-12);
      assert.ok(Math.abs(pose.yPercent) <= limit + 1e-12);
    }
  }
});

test("camera endpoints settle exactly and backward seeks reproduce state", () => {
  const options = { startFrame: 30, endFrame: 150, anchorX: 70, anchorY: 40, endZoom: 1.8, driftX: 0.2 };
  assert.deepEqual(focusCameraAt(0, options), { scale: 1, xPercent: 0, yPercent: 0, progress: 0 });
  const middle = focusCameraAt(72, options);
  assert.deepEqual(focusCameraAt(150, options), focusCameraAt(500, options));
  assert.deepEqual(focusCameraAt(72, options), middle);
});

test("shared match motion swaps precisely at peak velocity with no blank frame", () => {
  const opts = { cutFrame: 120, halfDurationFrames: 12, axis: "x", distancePercent: 8 };
  const before = matchCutAt(119, opts);
  const cut = matchCutAt(120, opts);
  const after = matchCutAt(121, opts);
  assert.equal(cut.xPercent, 0);
  assert.equal(before.outgoingOpacity, 1);
  assert.equal(cut.incomingOpacity, 1);
  assert.ok(before.xPercent < cut.xPercent && cut.xPercent < after.xPercent);
  assert.ok(Math.abs(before.xPercent + after.xPercent) < 1e-7);
  for (let frame = 105; frame < 140; frame++) {
    const pose = matchCutAt(frame, opts);
    assert.equal(pose.outgoingOpacity + pose.incomingOpacity, 1);
  }
  assert.deepEqual(before, matchCutAt(119, opts));
});

test("peak curve is bounded monotonic and symmetric", () => {
  let last = 0;
  for (let i = 0; i <= 100; i++) {
    const value = easePeak(i / 100);
    assert.ok(value >= last && value <= 1);
    assert.ok(Math.abs(value + easePeak(1 - i / 100) - 1) < 1e-7);
    last = value;
  }
  assert.equal(easePeak(-10), 0);
  assert.equal(easePeak(10), 1);
});

test("invalid camera or cut inputs fail instead of introducing NaN frames", () => {
  for (const options of [{ startFrame: 0, endFrame: 0 }, { startFrame: 0, endFrame: 30, endZoom: 0.8 },
    { startFrame: 0, endFrame: 30, anchorX: NaN }, { startFrame: 0, endFrame: 30, cycles: 1.5 }]) {
    assert.throws(() => focusCameraAt(0, options), RangeError);
  }
  assert.throws(() => matchCutAt(30, { cutFrame: 2 }), RangeError);
  assert.throws(() => matchCutAt(30, { cutFrame: 30, axis: "random" }), RangeError);
});

test("captions use measured ranges, preserve silence and exclude end frame", () => {
  const compiled = { captions: [{ id: "c1", text: "Fresh start?", start_frame: 15, end_frame: 36,
    words: [{ text: "Fresh", index: 0, start_frame: 15, end_frame: 20 },
      { text: "start?", index: 1, start_frame: 25, end_frame: 33 }] }] };
  assert.equal(captionAtFrame(compiled, 14), null);
  assert.equal(captionAtFrame(compiled, 15).activeWordIndex, 0);
  assert.equal(captionAtFrame(compiled, 23).activeWordIndex, null);
  assert.equal(captionAtFrame(compiled, 26).activeWordIndex, 1);
  assert.equal(captionAtFrame(compiled, 35).activeWordIndex, null);
  assert.equal(captionAtFrame(compiled, 36), null);
});

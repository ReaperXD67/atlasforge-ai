import test from "node:test";
import assert from "node:assert/strict";
import { makeStoryState, MODES } from "../scripts/lib/procedural_story_state.mjs";

function fixture() {
  const modes = MODES.filter((mode) => mode !== "pressure");
  let cursor = 0;
  const direction = { shots: {} };
  const shots = modes.map((mode, index) => {
    const id = `s${index + 1}`;
    direction.shots[id] = { mode };
    const shot = { id, start_frame: cursor, end_frame: cursor + (mode === "choice" ? 150 : 90) };
    cursor = shot.end_frame;
    return shot;
  });
  return { plan: { width: 1080, height: 1920, fps: 30, duration_frames: cursor, shots }, direction };
}

test("all covered frames have finite cameras and seeking is independent of history", () => {
  const { plan, direction } = fixture();
  const initial = structuredClone({ plan, direction });
  const state = makeStoryState(plan, direction);
  const first = state(120);
  for (let frame = 0; frame < plan.duration_frames; frame++) {
    const s = state(frame);
    assert.equal(s.frame, frame);
    assert.ok([...s.camera, ...s.look_at].every(Number.isFinite));
    assert.ok(MODES.includes(s.mode));
  }
  assert.deepEqual(state(120), first);
  assert.deepEqual({ plan, direction }, initial);
});

test("frame quantization selects the same pose at rounded host boundaries", () => {
  const { plan, direction } = fixture();
  const state = makeStoryState(plan, direction);
  for (const shot of plan.shots) {
    assert.deepEqual(state(shot.start_frame - 0.015), state(shot.start_frame));
    assert.deepEqual(state(shot.start_frame + 0.015), state(shot.start_frame));
  }
  assert.equal(state(-100).frame, 0);
  assert.equal(state(plan.duration_frames + 100).frame, plan.duration_frames - 1);
  assert.throws(() => state(NaN), /finite/);
});

test("domino impacts begin at the little-yes macro anchor and stop before money", () => {
  const { plan, direction } = fixture();
  const state = makeStoryState(plan, direction);
  const macro = plan.shots.find((s) => direction.shots[s.id].mode === "chain_macro");
  assert.equal(state(macro.start_frame - 1).chain, 0);
  assert.ok(state(macro.start_frame + 30).chain > 0);
  assert.equal(state(macro.end_frame).chain, 1);
});

test("the pause freezes every accumulated mechanical state", () => {
  const { plan, direction } = fixture();
  const state = makeStoryState(plan, direction);
  const still = plan.shots.find((s) => direction.shots[s.id].mode === "still");
  const a = state(still.start_frame), b = state(still.end_frame - 1);
  for (const key of ["chain", "money", "clock", "packages", "brake"]) assert.equal(a[key], b[key]);
  assert.deepEqual(a.camera, b.camera);
  assert.ok(a.paused && b.paused);
});

test("the final reveal and camera settle early enough for a readable held choice", () => {
  const { plan, direction } = fixture();
  const state = makeStoryState(plan, direction);
  const shot = plan.shots.at(-1);
  const settled = state(shot.start_frame + 60), last = state(shot.end_frame - 1);
  assert.equal(settled.choice, 1);
  assert.equal(settled.not_now_press, 1);
  assert.deepEqual(settled.camera, last.camera);
  assert.ok(shot.end_frame - (shot.start_frame + 60) >= 45);
});

test("missing, overlapping and fractional shot ranges fail before rendering", () => {
  for (const mutate of [
    ({ plan }) => { plan.shots[2].start_frame += 1; },
    ({ plan }) => { plan.shots[2].start_frame -= 1; },
    ({ plan }) => { plan.shots[2].start_frame += 0.5; },
    ({ plan }) => { plan.shots.pop(); },
    ({ direction }) => { direction.shots.s2.mode = "unknown"; },
    ({ direction }) => { direction.shots.s2.camera_from = [1, Infinity, 3]; },
  ]) {
    const f = fixture(); mutate(f);
    assert.throws(() => makeStoryState(f.plan, f.direction));
  }
});

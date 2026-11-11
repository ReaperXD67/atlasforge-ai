import test from "node:test";
import assert from "node:assert/strict";
import {
  MODES,
  makeQuestionState,
  ribbonSection,
} from "../scripts/lib/question_story_state.mjs";
function fixture() {
  const direction = { shots: {} };
  const shots = MODES.map((mode, i) => {
    const id = "s" + i;
    direction.shots[id] = { mode };
    return { id, start_frame: i * 60, end_frame: (i + 1) * 60 };
  });
  return {
    direction,
    plan: { fps: 30, width: 1080, height: 1920, duration_frames: 720, shots },
  };
}
test("all poses are finite, reversible and frame-boundary exact", () => {
  const { plan, direction } = fixture(),
    state = makeQuestionState(plan, direction),
    original = state(180);
  for (let f = 0; f < 720; f++) {
    const s = state(f);
    assert.ok(
      [...s.camera, ...s.look_at, s.unroll, s.travel].every(Number.isFinite),
    );
  }
  assert.deepEqual(state(180), original);
  for (const s of plan.shots)
    assert.deepEqual(
      state(s.start_frame - 0.015),
      state(s.start_frame + 0.015),
    );
  assert.throws(() => state(NaN), /finite/);
});
test("ribbon becomes a connected bridge before the message crosses, then holds", () => {
  const { plan, direction } = fixture(),
    state = makeQuestionState(plan, direction);
  assert.equal(state(9 * 60).unroll, 1);
  assert.equal(state(9 * 60).travel, 0);
  assert.equal(state(11 * 60).travel, 1);
  assert.deepEqual(state(11 * 60 + 24).camera, state(719).camera);
  assert.equal(state(719).core_scale, 1);
  for (const [u, x] of [
    [0, -2.75],
    [1, 2.75],
  ]) {
    const p = ribbonSection(u, 1, 0);
    assert.equal(p.center[0], x);
    assert.ok(Math.abs(p.center[1] - 0.64) < 1e-12);
    assert.deepEqual(p.side, [0, 0, 1]);
  }
});
test("every deforming section has finite nondegenerate surface directions", () => {
  for (let v = 0; v < 3; v++)
    for (let k = 0; k <= 20; k++)
      for (let i = 0; i <= 160; i++) {
        const u = i / 160,
          p = ribbonSection(u, k / 20, v),
          a = ribbonSection(Math.max(0, u - 0.001), k / 20, v),
          b = ribbonSection(Math.min(1, u + 0.001), k / 20, v);
        assert.ok([...p.center, ...p.side].every(Number.isFinite));
        const t = b.center.map((x, j) => x - a.center[j]),
          s = p.side,
          n = [
            t[1] * s[2] - t[2] * s[1],
            t[2] * s[0] - t[0] * s[2],
            t[0] * s[1] - t[1] * s[0],
          ];
        assert.ok(Math.hypot(...n) > 1e-7, "surface must retain a normal");
      }
  assert.throws(() => ribbonSection(2, 0), /Invalid/);
});
test("invalid scene order, duplicate modes and gaps fail before rendering", () => {
  for (const change of [
    (x) => x.plan.shots[3].start_frame++,
    (x) => (x.direction.shots.s2.mode = "compliment"),
    (x) => (x.direction.shots.s4.mode = "answer"),
    (x) => x.plan.shots.pop(),
  ]) {
    const f = fixture();
    change(f);
    assert.throws(() => makeQuestionState(f.plan, f.direction));
  }
});

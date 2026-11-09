import test from "node:test";
import assert from "node:assert/strict";
import {
  makeCountdownState,
  MODES,
} from "../scripts/lib/countdown_story_state.mjs";

function fixture() {
  const direction = { shots: {} };
  const shots = MODES.map((mode, index) => {
    const id = "shot-" + index;
    direction.shots[id] = { mode };
    return { id, start_frame: index * 60, end_frame: (index + 1) * 60 };
  });
  return {
    direction,
    plan: {
      width: 1080,
      height: 1920,
      fps: 30,
      duration_frames: shots.at(-1).end_frame,
      shots,
    },
  };
}

test("every frame has finite camera/token poses and backseek is deterministic", () => {
  const { plan, direction } = fixture();
  const state = makeCountdownState(plan, direction);
  const a = state(145);
  for (let f = 0; f < plan.duration_frames; f++) {
    const s = state(f);
    assert.ok([...s.camera, ...s.look_at, ...s.token].every(Number.isFinite));
    assert.ok(
      Number.isInteger(s.countdown) && s.countdown >= 0 && s.countdown <= 10,
    );
  }
  assert.deepEqual(state(145), a);
});

test("token stops while countdown keeps going, then leaves by its independent side route", () => {
  const { plan, direction } = fixture();
  const state = makeCountdownState(plan, direction);
  const halt = plan.shots.find((s) => direction.shots[s.id].mode === "halt");
  const exit = plan.shots.find((s) => direction.shots[s.id].mode === "exit");
  assert.deepEqual(
    state(halt.start_frame).token,
    state(exit.start_frame - 1).token,
  );
  assert.ok(
    state(exit.start_frame - 1).countdown < state(halt.start_frame).countdown,
  );
  assert.ok(state(exit.start_frame + 50).token[0] > 0);
});

test("final counter is zero and the quiet token/camera settle before ending", () => {
  const { plan, direction } = fixture();
  const state = makeCountdownState(plan, direction);
  const final = plan.shots.at(-1);
  const settled = state(final.start_frame + 30);
  assert.equal(settled.countdown, 0);
  assert.equal(settled.exit, 1);
  assert.deepEqual(settled.token, state(final.end_frame - 1).token);
  assert.deepEqual(settled.camera, state(final.end_frame - 1).camera);
});

test("host boundary rounding uses the right shot on first frame", () => {
  const { plan, direction } = fixture();
  const state = makeCountdownState(plan, direction);
  for (const shot of plan.shots) {
    assert.deepEqual(state(shot.start_frame - 0.015), state(shot.start_frame));
    assert.deepEqual(state(shot.start_frame + 0.015), state(shot.start_frame));
  }
  assert.throws(() => state(NaN), /finite/);
});

test("unknown scenes and incomplete/fractional coverage fail before drawing", () => {
  for (const mutate of [
    (f) => {
      f.plan.shots[2].start_frame += 1;
    },
    (f) => {
      f.plan.shots[2].start_frame -= 0.5;
    },
    (f) => {
      f.direction.shots["shot-2"].mode = "old-machine";
    },
    (f) => {
      f.direction.shots["shot-3"].mode = "countdown";
    },
    (f) => {
      f.direction.shots["shot-4"].mode = "halt";
      f.direction.shots["shot-5"].mode = "reach";
    },
    (f) => {
      f.plan.shots.pop();
    },
  ]) {
    const f = fixture();
    mutate(f);
    assert.throws(() => makeCountdownState(f.plan, f.direction));
  }
});

/** Original pure choreography. One measured frame clock, no simulation history. */
export const MODES = [
  "button_macro",
  "button_press",
  "chain",
  "chain_macro",
  "money",
  "clock",
  "unused",
  "pressure",
  "brake",
  "still",
  "gate_cost",
  "gate_use",
  "gate_life",
  "choice",
];
const clamp = (x) => Math.max(0, Math.min(1, x));
export const ease = (x) => {
  x = clamp(x);
  return x * x * (3 - 2 * x);
};
const mix = (a, b, p) => a + (b - a) * p;
const PRESETS = {
  button_macro: [
    [-2, 3.5, 5.2],
    [-2, 3.1, 4.8],
    [-2, 0.2, 0.65],
  ],
  button_press: [
    [-2.1, 2.4, 4.1],
    [-1.9, 2.1, 3.8],
    [-2, 0.22, 0.65],
  ],
  chain: [
    [2.8, 2.4, 4.8],
    [1.4, 2.6, 4.2],
    [0.15, -0.15, -0.45],
  ],
  chain_macro: [
    [-1.1, 2.0, 2.5],
    [-0.8, 1.9, 2.4],
    [-0.4, -0.55, -0.5],
  ],
  money: [
    [-2.8, 3.0, 1.8],
    [-2.55, 2.8, 1.65],
    [-2.1, -0.35, -1.0],
  ],
  clock: [
    [1.7, 3.9, 3.6],
    [1.7, 3.5, 3.3],
    [1.7, 0.18, 0.65],
  ],
  unused: [
    [3.1, 3.1, 2.0],
    [2.8, 2.9, 1.8],
    [2.25, 0.0, -1.0],
  ],
  pressure: [
    [2.3, 8.3, 9.1],
    [1.4, 7.8, 8.5],
    [0.1, 0.3, -0.1],
  ],
  brake: [
    [0.3, 3.0, 4.0],
    [0.1, 2.6, 3.8],
    [0, 0.28, 1.2],
  ],
  still: [
    [1.3, 7.7, 9],
    [1.3, 7.7, 9],
    [0, 0.2, 0],
  ],
  gate_cost: [
    [-1.55, 2.4, 5.4],
    [-1.5, 2.3, 5.1],
    [-1.5, 0.65, 1.35],
  ],
  gate_use: [
    [0, 2.4, 5.4],
    [0, 2.3, 5.1],
    [0, 0.65, 1.35],
  ],
  gate_life: [
    [1.55, 2.4, 5.4],
    [1.5, 2.3, 5.1],
    [1.5, 0.65, 1.35],
  ],
  choice: [
    [0, 5.6, 7.8],
    [0, 5.3, 7.4],
    [0, 0.15, 0.65],
  ],
};

export function makeStoryState(plan, direction) {
  if (
    plan.fps !== 30 ||
    plan.width !== 1080 ||
    plan.height !== 1920 ||
    !Number.isInteger(plan.duration_frames)
  )
    throw Error("Procedural film requires 1080x1920 at 30fps");
  const shots = plan.shots.map((s) => {
    const d = direction.shots[s.id];
    if (!d || !MODES.includes(d.mode))
      throw Error(`Unknown/missing visual mode for ${s.id}`);
    return { ...s, d };
  });
  if (
    !shots.length ||
    shots[0].start_frame !== 0 ||
    shots.at(-1).end_frame !== plan.duration_frames
  )
    throw Error("Incomplete shot coverage");
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i];
    if (
      !Number.isInteger(s.start_frame) ||
      !Number.isInteger(s.end_frame) ||
      s.end_frame <= s.start_frame ||
      (i && s.start_frame !== shots[i - 1].end_frame)
    )
      throw Error("Shot ranges must partition the voice clock");
    for (const key of ["camera_from", "camera_to", "look_at"])
      if (
        s.d[key] &&
        (!Array.isArray(s.d[key]) ||
          s.d[key].length !== 3 ||
          !s.d[key].every(Number.isFinite))
      )
        throw Error("Camera coordinates must be finite triples");
  }
  const at = (mode) => shots.find((s) => s.d.mode === mode);
  const start = (mode, fallback = 0) => at(mode)?.start_frame ?? fallback;
  const end = (mode, fallback = plan.duration_frames) =>
    at(mode)?.end_frame ?? fallback;
  const progress = (frame, mode) =>
    ease((frame - start(mode)) / (end(mode) - start(mode)));
  const pause = start("still", start("gate_cost"));
  return (frame) => {
    if (!Number.isFinite(frame)) throw Error("Frame must be finite");
    const f = Math.max(
      0,
      Math.min(plan.duration_frames - 1, Math.round(frame)),
    );
    const shot = shots.find((s) => f >= s.start_frame && f < s.end_frame),
      d = shot.d;
    const p = ease(
      (f - shot.start_frame) /
        (d.mode === "choice"
          ? 60
          : Math.max(1, shot.end_frame - shot.start_frame - 1)),
    );
    const preset = PRESETS[d.mode],
      from = d.camera_from || preset[0],
      to = d.camera_to || preset[1];
    const frozen = Math.min(f, pause),
      choice = ease((f - start("choice")) / 45);
    return {
      frame: f,
      shot_id: shot.id,
      mode: d.mode,
      shot_progress: p,
      heading: d.heading || "",
      hide_captions: !!d.hide_captions,
      camera: from.map((v, i) => mix(v, to[i], p)),
      look_at: d.look_at || preset[2],
      press:
        ease((f - start("button_press")) / 10) *
        (1 - ease((f - start("chain")) / 18)),
      chain: ease(
        (frozen - start("chain_macro")) /
          Math.max(1, end("chain_macro") - start("chain_macro")),
      ),
      money: progress(frozen, "money"),
      clock: Math.max(0, frozen - start("clock")) / 30,
      packages: ease(
        (frozen - start("unused")) /
          Math.max(1, start("brake") - start("unused")),
      ),
      brake: progress(f, "brake"),
      paused: f >= pause,
      gates: ["gate_cost", "gate_use", "gate_life"].map((m) => ({
        rise: ease((f - start(m)) / 10),
        open: progress(f, m),
      })),
      choice,
      not_now_press: ease((f - start("choice") - 42) / 15),
      stopped_frame: pause,
      disclosure: f < end("button_press"),
      end_context: d.mode === "choice",
    };
  };
}

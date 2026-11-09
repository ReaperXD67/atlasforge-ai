/** Original analytical countdown choreography. Every pose is derived from a frame. */
export const clamp = (value) => Math.max(0, Math.min(1, value));
export const ease = (value) => {
  const p = clamp(value);
  return p * p * (3 - 2 * p);
};
export const MODES = [
  "timer_macro",
  "reason_empty",
  "countdown",
  "want",
  "reach",
  "halt",
  "question",
  "backstage",
  "exit",
  "numbers",
  "clock_finish",
  "empty_front",
  "resolve",
];
const CAMERAS = {
  timer_macro: [
    [0, 2.8, 6.9],
    [0.12, 2.7, 6.6],
    [0, 1.25, 0],
  ],
  reason_empty: [
    [0.3, 4.0, 4.8],
    [0.1, 3.7, 4.4],
    [0, -0.15, 1.7],
  ],
  countdown: [
    [-0.35, 3.6, 8.7],
    [0, 3.3, 8.2],
    [0, 0.85, 0.25],
  ],
  want: [
    [-2.2, 2.8, 5.6],
    [-1.5, 2.5, 5.3],
    [0, 0.25, 1.35],
  ],
  reach: [
    [0.3, 2.1, 3.7],
    [0.1, 1.9, 3.3],
    [0, -0.05, 1.05],
  ],
  halt: [
    [0.1, 2.4, 4.1],
    [0.1, 2.4, 4.1],
    [0, -0.1, 0.95],
  ],
  question: [
    [-3.4, 3.0, 6.0],
    [-2.8, 3.2, 5.6],
    [0, 0.7, 0.3],
  ],
  backstage: [
    [3.6, 3.0, 2.4],
    [3.2, 2.8, -3.3],
    [0.2, 1.3, -0.15],
  ],
  exit: [
    [1.5, 6.7, 7.2],
    [1.7, 6.3, 6.9],
    [1.15, 0.05, 1.15],
  ],
  numbers: [
    [1.8, 2.6, 6.2],
    [2.3, 2.7, 5.8],
    [0.4, 1.1, 0],
  ],
  clock_finish: [
    [2.0, 5.8, 12.2],
    [2.0, 5.6, 11.9],
    [0.6, 0.9, 0.2],
  ],
  empty_front: [
    [0, 2.9, 7.2],
    [0, 2.9, 7.2],
    [0, 1.1, 0],
  ],
  resolve: [
    [2.4, 3.2, 3.6],
    [2.4, 3.0, 3.4],
    [2.28, -0.3, 1.07],
  ],
};

export function makeCountdownState(plan, direction) {
  if (
    plan.fps !== 30 ||
    plan.width !== 1080 ||
    plan.height !== 1920 ||
    !Number.isInteger(plan.duration_frames)
  )
    throw Error("Countdown requires 1080x1920 at 30fps");
  const shots = plan.shots.map((shot) => ({
    ...shot,
    d: direction.shots[shot.id],
  }));
  if (
    !shots.length ||
    shots[0].start_frame !== 0 ||
    shots.at(-1).end_frame !== plan.duration_frames
  )
    throw Error("Incomplete countdown shot coverage");
  for (let i = 0; i < shots.length; i++) {
    const shot = shots[i];
    if (!shot.d || !MODES.includes(shot.d.mode))
      throw Error("Unknown countdown mode");
    if (
      !Number.isInteger(shot.start_frame) ||
      !Number.isInteger(shot.end_frame) ||
      shot.end_frame <= shot.start_frame ||
      (i && shot.start_frame !== shots[i - 1].end_frame)
    )
      throw Error("Shot ranges must partition the frame clock");
  }
  const at = (mode) => shots.find((shot) => shot.d.mode === mode);
  const start = (mode) => {
    const shot = at(mode);
    if (!shot) throw Error("Missing countdown story anchor: " + mode);
    return shot.start_frame;
  };
  for (const mode of [
    "countdown",
    "reach",
    "halt",
    "backstage",
    "exit",
    "clock_finish",
    "resolve",
  ])
    start(mode);
  const modes = shots.map((shot) => shot.d.mode);
  if (new Set(modes).size !== modes.length)
    throw Error("Countdown scene modes must be unique");
  for (let index = 1; index < modes.length; index++) {
    if (MODES.indexOf(modes[index]) <= MODES.indexOf(modes[index - 1]))
      throw Error("Countdown scenes must preserve causal order");
  }
  const firstTick = start("countdown");
  const lastTick = start("resolve") - 4;
  if (lastTick <= firstTick)
    throw Error("Countdown must precede the resolution");
  return (frame) => {
    if (!Number.isFinite(frame)) throw Error("Frame must be finite");
    const f = Math.max(
      0,
      Math.min(plan.duration_frames - 1, Math.round(frame)),
    );
    const shot = shots.find(
      (item) => f >= item.start_frame && f < item.end_frame,
    );
    const mode = shot.d.mode;
    const progress = ease(
      (f - shot.start_frame) /
        (mode === "resolve"
          ? 30
          : Math.max(1, shot.end_frame - shot.start_frame - 1)),
    );
    const [from, to, target] = CAMERAS[mode];
    const ticks = clamp((f - firstTick) / (lastTick - firstTick)) * 10;
    const value = 10 - Math.floor(ticks);
    const reach = ease(
      (f - start("reach")) / Math.max(1, start("halt") - start("reach")),
    );
    const exit = ease(
      (f - start("exit")) / Math.max(30, start("clock_finish") - start("exit")),
    );
    const question = mode === "question" || mode === "backstage";
    return {
      frame: f,
      shot_id: shot.id,
      mode,
      progress,
      camera: from.map((v, i) => v + (to[i] - v) * progress),
      look_at: target,
      heading: shot.d.heading || "",
      hide_captions: !!shot.d.hide_captions,
      countdown: value,
      tick_phase: ticks % 1,
      ticks,
      token: [
        2.28 * exit,
        0.17,
        1.95 - 0.88 * reach + Math.sin(exit * Math.PI) * 0.37,
      ],
      reach,
      exit,
      quiet: f >= start("halt"),
      show_reason: f >= start("resolve"),
      shadow_pressure:
        0.35 +
        0.65 * ease((f - firstTick) / Math.max(1, start("halt") - firstTick)),
      end_context: f >= start("clock_finish"),
      disclosure: f < at("countdown").end_frame,
      question,
    };
  };
}

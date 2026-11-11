/** Original fixed-topology ribbon choreography; no simulation history or random state. */
export const clamp = (x) => Math.max(0, Math.min(1, x));
export const ease = (x) => {
  const p = clamp(x);
  return p * p * (3 - 2 * p);
};
export const MODES = [
  "seed",
  "compliment",
  "apology",
  "approach",
  "send",
  "missing",
  "reset",
  "fewer",
  "plain",
  "question",
  "clarity",
  "answer",
];
const CAMERAS = {
  seed: [
    [0, 3.3, 7.5],
    [0.3, 3.1, 7],
    [0, 1.25, 0],
  ],
  compliment: [
    [-3, 3.5, 7.1],
    [-2.5, 3.3, 6.7],
    [0, 1.2, 0],
  ],
  apology: [
    [2.9, 3.8, 6.7],
    [2.4, 3.4, 6.4],
    [0, 1.4, 0],
  ],
  approach: [
    [0, 6.8, 17.8],
    [0, 6.5, 17.3],
    [0, 0.8, 0],
  ],
  send: [
    [-3.7, 2.2, 4.9],
    [-3.2, 2, 4.7],
    [-0.6, 1.1, 0],
  ],
  missing: [
    [0.6, 2.4, 5.7],
    [0.3, 2.2, 5.3],
    [0, 1.5, 0],
  ],
  reset: [
    [0, 4.5, 8.6],
    [0, 4.3, 8.3],
    [0, 0.9, 0],
  ],
  fewer: [
    [-3.2, 3.6, 7.4],
    [-2.3, 3.5, 7.2],
    [0, 0.8, 0],
  ],
  plain: [
    [2.8, 4.2, 7.5],
    [2.2, 4.5, 7.3],
    [0, 0.6, 0],
  ],
  question: [
    [9, 8, 12.5],
    [8.5, 7.5, 12],
    [0, -0.5, 0],
  ],
  clarity: [
    [-3.4, 2.5, 5.4],
    [3.1, 2.8, 5.5],
    [0, 0.25, 0],
  ],
  answer: [
    [3.5, 4.4, 8.2],
    [3.5, 4.2, 8],
    [2, -0.2, 0],
  ],
};

export function makeQuestionState(plan, direction) {
  if (
    plan.fps !== 30 ||
    plan.width !== 1080 ||
    plan.height !== 1920 ||
    !Number.isInteger(plan.duration_frames)
  )
    throw Error("Question film requires 1080x1920 at 30fps");
  const shots = plan.shots.map((s) => ({ ...s, d: direction.shots[s.id] }));
  if (
    !shots.length ||
    shots[0].start_frame !== 0 ||
    shots.at(-1).end_frame !== plan.duration_frames
  )
    throw Error("Incomplete shot coverage");
  let last = -1;
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i],
      order = MODES.indexOf(s.d?.mode);
    if (order <= last || order < 0)
      throw Error("Ribbon modes must be unique and causally ordered");
    last = order;
    if (
      !Number.isInteger(s.start_frame) ||
      !Number.isInteger(s.end_frame) ||
      s.end_frame <= s.start_frame ||
      (i && shots[i - 1].end_frame !== s.start_frame)
    )
      throw Error("Shots must partition frame clock");
  }
  const at = (mode) => {
    const s = shots.find((s) => s.d.mode === mode);
    if (!s) throw Error("Missing ribbon anchor: " + mode);
    return s.start_frame;
  };
  for (const mode of MODES) at(mode);
  return (frame) => {
    if (!Number.isFinite(frame)) throw Error("Frame must be finite");
    const f = Math.max(
      0,
      Math.min(plan.duration_frames - 1, Math.round(frame)),
    );
    const s = shots.find((s) => f >= s.start_frame && f < s.end_frame),
      mode = s.d.mode;
    const progress = ease(
      (f - s.start_frame) /
        (mode === "answer" ? 24 : Math.max(1, s.end_frame - s.start_frame - 1)),
    );
    const [from, to, target] = CAMERAS[mode];
    const unroll = ease(
      (f - at("reset")) / Math.max(1, at("question") - at("reset")),
    );
    const compliment = ease(
      (f - at("compliment")) / Math.max(1, at("apology") - at("compliment")),
    );
    const apology = ease(
      (f - at("apology")) / Math.max(1, at("approach") - at("apology")),
    );
    const send = ease(
      (f - at("send")) / Math.max(1, at("missing") - at("send")),
    );
    const travel = ease(
      (f - at("clarity")) / Math.max(1, at("answer") - at("clarity")),
    );
    return {
      frame: f,
      shot_id: s.id,
      mode,
      progress,
      camera: from.map((x, i) => x + (to[i] - x) * progress),
      look_at: mode === "clarity" ? [-2.75 + 5.5 * travel, 0.2, 0] : target,
      unroll,
      opening_wrap: 0.68 + 0.32 * ease(f / 24),
      compliment,
      apology,
      send,
      travel,
      heading: s.d.heading || "",
      hide_captions: !!s.d.hide_captions,
      disclosure: f < at("approach"),
      end_context: f >= at("clarity"),
      core_scale: 1 - 0.88 * Math.max(compliment, apology) * (1 - unroll),
      knot_shift: Math.sin(send * Math.PI) * 0.35,
    };
  };
}

/** Returns the two edges of one ribbon section. Shape morphs from coils to flat bridge. */
export function ribbonSection(u, unroll, variant = 0) {
  if (
    ![u, unroll, variant].every(Number.isFinite) ||
    u < 0 ||
    u > 1 ||
    unroll < 0 ||
    unroll > 1 ||
    ![0, 1, 2].includes(variant)
  )
    throw Error("Invalid ribbon parameter");
  const a = u * Math.PI * (variant === 0 ? 3.7 : 4.7) + variant * 1.9;
  const radius = variant === 0 ? 1.05 : 1.27 + variant * 0.12;
  const x = (1 - unroll) * Math.cos(a) * radius + unroll * (u - 0.5) * 5.5;
  const y =
    (1 - unroll) *
      (1.75 +
        Math.sin(a * (variant === 0 ? 1 : 2)) *
          radius *
          (variant === 0 ? 1 : 0.7)) +
    unroll * (0.64 + 0.2 * Math.sin(Math.PI * u));
  const z =
    (1 - unroll) * ((u - 0.5) * 1.2 + variant * 0.07) +
    unroll * (variant === 0 ? 0 : variant === 1 ? -0.49 : 0.49);
  const roll = (1 - unroll) * a;
  const side = [
    Math.cos(roll) * (1 - unroll),
    Math.sin(roll) * (1 - unroll),
    unroll,
  ];
  const length = Math.hypot(...side) || 1;
  return { center: [x, y, z], side: side.map((v) => v / length) };
}

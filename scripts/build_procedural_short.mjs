#!/usr/bin/env node
/** Build a measured procedural film from authored direction; no image/model calls. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { projectFile, assetUrl } from "./lib/cinematic_build.mjs";
import { makeStoryState } from "./lib/procedural_story_state.mjs";
const repository = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const project = path.resolve(
  process.argv[2] || "videos/biznex-the-yes-machine",
);
const python = path.join(
  repository,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const verified = spawnSync(
  python,
  [
    path.join(repository, "scripts/compile_edit_plan.py"),
    path.join(project, "EDIT_PLAN.json"),
    "--check",
  ],
  { encoding: "utf8", timeout: 30000 },
);
if (verified.error || verified.status !== 0)
  throw Error(
    "Edit plan is invalid or stale; run its preparation/compile stage",
  );
const read = (name) =>
  JSON.parse(fs.readFileSync(projectFile(project, name), "utf8"));
const hash = (file) =>
  createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const plan = read("EDIT_PLAN.compiled.json"),
  direction = read("DIRECTION.json"),
  world = read("assets/world.json"),
  mix = read("AUDIO_MIX.json");
makeStoryState(plan, direction);
if (world.schema_version !== 1 || world.runtime?.three_version !== "0.187.0")
  throw Error("Unsupported procedural world version");
for (const value of Object.values(world.geometry)) {
  if (!Number.isFinite(value) || value <= 0 || value > 100)
    throw Error("Invalid/bounds-exceeding geometry parameter");
}
if (world.geometry.gate_count !== 3)
  throw Error("This authored mechanical world requires three question gates");
const master = direction.audio_master || "assets/audio/master.wav";
if (
  mix.master_sha256 !== hash(projectFile(project, master)) ||
  mix.compiled_plan_sha256 !==
    hash(projectFile(project, "EDIT_PLAN.compiled.json")) ||
  Math.abs(mix.duration_seconds - plan.duration_seconds) > 1 / 48000
)
  throw Error("Audio mix is stale or belongs to a different edit");
const sourceInputs = [
  "assets/world.json",
  "assets/vendor/three.module.js",
  "assets/vendor/three.core.js",
  "assets/vendor/THREE-LICENSE.txt",
  "assets/vendor/gsap.min.js",
  "assets/fonts/Montserrat.ttf",
  "assets/fonts/Montserrat-OFL.txt",
];
for (const name of sourceInputs) projectFile(project, name);
const expectedThree = {
  "assets/vendor/three.module.js":
    "104f56145899722094556490d787aae0617cc2fc3382f31df02d724ea1aee341",
  "assets/vendor/three.core.js":
    "613e370f76638fdef83926642bf256dc9615684922de1ce1f63a8583e5d78578",
};
for (const [name, digest] of Object.entries(expectedThree))
  if (hash(projectFile(project, name)) !== digest)
    throw Error("Pinned Three.js vendor bytes differ");
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const payload = (value) => JSON.stringify(value).replaceAll("<", "\\u003c");
const captions = plan.captions
  .map(
    (c) =>
      `<div id="${escape(c.id)}" class="caption"><span class="caption-inner">${c.words.map((w) => `<span data-word="${w.index}">${escape(w.text)}</span>`).join(" ")}</span></div>`,
  )
  .join("\n");
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920"><title>${escape(direction.title)}</title><link rel="stylesheet" href="cinematic.css"><script src="assets/vendor/gsap.min.js"></script></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="${plan.duration_seconds.toFixed(6)}" data-width="1080" data-height="1920" data-fps="30"><canvas id="machine-canvas" data-layout-ignore></canvas><div class="top-scrim" data-layout-ignore></div><div id="disclosure" class="disclosure">Fictional story · synthetic voice</div><div id="heading" class="heading"></div>${captions}<div id="end-context" class="end-context"><b>${escape(direction.brand || "BizNex Stories")}</b>${escape(direction.context || "Atomy · independent educational community")}<small>Learn first. Decide for yourself.</small></div><audio id="master-audio" class="clip" src="${escape(assetUrl(project, master))}" data-start="0" data-duration="${plan.duration_seconds.toFixed(6)}" data-track-index="5" data-volume="1"></audio></div><script>window.PROCEDURAL_PLAN=${payload(plan)};window.PROCEDURAL_DIRECTION=${payload(direction)};window.PROCEDURAL_WORLD=${payload(world)};</script><script type="module" src="cinematic.js"></script></body></html>`;
for (const name of ["cinematic.css", "cinematic.js"])
  fs.copyFileSync(
    path.join(repository, "scripts/templates/procedural", name),
    path.join(project, name),
  );
for (const name of ["procedural_story_state.mjs", "cinematic_primitives.js"])
  fs.copyFileSync(
    path.join(repository, "scripts/lib", name),
    path.join(project, "assets/vendor", name),
  );
fs.writeFileSync(path.join(project, "index.html"), html, "utf8");
const names = [
  "index.html",
  "cinematic.css",
  "cinematic.js",
  "DIRECTION.json",
  "EDIT_PLAN.compiled.json",
  "AUDIO_MIX.json",
  master,
  "assets/vendor/procedural_story_state.mjs",
  "assets/vendor/cinematic_primitives.js",
  ...sourceInputs,
];
const files = Object.fromEntries(
  names.map((name) => [name, hash(projectFile(project, name))]),
);
fs.writeFileSync(
  path.join(project, "CINEMATIC_BUILD.json"),
  JSON.stringify(
    {
      schema_version: 1,
      project_id: plan.project_id,
      duration_frames: plan.duration_frames,
      fps: plan.fps,
      files,
      renderer: "original-procedural-three-r187",
      rendered: false,
      uses_image_model: false,
      uses_video_model: false,
    },
    null,
    2,
  ) + "\n",
);
console.log(
  `Built ${plan.project_id}: ${plan.shots.length} measured shots, ${plan.duration_frames} frames; no image/model generation.`,
);

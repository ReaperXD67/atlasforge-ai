"use strict";

const element = (id) => document.getElementById(id);
const audio = element("audio");
const scrub = element("scrub");
const canvas = element("waveform");
const waveHint = element("wave-hint");
const timeDisplay = element("time-display").children;
const cueList = element("cue-list");
const pasteDialog = element("paste-dialog");
const rowViews = new Map();
let cues = [];
let nextId = 1;
let selectedId = null;
let audioUrl = "";
let exportName = "lyrics";
let peaks = [];
let playableCues = [];
let currentCue = null;
let frame = 0;

const duration = () => Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : null;

function createCue(text, start = null, end = null, section = "") {
  return { id: nextId++, text, start, end, section };
}

function notify(message, error = false) {
  const feedback = element("feedback");
  feedback.textContent = message;
  feedback.classList.toggle("is-error", error);
}

function clock(seconds, precision = 3) {
  const unit = 10 ** precision;
  const ticks = Math.round(seconds * unit);
  const mins = String(Math.floor(ticks / (60 * unit))).padStart(2, "0");
  const secs = String(Math.floor(ticks / unit) % 60).padStart(2, "0");
  return `${mins}:${secs}.${String(ticks % unit).padStart(precision, "0")}`;
}

function parseUntimed(text) {
  let section = "";
  const result = [];
  for (const rawLine of text.split(/\r\n?|\n/u)) {
    const line = rawLine.trim();
    if (!line) continue;
    const heading = line.match(/^(?:\[([^\[\]]+)\]|【([^【】]+)】)$/u);
    if (heading) section = (heading[1] ?? heading[2]).trim();
    else result.push(createCue(line, null, null, section));
  }
  return result;
}

function readTimestamp(value, label, row) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
  throw new Error(`Cue ${row} has an invalid ${label}. Use seconds as a number.`);
}

function parseCueJson(text) {
  const data = JSON.parse(text);
  const draft = data?.status === "needs_review" && Array.isArray(data.draft_cues);
  const entries = Array.isArray(data) ? data : draft ? data.draft_cues : data?.cues;
  if (!Array.isArray(entries)) throw new Error("Choose a JSON cue array or an object with a cues array.");
  const cues = entries.map((entry, index) => {
    const row = index + 1;
    if (typeof entry?.text !== "string") throw new Error(`Cue ${row} is missing lyric text.`);
    if (entry.section != null && typeof entry.section !== "string") throw new Error(`Cue ${row} has an invalid section.`);
    return createCue(entry.text, readTimestamp(entry.start, "start", row), readTimestamp(entry.end, "end", row), entry.section ?? "");
  });
  return { cues, draft };
}

function parseLrc(text) {
  const result = [];
  const offset = Number(text.match(/^\s*\[offset:\s*([+-]?\d+)\]/imu)?.[1] ?? 0) / 1000;
  for (const rawLine of text.split(/\r\n?|\n/u)) {
    const line = rawLine.trim();
    if (!line) continue;
    const leading = line.match(/^(?:\[\d+:[0-5]\d(?:[.:]\d{1,3})?\])+/u)?.[0];
    if (!leading) {
      if (!line.startsWith("[")) result.push(createCue(line));
      continue;
    }
    const lyric = line.slice(leading.length).trim();
    if (!lyric) continue;
    for (const [, minutes, seconds, fraction] of leading.matchAll(/\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]/gu)) {
      const time = Number(minutes) * 60 + Number(seconds) + Number(fraction?.padEnd(3, "0") ?? 0) / 1000 + offset;
      result.push(createCue(lyric, Math.max(0, time)));
    }
  }
  return result.sort((left, right) => (left.start ?? Infinity) - (right.start ?? Infinity));
}

function validateCues() {
  const trackEnd = duration();
  const ordered = cues.filter((cue) => Number.isFinite(cue.start) && cue.start >= 0).sort((left, right) => left.start - right.start);
  const outcomes = new Map(cues.map((cue) => [cue.id, { error: cue.text.trim() ? "Set a start time." : "Enter the lyric text." }]));
  const ready = [];
  for (let index = 0; index < ordered.length; index++) {
    const cue = ordered[index];
    const next = ordered[index + 1];
    const end = cue.end ?? next?.start ?? trackEnd;
    let error = "";
    if (!cue.text.trim()) error = "Enter the lyric text.";
    else if (end === null) error = "Set an end time or load the recording.";
    else if (end <= cue.start) error = "End must be after start. Check for duplicate starts.";
    else if (next && end > next.start) error = "This cue overlaps the next start.";
    else if (trackEnd !== null && end > trackEnd) error = "This cue ends after the recording.";
    outcomes.set(cue.id, { error, end });
    if (!error) ready.push({ id: cue.id, text: cue.text, start: cue.start, end, section: cue.section });
  }
  return { outcomes, ready };
}

function updateTransport() {
  const trackEnd = duration();
  const ready = trackEnd !== null;
  const playing = ready && !audio.paused && !audio.ended;
  element("play").disabled = !ready;
  element("play").setAttribute("aria-label", playing ? "Pause recording" : "Play recording");
  element("play").firstElementChild.textContent = playing ? "Ⅱ" : "▶";
  element("speed").disabled = !ready;
  element("stamp").disabled = !ready || selectedId === null;
  scrub.disabled = !ready;
  scrub.max = trackEnd ?? 1;
  timeDisplay[1].textContent = `/ ${ready ? clock(trackEnd) : "--:--.---"}`;
}

function showPlayhead() {
  const now = audio.currentTime;
  timeDisplay[0].textContent = clock(now);
  element("review-time").textContent = clock(now);
  scrub.value = now;
  const active = playableCues.find((cue) => cue.start <= now && now < cue.end) ?? null;
  if (active !== currentCue) {
    if (currentCue) rowViews.get(currentCue.id)?.row.classList.remove("is-active");
    if (active) rowViews.get(active.id)?.row.classList.add("is-active");
    element("preview-section").textContent = active?.section ?? "";
    element("preview-text").textContent = active?.text ?? "No cue at the playhead";
    element("monitor").classList.toggle("is-empty", !active);
    currentCue = active;
  }
  drawWaveform();
}

function refreshCues() {
  const { outcomes, ready } = validateCues();
  playableCues = ready;
  for (const cue of cues) {
    const view = rowViews.get(cue.id);
    const { error, end } = outcomes.get(cue.id);
    const selected = cue.id === selectedId;
    view.row.classList.toggle("is-selected", selected);
    view.select.setAttribute("aria-pressed", String(selected));
    view.seek.disabled = duration() === null || cue.start === null || cue.start < 0 || cue.start >= duration();
    view.start.setAttribute("aria-invalid", String(cue.start === null || cue.start < 0));
    view.end.setAttribute("aria-invalid", String(Boolean(error) && Number.isFinite(cue.start) && cue.text.trim() !== ""));
    view.end.placeholder = Number.isFinite(end) && cue.end === null ? String(Number(end.toFixed(3))) : "Auto";
    view.problem.textContent = error;
    view.problem.hidden = !error;
  }
  const count = cues.length;
  element("cue-count").textContent = count ? `${ready.length} of ${count} ready` : "No cues";
  element("cue-columns").hidden = !count;
  element("cue-footer").hidden = !count;
  element("empty-cues").hidden = Boolean(count);
  element("export-json").disabled = !count;
  element("export-lrc").disabled = !count;
  updateTransport();
  showPlayhead();
}

function chooseCue(id, scroll = false) {
  selectedId = id;
  refreshCues();
  if (scroll) rowViews.get(id)?.row.scrollIntoView({ block: "nearest" });
}

function makeButton(text, label, handler, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = text;
  button.setAttribute("aria-label", label);
  button.title = label;
  button.addEventListener("click", handler);
  return button;
}

function makeInput(cue, property, type, label, className = "") {
  const input = document.createElement(type === "textarea" ? "textarea" : "input");
  if (type === "textarea") input.rows = 1;
  else input.type = type;
  input.className = `cue-input ${className}`;
  input.setAttribute("aria-label", label);
  input.value = cue[property] ?? "";
  if (type === "number") {
    input.inputMode = "decimal";
    input.min = 0;
    input.step = "0.001";
  }
  input.addEventListener("input", () => {
    cue[property] = type === "number" ? (Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null) : input.value;
    refreshCues();
  });
  return input;
}

function numberField(input, title) {
  const field = document.createElement("label");
  const label = document.createElement("span");
  label.className = "cue-field-label";
  label.textContent = title;
  field.append(label, input);
  return field;
}

function renderCues() {
  currentCue = null;
  element("monitor").classList.add("is-empty");
  element("preview-section").textContent = "";
  element("preview-text").textContent = "No cue at the playhead";
  rowViews.clear();
  const rows = cues.map((cue, index) => {
    const position = index + 1;
    const row = document.createElement("li");
    row.className = "cue-row";
    const copy = document.createElement("div");
    copy.className = "cue-copy";
    const select = makeButton(String(position).padStart(2, "0"), `Select cue ${position}`, () => chooseCue(cue.id), "cue-select");
    const text = makeInput(cue, "text", "textarea", `Lyric ${position}`, "cue-text");
    text.placeholder = "Lyric line";
    const section = makeInput(cue, "section", "text", `Section ${position}`, "cue-section");
    section.placeholder = "Add section";
    copy.append(select, text, section);
    const start = makeInput(cue, "start", "number", `Start ${position} in seconds`, "cue-time");
    start.placeholder = "Unset";
    const end = makeInput(cue, "end", "number", `End ${position} in seconds`, "cue-time");
    const actions = document.createElement("div");
    actions.className = "cue-actions";
    const seek = makeButton("↪", `Seek to cue ${position}`, () => {
      audio.currentTime = cue.start;
      chooseCue(cue.id);
    });
    const remove = makeButton("×", `Remove cue ${position}`, () => {
      cues.splice(index, 1);
      if (selectedId === cue.id) selectedId = (cues[index] ?? cues[index - 1])?.id ?? null;
      renderCues();
      if (selectedId !== null) rowViews.get(selectedId)?.select.focus();
      else element("add-cue").focus();
    });
    actions.append(seek, remove);
    const problem = document.createElement("p");
    problem.id = `cue-problem-${cue.id}`;
    problem.className = "cue-problem";
    start.setAttribute("aria-describedby", problem.id);
    end.setAttribute("aria-describedby", problem.id);
    row.append(copy, numberField(start, "Start (s)"), numberField(end, "End (s)"), actions, problem);
    rowViews.set(cue.id, { row, select, start, end, seek, problem, text });
    return row;
  });
  cueList.replaceChildren(...rows);
  refreshCues();
}

function replaceCues(replacement, draft = false) {
  if (!replacement.length) throw new Error("No lyric lines found.");
  cues = replacement;
  selectedId = cues[0].id;
  element("draft-note").hidden = !draft;
  renderCues();
  notify(`Loaded ${cues.length} lyric ${cues.length === 1 ? "line" : "lines"}${draft ? " for review" : ""}.`);
}

function stampSelected() {
  if (duration() === null || selectedId === null || audio.currentTime >= duration()) return;
  const index = cues.findIndex((cue) => cue.id === selectedId);
  const cue = cues[index];
  const start = Number(audio.currentTime.toFixed(3));
  if (start >= duration()) return;
  cue.start = start;
  rowViews.get(cue.id).start.value = start;
  chooseCue(cues[index + 1]?.id ?? null, true);
  notify(`Cue ${index + 1} starts at ${clock(start)}.${selectedId === null ? " Last line stamped." : ""}`);
}

function drawWaveform() {
  const { width, height } = canvas;
  const ctx = canvas.getContext("2d");
  const trackEnd = duration();
  const ratio = trackEnd ? audio.currentTime / trackEnd : 0;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#3b2e26";
  const pixel = window.devicePixelRatio || 1;
  for (let i = 1; i < 16; i++) ctx.fillRect(i * width / 16, 0, pixel, height);
  const space = width / peaks.length;
  for (let i = 0; i < peaks.length; i++) {
    const bar = Math.max(pixel, peaks[i] * height * .85);
    ctx.fillStyle = i * space < width * ratio ? "#efb488" : "#8d6750";
    ctx.fillRect(i * space, (height - bar) / 2, Math.max(pixel, space * .64), bar);
  }
  if (trackEnd) {
    ctx.fillStyle = "#ffdbb9";
    ctx.fillRect(Math.min(width - pixel, width * ratio), 0, pixel, height);
  }
}

async function analyzeWaveform(file, url) {
  if (!window.AudioContext || file.size > 120 * 1024 ** 2) {
    waveHint.textContent = "Waveform preview unavailable";
    return;
  }
  let context;
  try {
    context = new AudioContext();
    const decoded = await context.decodeAudioData(await file.arrayBuffer());
    if (url !== audioUrl) return;
    const samples = decoded.getChannelData(0);
    const peakCount = 180;
    const next = Array.from({ length: peakCount }, (_, index) => {
      const start = Math.floor(index * samples.length / peakCount);
      const end = Math.floor((index + 1) * samples.length / peakCount);
      const stride = Math.max(1, Math.floor((end - start) / 2000));
      let peak = 0;
      for (let sample = start; sample < end; sample += stride) peak = Math.max(peak, Math.abs(samples[sample]));
      return Math.min(peak, 1);
    });
    peaks = next;
    waveHint.hidden = true;
    drawWaveform();
  } catch {
    if (url === audioUrl) waveHint.textContent = "Waveform preview unavailable";
  } finally {
    if (context) await context.close();
  }
}

function animatePlayhead() {
  showPlayhead();
  frame = audio.paused || audio.ended ? 0 : requestAnimationFrame(animatePlayhead);
}

async function togglePlaying() {
  if (duration() === null) return;
  if (audio.paused) {
    try { await audio.play(); }
    catch { notify("Playback is unavailable. Load an audio file your browser supports.", true); }
  } else audio.pause();
}

function exportCues(type) {
  const { ready, outcomes } = validateCues();
  if (ready.length !== cues.length) {
    const index = cues.findIndex((cue) => outcomes.get(cue.id).error);
    chooseCue(cues[index].id, true);
    rowViews.get(cues[index].id).select.focus();
    notify(`Cue ${index + 1} needs review. ${outcomes.get(cues[index].id).error}`, true);
    return;
  }
  const items = ready.map(({ text, start, end, section }) => ({ text, start, end, section }));
  if (type === "lrc") {
    for (let index = 1; index < items.length; index++) {
      if (clock(items[index - 1].start) === clock(items[index].start)) {
        notify("Two starts are closer than one millisecond. Increase their spacing for LRC export.", true);
        return;
      }
    }
  }
  const data = type === "json"
    ? JSON.stringify(items, null, 2)
    : items.map(({ text, start }) => `[${clock(start)}]${text.replace(/\r?\n/gu, " ")}`).join("\n");
  const blob = new Blob([`${data}\n`], { type: type === "json" ? "application/json" : "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const download = document.createElement("a");
  download.href = url;
  download.download = `${exportName}.${type}`;
  download.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  notify(`Exported ${items.length} ${type.toUpperCase()} cues.`);
}

element("open-audio").addEventListener("click", () => element("audio-file").click());
element("open-cues").addEventListener("click", () => element("cue-file").click());
element("audio-file").addEventListener("change", ({ target }) => {
  const file = target.files[0];
  target.value = "";
  if (!file) return;
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = URL.createObjectURL(file);
  exportName = file.name.replace(/\.[^.]+$/u, "") || "lyrics";
  peaks = [];
  waveHint.textContent = "Reading audio waveform…";
  waveHint.hidden = false;
  element("track-name").textContent = file.name;
  audio.src = audioUrl;
  updateTransport();
  showPlayhead();
  void analyzeWaveform(file, audioUrl);
});
element("cue-file").addEventListener("change", async ({ target }) => {
  const file = target.files[0];
  target.value = "";
  if (!file) return;
  try {
    const data = (await file.text()).replace(/^\uFEFF/u, "");
    const parsed = file.name.toLowerCase().endsWith(".lrc") ? { cues: parseLrc(data), draft: false } : parseCueJson(data);
    replaceCues(parsed.cues, parsed.draft);
    if (!audioUrl) exportName = file.name.replace(/\.[^.]+$/u, "") || "lyrics";
  } catch (error) { notify(error.message, true); }
});

element("open-paste").addEventListener("click", () => {
  element("commit-paste").textContent = cues.length ? "Replace cues" : "Add lyrics";
  pasteDialog.showModal();
});
element("cancel-paste").addEventListener("click", () => pasteDialog.close());
element("paste-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const field = element("pasted-lyrics");
  const replacement = parseUntimed(field.value);
  if (!replacement.length) {
    field.setCustomValidity("Paste at least one lyric line.");
    field.reportValidity();
    return;
  }
  replaceCues(replacement);
  field.value = "";
  pasteDialog.close();
});
element("pasted-lyrics").addEventListener("input", ({ target }) => target.setCustomValidity(""));
element("add-cue").addEventListener("click", () => {
  const position = selectedId === null ? cues.length : cues.findIndex((cue) => cue.id === selectedId) + 1;
  const cue = createCue("", null, null, cues[position - 1]?.section ?? "");
  cues.splice(position, 0, cue);
  selectedId = cue.id;
  renderCues();
  rowViews.get(cue.id).text.focus();
});

element("play").addEventListener("click", togglePlaying);
element("stamp").addEventListener("click", stampSelected);
element("speed").addEventListener("change", ({ target }) => { audio.playbackRate = Number(target.value); });
element("export-json").addEventListener("click", () => exportCues("json"));
element("export-lrc").addEventListener("click", () => exportCues("lrc"));
scrub.addEventListener("input", () => {
  audio.currentTime = scrub.valueAsNumber;
  showPlayhead();
});
audio.addEventListener("loadedmetadata", () => {
  audio.playbackRate = Number(element("speed").value);
  refreshCues();
  notify(`Audio ready. Duration ${clock(duration())}.`);
});
audio.addEventListener("error", () => {
  refreshCues();
  notify("This recording could not open. Try a WAV or MP3 file.", true);
});
audio.addEventListener("timeupdate", showPlayhead);
audio.addEventListener("playing", () => {
  updateTransport();
  if (!frame) animatePlayhead();
});
for (const event of ["pause", "ended"]) audio.addEventListener(event, updateTransport);

document.addEventListener("keydown", (event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.repeat || pasteDialog.open) return;
  if (event.target.closest?.("input, textarea, select, [contenteditable]")) return;
  if (event.key.toLowerCase() === "s" && !element("stamp").disabled) {
    event.preventDefault();
    stampSelected();
  }
});

new ResizeObserver(() => {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(canvas.clientWidth * ratio);
  canvas.height = Math.round(canvas.clientHeight * ratio);
  drawWaveform();
}).observe(canvas);
renderCues();

import { readFileSync, writeFileSync } from "node:fs";

const path = new URL("../audio_meta.json", import.meta.url);
const meta = JSON.parse(readFileSync(path, "utf8"));
const lines = new Map([
  [1, "Quick quiz. Which Atomy Evening Care step comes third?"],
  [2, "Three... two... one..."],
  [3, "Peeling Gel. Did you get it right? Save this for tonight."],
]);

for (const voice of meta.voices ?? []) {
  const tokens = (lines.get(Number(voice.frame)) ?? "").split(/\s+/).filter(Boolean);
  const usable = Math.max(0.2, Number(voice.duration_s) - 0.12);
  const gap = tokens.length > 1 ? Math.min(0.03, usable / tokens.length / 5) : 0;
  const speech = usable - gap * Math.max(0, tokens.length - 1);
  const weights = tokens.map((token) => 0.5 + Math.sqrt(Math.max(1, token.replace(/[^\p{L}\p{N}]/gu, "").length)));
  const totalWeight = weights.reduce((sum, value) => sum + value, 0);
  let cursor = 0.04;
  voice.words = tokens.map((text, index) => {
    const start = cursor;
    const end = start + speech * (weights[index] / totalWeight);
    cursor = end + gap;
    return { id: `caption-word-${voice.frame}-${index}`, text, start: Number(start.toFixed(3)), end: Number(end.toFixed(3)) };
  });
}

writeFileSync(path, `${JSON.stringify(meta, null, 2)}\n`);

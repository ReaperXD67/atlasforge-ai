import { readFileSync, writeFileSync } from "node:fs";

const path = new URL("../audio_meta.json", import.meta.url);
const meta = JSON.parse(readFileSync(path, "utf8"));
const lines = new Map([
  [1, "Quick—what’s Atomy’s number-one product: HemoHIM, toothpaste, or skincare?"],
  [2, "Trick question. There are two correct answers."],
  [3, "By revenue, HemoHIM wins—more than three hundred billion won worldwide."],
  [4, "By units, Evening Care wins—nearly five million sets. Toothpaste Plus was right behind at four point six million."],
  [5, "Same brand. Two scoreboards. So… did you guess it?"],
]);

for (const voice of meta.voices ?? []) {
  const tokens = (lines.get(Number(voice.frame)) ?? "").split(/\s+/).filter(Boolean);
  const usable = Math.max(0.2, Number(voice.duration_s) - 0.14);
  const gap = tokens.length > 1 ? Math.min(0.035, usable / tokens.length / 5) : 0;
  const speech = usable - gap * Math.max(0, tokens.length - 1);
  const weights = tokens.map((token) => {
    const letters = token.replace(/[^\p{L}\p{N}]/gu, "").length;
    return 0.52 + Math.sqrt(Math.max(1, letters));
  });
  const totalWeight = weights.reduce((sum, value) => sum + value, 0);
  let cursor = 0.05;
  voice.words = tokens.map((text, index) => {
    const start = cursor;
    const end = start + speech * (weights[index] / totalWeight);
    cursor = end + gap;
    return {
      id: `caption-word-${voice.frame}-${index}`,
      text,
      start: Number(start.toFixed(3)),
      end: Number(end.toFixed(3)),
    };
  });
}

writeFileSync(path, `${JSON.stringify(meta, null, 2)}\n`);

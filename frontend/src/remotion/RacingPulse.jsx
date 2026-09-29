import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
const editThemes = {
  smoke_velocity: { accent: "#d8ff3f", secondary: "#ff6a35", rgb: "216,255,63", glow: "rgba(216,255,63,.55)", label: "SMOKE / VELOCITY" },
  neon_strobe: { accent: "#46e6ff", secondary: "#ff315d", rgb: "70,230,255", glow: "rgba(70,230,255,.55)", label: "NEON / STROBE" },
  luxury_noir: { accent: "#d6b47a", secondary: "#f4f0e9", rgb: "214,180,122", glow: "rgba(214,180,122,.38)", label: "LUXURY / NOIR" },
  flash_editorial: { accent: "#ff4c9c", secondary: "#ffffff", rgb: "255,76,156", glow: "rgba(255,76,156,.52)", label: "FLASH / EDITORIAL" },
  pragon_neon: { accent: "#2de7ff", secondary: "#ff315d", rgb: "45,231,255", glow: "rgba(45,231,255,.56)", label: "PRAGON / NEON" },
};

function previousEvent(values, time) {
  if (!values?.length) return null;
  let low = 0;
  let high = values.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (values[middle] <= time) low = middle;
    else high = middle - 1;
  }
  return values[low] <= time ? { index: low, time: values[low] } : null;
}

function nearestDistance(values, time) {
  if (!values?.length) return Number.POSITIVE_INFINITY;
  let low = 0;
  let high = values.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (values[middle] < time) low = middle + 1;
    else high = middle;
  }
  return Math.min(Math.abs((values[low] ?? values[values.length - 1]) - time), Math.abs((values[Math.max(0, low - 1)] ?? values[0]) - time));
}

function sampleEnergy(curve, time) {
  if (!curve?.length) return 0.55;
  let low = 0;
  let high = curve.length - 1;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (curve[middle].time_seconds < time) low = middle + 1;
    else high = middle;
  }
  const nextIndex = low;
  if (nextIndex <= 0) return curve[0].energy;
  const before = curve[nextIndex - 1];
  const after = curve[nextIndex];
  const progress = (time - before.time_seconds) / Math.max(0.001, after.time_seconds - before.time_seconds);
  return before.energy + (after.energy - before.energy) * progress;
}

function SpeedLines({ intensity, accent }) {
  return <AbsoluteFill style={{ overflow: "hidden", opacity: 0.25 + intensity * 0.36 }}>
    {Array.from({ length: 18 }, (_, index) => {
      const y = 90 + index * 54;
      const width = 220 + (index % 5) * 135;
      return <div key={index} style={{
        position: "absolute",
        top: y,
        right: -80 + (index % 3) * 40,
        width,
        height: index % 4 === 0 ? 3 : 1,
        background: index % 4 === 0 ? accent : "rgba(255,255,255,.75)",
        translate: `${-intensity * (120 + index * 9)}px 0`,
        boxShadow: index % 4 === 0 ? "0 0 28px rgba(255,91,39,.8)" : "none",
      }} />;
    })}
  </AbsoluteFill>;
}

function TrackMap({ pulse, accent }) {
  return <svg viewBox="0 0 820 430" style={{ position: "absolute", width: 860, right: 55, bottom: 52, opacity: 0.7 }}>
    <path d="M97 251 C39 179 122 90 252 105 C374 120 360 41 494 60 C672 84 732 159 677 243 C637 303 721 351 642 389 C548 434 484 349 371 373 C238 402 203 327 97 251Z" fill="none" stroke="rgba(255,255,255,.13)" strokeWidth="29" />
    <path d="M97 251 C39 179 122 90 252 105 C374 120 360 41 494 60 C672 84 732 159 677 243 C637 303 721 351 642 389 C548 434 484 349 371 373 C238 402 203 327 97 251Z" fill="none" stroke={accent} strokeWidth={4 + pulse * 4} strokeLinecap="round" pathLength="1" strokeDasharray={`${0.2 + pulse * 0.35} 1`} strokeDashoffset={-pulse * 0.42} style={{ filter: `drop-shadow(0 0 14px ${accent})` }} />
  </svg>;
}

export function RacingPulse({
  audioUrl = null,
  title = "SEPANG TRACK EXPERIENCE",
  brand = "PRAGON",
  beatMap = null,
  editStyle = "smoke_velocity",
  hookWords = "REDLINE, NO BRAKES, AFTER DARK, FULL SEND",
  visualDirection = "",
}) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;
  const bpm = beatMap?.bpm || 128;
  const trustedDownbeats = Boolean(beatMap?.downbeat_confidence >= 0.35 && beatMap?.downbeats_seconds?.length);
  const barAnchors = trustedDownbeats ? beatMap.downbeats_seconds : beatMap?.beats_seconds?.filter((_, index) => index % 4 === 0);
  const beatWindow = Math.min(0.18, (60 / bpm) * 0.36);
  const beatDistance = nearestDistance(beatMap?.beats_seconds, seconds);
  const downbeatDistance = nearestDistance(barAnchors, seconds);
  const fallbackPhase = ((seconds * bpm) / 60) % 1;
  const fallbackPulse = 1 - interpolate(fallbackPhase, [0, 0.16, 1], [0, 1, 0], clamp);
  const pulse = beatMap ? Math.pow(Math.max(0, 1 - beatDistance / beatWindow), 2) : fallbackPulse;
  const downbeatPulse = beatMap ? Math.pow(Math.max(0, 1 - downbeatDistance / (beatWindow * 1.25)), 2) : pulse;
  const energy = sampleEnergy(beatMap?.energy_curve, seconds);
  const section = beatMap?.sections?.find((item) => item.start_seconds <= seconds && item.end_seconds > seconds);
  const theme = editThemes[editStyle] || editThemes.smoke_velocity;
  const fallbackDownbeatIndex = Math.max(0, Math.floor((seconds * bpm / 60) / 4));
  const fallbackDownbeatTime = fallbackDownbeatIndex * (60 / bpm) * 4;
  const accentEvent = previousEvent(barAnchors, seconds) || { index: fallbackDownbeatIndex, time: fallbackDownbeatTime };
  const accentAge = Math.max(0, seconds - accentEvent.time);
  const impact = seconds > 1.1 && accentAge <= 0.14 ? interpolate(accentAge, [0, 0.035, 0.14], [0.82, 0.34, 0], clamp) : 0;
  const reveal = 0.28 + spring({ frame, fps, config: { damping: 180, stiffness: 120, mass: 0.8 } }) * 0.72;
  const outro = interpolate(frame, [durationInFrames - fps * 2, durationInFrames - 1], [1, 0], { ...clamp, easing: Easing.bezier(0.7, 0, 0.84, 0) });
  const progress = frame / Math.max(1, durationInFrames - 1);
  const speed = 0.22 + energy * 0.7 + pulse * 0.18;
  const closingBrand = seconds >= Math.max(0, durationInFrames / fps - 3.8);
  const spacedBrand = String(brand || "PRAGON").toUpperCase().split("").join(" ");

  return <AbsoluteFill style={{ background: "#070809", color: "#f4f0e9", fontFamily: "Barlow, Arial, sans-serif", overflow: "hidden", opacity: outro }}>
    {audioUrl ? <Audio src={audioUrl} /> : null}
    <AbsoluteFill style={{ scale: 1 + impact * 0.018, background: `radial-gradient(circle at 72% 52%, rgba(${theme.rgb},${0.12 + energy * 0.3}), transparent 28%), radial-gradient(circle at 18% 10%, rgba(255,255,255,.08), transparent 24%), linear-gradient(135deg,#08090a 0%,#121212 53%,#080706 100%)` }} />
    <AbsoluteFill style={{ scale: 1 + downbeatPulse * 0.012, opacity: 0.22 + pulse * 0.16, background: `repeating-linear-gradient(115deg, transparent 0 86px, ${theme.secondary}38 87px 90px, transparent 91px 178px)` }} />
    <SpeedLines intensity={speed + pulse * 0.25} accent={theme.accent} />
    <TrackMap pulse={progress} accent={theme.accent} />
    <div style={{ position: "absolute", left: 88, top: 78, width: 12, height: 160, background: theme.accent, scale: `1 ${reveal}`, transformOrigin: "top", boxShadow: `0 0 32px ${theme.glow}` }} />
    <div style={{ position: "absolute", left: 126, top: 78, opacity: reveal, translate: `${interpolate(reveal, [0, 1], [-42, 0])}px 0` }}>
      <div style={{ fontFamily: "Barlow Condensed, Arial, sans-serif", fontSize: 35, fontWeight: 900, letterSpacing: 10, color: theme.accent }}>{brand}</div>
      <div style={{ marginTop: 52, fontFamily: "Barlow Condensed, Arial, sans-serif", fontSize: 116, lineHeight: 0.84, fontWeight: 900, letterSpacing: -3, maxWidth: 1160 }}>{title}</div>
      <div style={{ marginTop: 42, display: "flex", gap: 18, alignItems: "center", fontSize: 24, letterSpacing: 4, color: "rgba(244,240,233,.72)" }}>
        <span>{section?.label?.toUpperCase() || "SONG MAP"}</span><span style={{ color: theme.accent }}>◆</span><span>{beatMap?.is_rhythmic ? trustedDownbeats ? "BAR-LOCKED" : "LYRIC PHASE PENDING" : "PHRASE FLOW"}</span><span style={{ color: theme.accent }}>◆</span><span>{Math.round(bpm)} BPM</span>
      </div>
    </div>
    {closingBrand ? <div style={{ position: "absolute", zIndex: 6, inset: 0, display: "grid", placeItems: "center", background: "radial-gradient(circle at 50% 66%, rgba(255,49,93,.17), transparent 24%), rgba(2,5,9,.78)" }}>
      <div style={{ position: "absolute", width: "72%", height: 2, top: "67%", background: `linear-gradient(90deg,transparent,${theme.accent},${theme.secondary},transparent)`, boxShadow: `0 0 26px ${theme.glow}` }} />
      <div style={{ position: "relative", fontFamily: "Barlow Condensed, Arial, sans-serif", fontSize: 218, lineHeight: 0.82, fontWeight: 900, letterSpacing: 25, color: "#f8f5ee", textShadow: `-9px 0 0 ${theme.accent}99, 9px 0 0 ${theme.secondary}88, 0 20px 70px rgba(0,0,0,.9)` }}>{spacedBrand}</div>
      <div style={{ position: "absolute", top: "61%", color: "rgba(247,245,238,.68)", fontSize: 23, letterSpacing: 9 }}>SEPANG / MALAYSIA / AFTER DARK</div>
    </div> : null}
    <div style={{ position: "absolute", left: 88, right: 88, bottom: 55, height: 2, background: "rgba(255,255,255,.15)" }}>
      <div style={{ width: `${progress * 100}%`, height: "100%", background: theme.accent, boxShadow: `0 0 14px ${theme.accent}` }} />
    </div>
    <div style={{ position: "absolute", left: 88, bottom: 73, fontFamily: "monospace", fontSize: 18, letterSpacing: 2, color: "rgba(255,255,255,.5)" }}>MASTER SYNC / {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(Math.floor(seconds % 60)).padStart(2, "0")} / ENERGY {Math.round(energy * 100)}</div>
    <div style={{ position: "absolute", right: 88, bottom: 73, maxWidth: 660, overflow: "hidden", color: "rgba(255,255,255,.44)", fontFamily: "monospace", fontSize: 15, letterSpacing: 1.8, textAlign: "right", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{theme.label} / {(visualDirection || "DIRECTOR BRIEF READY").toUpperCase()}</div>
  </AbsoluteFill>;
}

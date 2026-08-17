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

function SpeedLines({ intensity }) {
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
        background: index % 4 === 0 ? "#ff5b27" : "rgba(255,255,255,.75)",
        translate: `${-intensity * (120 + index * 9)}px 0`,
        boxShadow: index % 4 === 0 ? "0 0 28px rgba(255,91,39,.8)" : "none",
      }} />;
    })}
  </AbsoluteFill>;
}

function TrackMap({ pulse }) {
  return <svg viewBox="0 0 820 430" style={{ position: "absolute", width: 860, right: 55, bottom: 52, opacity: 0.7 }}>
    <path d="M97 251 C39 179 122 90 252 105 C374 120 360 41 494 60 C672 84 732 159 677 243 C637 303 721 351 642 389 C548 434 484 349 371 373 C238 402 203 327 97 251Z" fill="none" stroke="rgba(255,255,255,.13)" strokeWidth="29" />
    <path d="M97 251 C39 179 122 90 252 105 C374 120 360 41 494 60 C672 84 732 159 677 243 C637 303 721 351 642 389 C548 434 484 349 371 373 C238 402 203 327 97 251Z" fill="none" stroke="#f25c2a" strokeWidth={4 + pulse * 4} strokeLinecap="round" pathLength="1" strokeDasharray={`${0.2 + pulse * 0.35} 1`} strokeDashoffset={-pulse * 0.42} style={{ filter: "drop-shadow(0 0 14px rgba(242,92,42,.55))" }} />
  </svg>;
}

export function RacingPulse({
  audioUrl = null,
  title = "SEPANG TRACK EXPERIENCE",
  brand = "BOSSTON × PRAGON",
  bpm = 128,
}) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;
  const beatPhase = ((seconds * bpm) / 60) % 1;
  const pulse = 1 - interpolate(beatPhase, [0, 0.16, 1], [0, 1, 0], clamp);
  const reveal = spring({ frame, fps, config: { damping: 180, stiffness: 120, mass: 0.8 } });
  const outro = interpolate(frame, [durationInFrames - fps * 2, durationInFrames - 1], [1, 0], { ...clamp, easing: Easing.bezier(0.7, 0, 0.84, 0) });
  const progress = frame / Math.max(1, durationInFrames - 1);
  const speed = interpolate(Math.sin(seconds * 0.85), [-1, 1], [0.35, 0.95]);

  return <AbsoluteFill style={{ background: "#070809", color: "#f4f0e9", fontFamily: "DM Sans, Arial, sans-serif", overflow: "hidden", opacity: outro }}>
    {audioUrl ? <Audio src={audioUrl} /> : null}
    <AbsoluteFill style={{ background: "radial-gradient(circle at 72% 52%, rgba(144,31,8,.43), transparent 28%), radial-gradient(circle at 18% 10%, rgba(255,255,255,.08), transparent 24%), linear-gradient(135deg,#08090a 0%,#121212 53%,#080706 100%)" }} />
    <AbsoluteFill style={{ scale: 1 + pulse * 0.008, opacity: 0.25 + pulse * 0.1, background: "repeating-linear-gradient(115deg, transparent 0 86px, rgba(255,80,25,.24) 87px 90px, transparent 91px 178px)" }} />
    <SpeedLines intensity={speed + pulse * 0.25} />
    <TrackMap pulse={progress} />
    <div style={{ position: "absolute", left: 88, top: 78, width: 12, height: 160, background: "#ff5b27", scale: `1 ${reveal}`, transformOrigin: "top", boxShadow: "0 0 32px rgba(255,91,39,.45)" }} />
    <div style={{ position: "absolute", left: 126, top: 78, opacity: reveal, translate: `${interpolate(reveal, [0, 1], [-42, 0])}px 0` }}>
      <div style={{ fontSize: 29, fontWeight: 700, letterSpacing: 8, color: "#ff6c36" }}>{brand}</div>
      <div style={{ marginTop: 52, fontSize: 102, lineHeight: 0.87, fontWeight: 800, letterSpacing: -5, maxWidth: 1060 }}>{title}</div>
      <div style={{ marginTop: 42, display: "flex", gap: 18, alignItems: "center", fontSize: 24, letterSpacing: 4, color: "rgba(244,240,233,.72)" }}>
        <span>SONG LAUNCH</span><span style={{ color: "#ff5b27" }}>◆</span><span>RACE NIGHT</span><span style={{ color: "#ff5b27" }}>◆</span><span>{Math.round(bpm)} BPM</span>
      </div>
    </div>
    <div style={{ position: "absolute", left: 88, right: 88, bottom: 55, height: 2, background: "rgba(255,255,255,.15)" }}>
      <div style={{ width: `${progress * 100}%`, height: "100%", background: "#ff5b27", boxShadow: "0 0 14px #ff5b27" }} />
    </div>
    <div style={{ position: "absolute", left: 88, bottom: 73, fontFamily: "monospace", fontSize: 18, letterSpacing: 2, color: "rgba(255,255,255,.5)" }}>MASTER SYNC / {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(Math.floor(seconds % 60)).padStart(2, "0")}</div>
  </AbsoluteFill>;
}

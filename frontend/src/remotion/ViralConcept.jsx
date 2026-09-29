import { AbsoluteFill, Audio, Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

const palette = {
  ink: "#08090a",
  amber: "#ef8b3d",
  cream: "#f5efe6",
  muted: "#aaa49a",
};

function CatPerformance({ energy }) {
  const lean = interpolate(energy, [-1, 1], [-5, 5]);
  const lift = interpolate(Math.abs(energy), [0, 1], [0, -18]);
  return <div style={{ position: "absolute", left: "50%", top: "45%", width: 350, height: 480, transform: `translate(-50%, -50%) translateY(${lift}px) rotate(${lean}deg)` }}>
    <div style={{ position: "absolute", left: 80, top: 26, width: 190, height: 178, borderRadius: "48% 48% 44% 44%", background: "linear-gradient(145deg,#d6a16d,#7e4d2e)", boxShadow: "0 28px 90px rgba(0,0,0,.55)" }} />
    <div style={{ position: "absolute", left: 87, top: 0, width: 72, height: 92, background: "#bd7f4b", clipPath: "polygon(50% 0,100% 100%,0 82%)" }} />
    <div style={{ position: "absolute", right: 87, top: 0, width: 72, height: 92, background: "#bd7f4b", clipPath: "polygon(50% 0,100% 82%,0 100%)" }} />
    {[128, 204].map((left) => <div key={left} style={{ position: "absolute", left, top: 100, width: 18, height: 22, borderRadius: "50%", background: "#dff7a2", boxShadow: "0 0 20px rgba(210,255,126,.35)" }} />)}
    <div style={{ position: "absolute", left: 95, top: 170, width: 165, height: 234, borderRadius: "48% 48% 38% 38%", background: "linear-gradient(160deg,#c99059,#684027)" }} />
    <div style={{ position: "absolute", left: 83, top: 190, width: 45, height: 190, borderRadius: 30, background: "#a96d3e", transformOrigin: "top", transform: `rotate(${18 + energy * 24}deg)` }} />
    <div style={{ position: "absolute", right: 82, top: 190, width: 45, height: 190, borderRadius: 30, background: "#a96d3e", transformOrigin: "top", transform: `rotate(${-18 - energy * 24}deg)` }} />
    <div style={{ position: "absolute", right: 7, top: 250, width: 150, height: 42, borderRadius: 30, background: "#8b552f", transformOrigin: "left", transform: `rotate(${45 + energy * 16}deg)` }} />
  </div>;
}

function TalkingDuo({ energy }) {
  return <div style={{ position: "absolute", inset: "20% 7% 25%", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "center" }}>
    {[[-1, "A"], [1, "B"]].map(([direction, label], index) => <div key={label} style={{ aspectRatio: ".82", borderRadius: "46% 46% 38% 38%", background: index ? "linear-gradient(160deg,#b36f52,#4d2d29)" : "linear-gradient(160deg,#d9af83,#76513a)", border: "1px solid rgba(255,255,255,.16)", boxShadow: "0 40px 100px rgba(0,0,0,.55)", transform: `translateY(${(index ? -1 : 1) * energy * 6}px) rotate(${direction * 2}deg)`, position: "relative" }}>
      <div style={{ position: "absolute", top: "38%", left: "18%", right: "18%", display: "flex", justifyContent: "space-between" }}>{[1, 2].map((eye) => <span key={eye} style={{ width: 18, height: 16, borderRadius: "50%", background: "#151312" }} />)}</div>
      <div style={{ position: "absolute", top: "60%", left: "39%", width: "22%", height: 10 + Math.abs(energy) * 12, borderRadius: 20, background: "#351c1c" }} />
      <span style={{ position: "absolute", left: 18, bottom: 20, font: "600 16px DM Sans", color: "rgba(255,255,255,.7)" }}>SPEAKER {label}</span>
    </div>)}
  </div>;
}

function PhysicsSpectacle({ progress }) {
  return <div style={{ position: "absolute", inset: "17% 10% 23%", display: "flex", justifyContent: "center", alignItems: "end", perspective: 1200 }}>
    <div style={{ width: "76%", height: "84%", display: "grid", gridTemplateRows: "repeat(8, 1fr)", gap: 8, transform: `rotateX(${progress * 5}deg) rotateZ(${-progress * 5}deg) translateY(${progress * 90}px)` }}>
      {Array.from({ length: 8 }, (_, index) => <div key={index} style={{ background: `linear-gradient(90deg,#423d38 ${20 + index * 2}%,#aba095,#302c29)`, border: "1px solid rgba(255,255,255,.1)", boxShadow: "0 12px 24px rgba(0,0,0,.3)", transformOrigin: index % 2 ? "left" : "right", transform: `translateX(${progress * (index % 2 ? 1 : -1) * index * 6}px) rotateZ(${progress * (index % 2 ? 1 : -1) * index * 1.2}deg)` }} />)}
    </div>
    <div style={{ position: "absolute", left: "8%", right: "8%", bottom: -10, height: 180, borderRadius: "50%", background: "radial-gradient(ellipse,rgba(184,161,139,.45),transparent 66%)", filter: "blur(14px)", opacity: progress }} />
  </div>;
}

export function ViralConcept({ recipe, concept, audioUrl, bpm = 120, referenceUrl }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const framesPerBeat = Math.max(8, fps * 60 / bpm);
  const beatPhase = (frame % framesPerBeat) / framesPerBeat;
  const energy = Math.sin(beatPhase * Math.PI * 2);
  const reveal = spring({ frame, fps, config: { damping: 18, stiffness: 90 } });
  const collapse = interpolate(frame, [durationInFrames * .42, durationInFrames * .82], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const gridX = interpolate(frame, [0, durationInFrames], [0, -180]);
  return <AbsoluteFill style={{ background: palette.ink, color: palette.cream, overflow: "hidden", fontFamily: "DM Sans, sans-serif" }}>
    {audioUrl && <Audio src={audioUrl} volume={.9} />}
    {referenceUrl && <Img src={referenceUrl} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: .24, filter: "saturate(.75) contrast(1.12) blur(1px)", transform: `scale(${1.04 + reveal * .02})` }} />}
    <AbsoluteFill style={{ background: "radial-gradient(circle at 52% 34%,rgba(234,115,45,.14),transparent 30%),linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.78))" }} />
    <div style={{ position: "absolute", inset: 0, opacity: .24, backgroundImage: "linear-gradient(rgba(255,255,255,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.055) 1px,transparent 1px)", backgroundSize: "72px 72px", transform: `translateX(${gridX % 72}px)` }} />
    <div style={{ position: "absolute", top: 64, left: 54, right: 54, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 15, letterSpacing: ".16em" }}><span style={{ color: palette.amber, fontWeight: 700 }}>AI VIRAL LAB</span><span style={{ color: palette.muted }}>MOTION PREVIS · 9:16</span></div>
    {recipe === "beat_creature" && <CatPerformance energy={energy * reveal} />}
    {recipe === "talking_duo" && <TalkingDuo energy={energy * reveal} />}
    {recipe === "physics_spectacle" && <PhysicsSpectacle progress={collapse} />}
    <div style={{ position: "absolute", left: 54, right: 54, bottom: 78, transform: `translateY(${(1 - reveal) * 30}px)`, opacity: reveal }}>
      <div style={{ width: 54, height: 4, background: palette.amber, marginBottom: 18 }} />
      <div style={{ fontFamily: "Cormorant Garamond, serif", fontSize: 64, lineHeight: .92, letterSpacing: "-.035em", textTransform: "uppercase" }}>{concept || "Describe your impossible shot"}</div>
      <div style={{ marginTop: 18, color: palette.muted, fontSize: 17 }}>Identity lock · coherent motion · synthetic-media manifest</div>
    </div>
  </AbsoluteFill>;
}

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowSquareOut, Bell, CalendarBlank, CaretDown, CaretLeft, CaretRight, Check, CheckCircle, CircleNotch,
  ClosedCaptioning, Command, Desktop, DotsThree, Eye, FilmReel, FolderOpen,
  Image as ImageIcon, List, LockKey, MagnifyingGlassPlus, Microphone, Minus, MusicNotes,
  Pause, Play, Plus, Question, Queue, SlidersHorizontal, Sparkle, SpeakerHigh,
  StopCircle, UploadSimple, Warning, Waveform, X, YoutubeLogo,
} from "@phosphor-icons/react";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-600.css";
import "@fontsource/cormorant-garamond/latin-600.css";

const fallbackProfiles = [
  { id: "atomy-us-openrouter", name: "Atomy USA — Joining Guide", brand: "Atomy", region: "United States", duration_minutes: 7, text_provider: "openrouter", voice_provider: "chatterbox", fps: 60 },
  { id: "atomy-us-preview", name: "Atomy USA — Fast Preview", brand: "Atomy", region: "United States", duration_minutes: 2, text_provider: "openrouter", voice_provider: "chatterbox", fps: 60 },
  { id: "general-explainer", name: "General Explainer", brand: "", region: "Global", duration_minutes: 5, text_provider: "openrouter", voice_provider: "chatterbox", fps: 60 },
];

const RemotionPreview = lazy(() => import("./remotion/RemotionPreview"));
const ViralLab = lazy(() => import("./viral/ViralLab"));
const AIGenerationLab = lazy(() => import("./ai/AIGenerationLab"));

const initialScenes = [
  { id: 1, title: "How to Join Atomy USA", caption: "A clear, practical member-registration guide.", duration: 55, image: "/assets/scenes/city-waterfront.webp", source: "Pexels or generated still", motion: "Slow push-in", transition: "Crossfade" },
  { id: 2, title: "Before You Begin", caption: "Prepare a sponsor ID and accurate personal details.", duration: 88, image: "/assets/scenes/member-guidance.webp", source: "Pexels people", motion: "Gentle drift right", transition: "Crossfade" },
  { id: 3, title: "Understand the Products", caption: "Review official product information before deciding.", duration: 96, image: "/assets/scenes/product-education.webp", source: "Product still", motion: "Parallax push-in", transition: "Dip to black" },
  { id: 4, title: "Know the Model", caption: "Results vary; there are no guaranteed earnings.", duration: 94, image: "/assets/scenes/member-education.webp", source: "Education footage", motion: "Locked frame", transition: "Crossfade" },
  { id: 5, title: "Complete Registration", caption: "Use the official regional site and verify every field.", duration: 87, image: "/assets/scenes/registration.webp", source: "Pexels lifestyle", motion: "Slow push-in", transition: "Fade out" },
];

const sceneFallbackImages = initialScenes.map((scene) => scene.image);
const musicEditStyles = [
  { id: "pragon_neon", name: "Pragon neon", note: "Premium cyan/ember wordmark · vocal-locked brand resolve" },
  { id: "smoke_velocity", name: "Smoke + velocity", note: "Acid outline type · dense atmosphere · hard bass flashes" },
  { id: "neon_strobe", name: "Neon strobe", note: "Chromatic split type · electric color · sharp impact frames" },
  { id: "luxury_noir", name: "Luxury noir", note: "Black-label restraint · boxed type · precise highlights" },
  { id: "flash_editorial", name: "Flash editorial", note: "Fashion-camera flash · graphic stamps · off-register energy" },
];

const pragonLyrics = `[Intro]
[distorted electric guitar riff, kendang percussion, bright synth lead]
PRA-gon!
(Woah-oh-oh-oh)
Selamanya!
Satu! Berdua!

[Chorus]
[full band, driving pop-rock beat]
(Hey! Hey! Hey! Hey!)
PRA-gon! PRA-gon! PRA-gon! PRA-gon! PRA-gon! PRA-gon!

[Verse 1]
[bass and drums continue, palm-muted guitar]
Hidup berulang, hari yang sama
Bangun berjalan, ikut rentak lama (Woo!)
Jangan terkurung dalam putaran
Nikmati masa, terus ke hadapan

[Verse 2]
[female vocals enter]
Tak perlu tunggu, tak perlu susah
Langkah kita bebas, rasa semakin gah
Buka langkah bina semangat baru
Dengarkan janji, kita mara terus maju

[Verse 3]
[male vocals, synth pads]
Di bawah langit yang membentang luas
Kita melaju, takkan pernah batas
PRA-gon membakar semangat jiwa
Menuju puncak meraih semua

[Pre-Chorus]
[female vocals, building drum intensity]
Langkah kaki ini semakin pasti
Tak ada lagi yang bisa membenci
PRA-gon abadi di dalam sanubari
Kita berdiri tegak menantang hari

[Chorus]
[high energy, kendang fills]
PRA-gon! PRA-gon!
(Woo!)

[Guitar Solo]
[distorted lead guitar, rapid kendang rhythm]
(Yeah! Yeah!)

[Chorus]
[male vocals, pop-rock arrangement]
PRA-gon PA-du dentuman rasa
Membawa jiwa menembus angkasa
Meski badai datang menerjang kita
Hati ini tetap satu selamanya

[Outro]
[heavy guitar chords, synth lead]
Bukan sekadar mimpi kita realisasi
Satu frekuensi tanpa ada gengsi
Jalur kiri kanan kita tetap satu visi
Langkah mantap ini dia resolusi
Hidup berulang, hari yang sama
Jangan terkurung dalam putaran
Takkan pernah runtuh!
Selamanya! Selamanya!
Satu! Selamanya!
Satu! Berdua!
PRA-gon! PRA-gon! PRA-gon! PRA-gon! PRA-gon! PRA-gon!`;
const storyboardToScenes = (storyboard, runId) => storyboard.scenes.map((scene, position) => {
  const angle = scene.camera_angle?.toLowerCase() || "";
  const transition = scene.transition?.toLowerCase() || "";
  const searchTitle = titleCase(scene.visual_search_query || scene.environment || `Scene ${scene.index}`);
  const sourceLabel = {
    pexels_video: "Pexels matching clip",
    pixabay_video: "Pixabay matching clip",
    comfyui_wan22: "Wan 2.2 local AI clip",
    fal_wan_s2v: "Wan 2.2 recurring performer",
    openai_imagegen_outro: "Owned AI ember closing plate",
    veo: "Veo premium clip",
    minimax: "MiniMax premium clip",
    local_motion: scene.visual_mode === "information_card" ? "Local information card" : "Stable photo motion",
  }[scene.selected_video_provider] || titleCase(scene.selected_video_provider || "Local fallback");
  return {
    id: scene.index,
    title: position === 0 ? storyboard.title : searchTitle,
    caption: scene.narration,
    duration: Number(scene.duration_seconds) || 1,
    image: `/api/runs/${runId}/scenes/${scene.index}`,
    fallbackImage: sceneFallbackImages[position % sceneFallbackImages.length],
    source: sourceLabel,
    motion: angle.includes("locked") ? "Locked frame" : angle.includes("lateral") ? "Gentle drift right" : angle.includes("close") || angle.includes("overhead") ? "Parallax push-in" : "Slow push-in",
    transition: transition.includes("black") ? "Dip to black" : transition.includes("fade") ? "Fade out" : "Crossfade",
  };
});

const productionSteps = [
  { label: "Brief", stages: ["research"] },
  { label: "Script", stages: ["script", "storyboard"] },
  { label: "Voice", stages: ["narration", "sound_mix"] },
  { label: "Visuals", stages: ["images", "performer_direction", "performer_video", "premium_video", "local_video", "stock_video"] },
  { label: "Edit", stages: ["render", "finalize"] },
  { label: "Captions", stages: ["subtitles"] },
  { label: "Quality", stages: ["metadata", "quality_gate"] },
  { label: "Publish", stages: ["publish"] },
];

const formatClock = (seconds) => {
  const safe = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
};
const formatDuration = (seconds) => `00:${formatClock(seconds)}:00`;
const titleCase = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function BrandMark() {
  return <div className="brand-mark" aria-label="AtlasForge Studio"><FilmReel weight="duotone" aria-hidden="true" /><span>AtlasForge Studio</span><small>LOCAL-FIRST</small></div>;
}

function StatusDot({ ok, pending = false }) {
  return <span className={`status-dot ${ok ? "is-ok" : ""} ${pending ? "is-pending" : ""}`} aria-label={pending ? "checking" : ok ? "ready" : "needs setup"} />;
}

function StageRail({ stages = [], activeJob, published = false }) {
  const stageMap = useMemo(() => new Map(stages.map((stage) => [stage.stage, stage.status])), [stages]);
  const hasJob = Boolean(activeJob);
  return <nav className="stage-rail" aria-label="Production stages">{productionSteps.map((step, index) => {
    const statuses = step.stages.map((stage) => stageMap.get(stage)).filter(Boolean);
    const complete = step.label === "Publish" ? published : statuses.length > 0 && statuses.every((status) => status === "completed");
    const failed = statuses.some((status) => status === "failed");
    const running = statuses.some((status) => status === "running");
    const visualWorkspace = !hasJob && step.label === "Visuals";
    return <div className={`stage-step ${complete ? "is-complete" : ""} ${running || visualWorkspace ? "is-active" : ""} ${failed ? "is-failed" : ""}`} key={step.label}>
      <span className="stage-label">{step.label}</span><span className="stage-rule" />
      <span className="stage-node" aria-label={`${step.label}: ${complete ? "complete" : running ? "running" : failed ? "failed" : "pending"}`}>{complete ? <Check weight="bold" /> : failed ? <X weight="bold" /> : running ? <CircleNotch className="spin" /> : index + 1}</span>
    </div>;
  })}</nav>;
}

function ChapterRail({ scenes, selectedId, onSelect, activeTab, setActiveTab, onAddScene }) {
  let start = 0;
  return <aside className="chapter-panel panel-surface">
    <div className="panel-tabs" role="tablist" aria-label="Storyboard panel"><button className={activeTab === "chapters" ? "active" : ""} onClick={() => setActiveTab("chapters")} role="tab">Chapters</button><button className={activeTab === "assets" ? "active" : ""} onClick={() => setActiveTab("assets")} role="tab">Assets</button></div>
    {activeTab === "chapters" ? <div className="chapter-scroll">{scenes.map((scene) => {
      const sceneStart = start;
      start += scene.duration;
      return <button className={`chapter-card ${selectedId === scene.id ? "active" : ""}`} key={scene.id} onClick={() => onSelect(scene.id)}><span className="chapter-index">{scene.id}</span><span className="chapter-start">{formatClock(sceneStart)}</span><img src={scene.image} alt="" /><span className="chapter-copy"><strong>{scene.title}</strong><small>{formatClock(scene.duration)}</small></span><DotsThree weight="bold" aria-hidden="true" /></button>;
    })}</div> : <div className="asset-list">{[
      [FilmReel, "Matching scene clips", "Pexels Video first"],
      [ImageIcon, "Stable still fallbacks", "Supersampled, no camera shake"],
      [FolderOpen, "AI candidate quarantine", "Wan 2.2 via ComfyUI"],
      [MusicNotes, "Original ambient score", "Generated locally"],
      [ClosedCaptioning, "Timed captions", "Whisper alignment"],
    ].map(([Icon, title, detail]) => <div className="asset-row" key={title}><Icon weight="duotone" /><span><strong>{title}</strong><small>{detail}</small></span><CheckCircle weight="fill" className="ready-icon" /></div>)}</div>}
    <div className="panel-footer"><button className="secondary-button grow" onClick={onAddScene}><Plus /> Add scene</button><button className="icon-button" title="Open scene queue" aria-label="Open scene queue"><Queue /></button></div>
  </aside>;
}

function Preview({ scene, playing, setPlaying, playhead, setPlayhead, totalDuration, outputUrl }) {
  const videoRef = useRef(null);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !outputUrl) return;
    if (playing) video.play().catch(() => setPlaying(false));
    else video.pause();
  }, [playing, outputUrl, setPlaying]);
  useEffect(() => {
    const video = videoRef.current;
    if (video && Math.abs(video.currentTime - playhead) > 1) video.currentTime = playhead;
  }, [playhead]);
  const skip = (seconds) => {
    const next = Math.max(0, Math.min(totalDuration, playhead + seconds));
    setPlayhead(next);
    if (videoRef.current) videoRef.current.currentTime = next;
  };
  return <section className="preview-card panel-surface" aria-label="Video preview">
    <div className="preview-media">{outputUrl ? <video ref={videoRef} src={outputUrl} controls preload="metadata" poster={scene.image} onTimeUpdate={(event) => setPlayhead(event.currentTarget.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} /> : <>
      <AnimatePresence mode="wait"><motion.img key={scene.id} src={scene.image} onError={(event) => { event.currentTarget.src = scene.fallbackImage || initialScenes[0].image; }} alt={`Storyboard preview for ${scene.title}`} initial={{ opacity: 0.3, scale: 1.015 }} animate={{ opacity: 1, scale: playing ? 1.035 : 1 }} exit={{ opacity: 0.25 }} transition={{ duration: playing ? 8 : 0.35, ease: "easeOut" }} /></AnimatePresence>
      <div className="preview-shade" /><motion.div className="title-safe" key={`copy-${scene.id}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><h1>{scene.title}</h1><p>{scene.caption}</p></motion.div>
    </>}</div>
    <div className="transport"><span className="timecode"><strong>{formatClock(playhead)}</strong> / {formatClock(totalDuration)}</span><div className="transport-controls"><button onClick={() => skip(-10)} aria-label="Back 10 seconds" title="Back 10 seconds"><CaretLeft weight="bold" /></button><button className="transport-play" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause preview" : "Play preview"}>{playing ? <Pause weight="fill" /> : <Play weight="fill" />}</button><button onClick={() => skip(10)} aria-label="Forward 10 seconds" title="Forward 10 seconds"><CaretRight weight="bold" /></button></div><div className="transport-tools"><button title="Preview display" aria-label="Preview display"><Desktop /></button><button title="Volume" aria-label="Volume"><SpeakerHigh /></button><button title="Preview settings" aria-label="Preview settings"><SlidersHorizontal /></button></div></div>
  </section>;
}

function FinalFilmPlayer({ outputUrl, posterUrl, title, runDetail }) {
  const [playbackState, setPlaybackState] = useState("loading");
  const videoRef = useRef(null);
  const sync = runDetail?.music_sync;
  const audioMap = runDetail?.audio_map;
  const lyricTiming = runDetail?.lyric_timing;
  const selection = runDetail?.video_selection;
  const sourceCount = ["performer", "stock", "premium", "local", "owned"].reduce((total, source) => total + Object.keys(selection?.[source] || {}).length, 0);
  useEffect(() => {
    setPlaybackState("loading");
    videoRef.current?.load();
  }, [outputUrl]);
  const lockOneX = (event) => {
    const video = event.currentTarget;
    video.defaultPlaybackRate = 1;
    if (video.playbackRate !== 1) video.playbackRate = 1;
  };
  return <div className="final-film-player">
    <video
      ref={videoRef}
      src={outputUrl}
      poster={posterUrl}
      controls
      playsInline
      preload="auto"
      aria-label={`Final rendered music film: ${title}`}
      onLoadedMetadata={lockOneX}
      onRateChange={lockOneX}
      onCanPlay={() => setPlaybackState("ready")}
      onPlaying={() => setPlaybackState("playing")}
      onPause={() => setPlaybackState("ready")}
      onWaiting={() => setPlaybackState("buffering")}
      onStalled={() => setPlaybackState("buffering")}
      onError={() => setPlaybackState("error")}
    />
    <div className={`playback-state ${playbackState}`}><span />{playbackState === "buffering" ? "Buffering" : playbackState === "error" ? "Playback error" : "Final MP4 · 1×"}</div>
    <div className="render-proof" aria-label="Render verification">
      <span><CheckCircle weight="fill" /> {sync?.within_frame_tolerance ? "Frame-locked cut" : "Render complete"}</span>
      {sync && <span>{Math.round(sync.max_error_seconds * 1000)} ms max cut drift</span>}
      {audioMap && <span>{audioMap.analysis_backend === "beat_this" ? "Beat This" : "Local DSP"} · {Math.round(audioMap.bpm)} BPM</span>}
      {lyricTiming?.analysis_backend === "faster_whisper_dtw" && <span>{Math.round(lyricTiming.anchor_coverage * 100)}% lyric anchors · {lyricTiming.language?.toUpperCase()}</span>}
      {sourceCount > 0 && <span>{sourceCount} directed clips</span>}
    </div>
  </div>;
}

function WaveTrack({ tone, label }) {
  return <div className={`wave-track ${tone}`} aria-label={label}>{Array.from({ length: 18 }, (_, index) => <Waveform key={index} weight="fill" aria-hidden="true" />)}</div>;
}

function Timeline({ scenes, selectedId, onSelect, playhead, setPlayhead }) {
  const total = scenes.reduce((sum, scene) => sum + scene.duration, 0);
  const rulerInterval = total <= 180 ? 30 : total <= 600 ? 60 : 120;
  const rulerMarks = Array.from({ length: Math.floor(total / rulerInterval) + 1 }, (_, index) => index * rulerInterval);
  if (rulerMarks.at(-1) < total) rulerMarks.push(total);
  const trackRef = useRef(null);
  const seek = (event) => {
    const bounds = trackRef.current?.getBoundingClientRect();
    if (!bounds) return;
    setPlayhead(Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)) * total);
  };
  return <section className="timeline panel-surface" aria-label="Editorial timeline">
    <div className="timeline-ruler"><div className="track-label-spacer" /><div className="ruler-marks">{rulerMarks.map((mark) => <span key={mark} style={{ left: `${(mark / total) * 100}%` }}>{formatClock(mark)}</span>)}</div></div>
    <div className="timeline-body"><div className="track-labels">{[[Eye, "Visuals"], [Microphone, "Voice"], [MusicNotes, "Music"], [Waveform, "SFX"], [ClosedCaptioning, "Captions"]].map(([Icon, label]) => <div className="track-label" key={label}><Icon /><span>{label}</span></div>)}</div>
      <div className="tracks" ref={trackRef} onClick={seek}><div className="scene-track">{scenes.map((scene) => <button key={scene.id} className={selectedId === scene.id ? "selected" : ""} style={{ width: `${(scene.duration / total) * 100}%` }} onClick={(event) => { event.stopPropagation(); onSelect(scene.id); }} title={scene.title}><img src={scene.image} alt="" /><span>{scene.id}</span></button>)}</div><WaveTrack tone="voice" label="Voice waveform" /><div className="music-track"><MusicNotes weight="fill" /><span>Quiet momentum</span><small>96 BPM · original</small></div><WaveTrack tone="sfx" label="Sound effects waveform" /><div className="caption-track">{scenes.map((scene) => <span key={scene.id} style={{ width: `${(scene.duration / total) * 100}%` }}>{scene.caption}</span>)}</div><div className="playhead" style={{ left: `${(playhead / total) * 100}%` }}><span /></div></div>
    </div>
    <div className="timeline-zoom"><button title="Zoom out" aria-label="Zoom out"><Minus /></button><input type="range" min="0" max="100" defaultValue="34" aria-label="Timeline zoom" /><button title="Zoom in" aria-label="Zoom in"><MagnifyingGlassPlus /></button><span>Fit</span></div>
  </section>;
}

function SceneInspector({ scene, sceneCount, onChange, onRegenerate, busy }) {
  return <aside className="inspector panel-surface"><div className="inspector-head"><span><FilmReel /> Scene {scene.id} of {sceneCount}</span><div><button aria-label="Previous scene"><CaretLeft /></button><button aria-label="Next scene"><CaretRight /></button></div></div><img className="inspector-thumb" src={scene.image} alt={`Selected visual for ${scene.title}`} />
    <label><span>Scene title</span><input value={scene.title} onChange={(event) => onChange({ title: event.target.value })} /></label><label className="duration-field"><span>Duration</span><input value={formatDuration(scene.duration)} readOnly /></label><div className="inspector-divider" />
    <label><span>Visual source</span><div className="source-select"><img src={scene.image} alt="" /><select value={scene.source} onChange={(event) => onChange({ source: event.target.value })}><option>Pexels matching clip</option><option>AI Generation candidate · admission required</option><option>Local information card</option><option>Stable photo motion</option><option>Veo premium clip</option><option>MiniMax premium clip</option><option>Pexels or generated still</option></select></div></label>
    <label><span>Motion</span><select value={scene.motion} onChange={(event) => onChange({ motion: event.target.value })}><option>Slow push-in</option><option>Gentle drift right</option><option>Parallax push-in</option><option>Locked frame</option></select></label>
    <label><span>Transition</span><div className="split-field"><select value={scene.transition} onChange={(event) => onChange({ transition: event.target.value })}><option>Crossfade</option><option>Dip to black</option><option>Fade out</option></select><select defaultValue="0.55"><option value="0.35">0.35s</option><option value="0.55">0.55s</option><option value="0.75">0.75s</option></select></div></label>
    <button className="secondary-button regenerate" onClick={onRegenerate} disabled={busy}>{busy ? <CircleNotch className="spin" /> : <Sparkle weight="fill" />} Regenerate with this scene</button><p className="inspector-note">Scene edits shape the next full render. The result stays local until you explicitly use Upload all.</p>
  </aside>;
}

function ProviderStrip({ system, selectedProfile, quality, workspace }) {
  const qualityLabel = quality === "max" ? "Max detail" : quality === "fast" ? "Fast draft" : "Balanced";
  const providers = [
    { label: "Local project", detail: "Autosaved", ok: true },
    { label: "OpenRouter", detail: "Script", ok: Boolean(system.openrouter) },
    { label: system.chatterbox ? "Chatterbox" : "Kokoro", detail: system.chatterbox ? "Expressive local voice" : "Fast voice fallback", ok: Boolean(system.chatterbox || system.kokoro) },
    { label: "Whisper", detail: "Captions · CPU", ok: Boolean(system.whisper) },
    { label: "Wan 2.2", detail: system.comfyui ? "Quarantined candidates" : "Optional · offline", ok: Boolean(system.comfyui) },
    { label: "Wan S2V", detail: system.fal_wan_s2v ? "Malaysian duet ready" : "Add FAL_KEY", ok: Boolean(system.fal_wan_s2v) },
    { label: system.gpu_name || "NVIDIA GPU", detail: system.nvenc ? "NVENC" : "CPU fallback", ok: Boolean(system.gpu || system.ffmpeg) },
    { label: ["viral", "ai"].includes(workspace) ? "1080×1920" : `${system.width || 1920}×${system.height || 1080}`, detail: `${system.fps || selectedProfile?.fps || 60} fps`, ok: true },
    { label: "$0 media APIs", detail: `${qualityLabel} · Pexels${system.pixabay ? " + Pixabay" : ""}`, ok: true },
  ];
  return <footer className="provider-strip">{providers.map((provider) => <div className="provider-cell" key={provider.label}><StatusDot ok={provider.ok} /><span><strong>{provider.label}</strong><small>{provider.detail}</small></span></div>)}</footer>;
}

function GenerateDialog({ open, onClose, profiles, form, setForm, onSelectProfile, onSubmit, submitting, system }) {
  const [uploadingVoice, setUploadingVoice] = useState(false);
  const [voiceReference, setVoiceReference] = useState(null);
  const voiceInputRef = useRef(null);
  const uploadVoice = async (file) => {
    if (!file) return;
    setUploadingVoice(true);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const result = await fetchJson("/api/voice/uploads", { method: "POST", body: payload });
      setVoiceReference(result);
      setForm((current) => ({ ...current, voice_provider: "chatterbox", voice_upload_id: result.upload_id }));
    } catch (error) {
      setVoiceReference({ error: error.message });
    } finally {
      setUploadingVoice(false);
    }
  };
  if (!open) return null;
  return <motion.div className="dialog-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}><motion.form className="generate-dialog" initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.98 }} onSubmit={onSubmit} onMouseDown={(event) => event.stopPropagation()}>
    <div className="dialog-head"><div><span className="eyebrow">Production setup</span><h2>Generate a complete film</h2><p>OpenRouter writes. Licensed matching footage leads. Local AI is a quarantined last resort, never a default hero shot.</p></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close setup"><X /></button></div>
    <div className="readiness-line"><span className={system.openrouter ? "ready" : "missing"}>{system.openrouter ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} OpenRouter</span><span className={system.pexels ? "ready" : "missing"}>{system.pexels ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Pexels Video</span><span className={system.chatterbox ? "ready" : "missing"}>{system.chatterbox ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Chatterbox</span><span className={system.nvenc ? "ready" : "missing"}>{system.nvenc ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} NVENC</span><span className={system.kokoro ? "ready" : "missing"}>{system.kokoro ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Kokoro fallback</span></div>
    <label><span>Use case</span><select value={form.profile} onChange={(event) => onSelectProfile(event.target.value)}>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
    <label><span>Topic or angle <small>optional</small></span><textarea value={form.topic} onChange={(event) => setForm({ ...form, topic: event.target.value })} placeholder="Example: A calm, factual walkthrough of joining Atomy USA" rows="3" /></label>
    <div className="form-grid"><label><span>Length</span><select value={form.duration_minutes} onChange={(event) => setForm({ ...form, duration_minutes: Number(event.target.value) })}><option value="2">2 min preview</option><option value="5">5 minutes</option><option value="7">7 minutes</option><option value="10">10 minutes</option></select></label><label><span>Frame rate</span><select value={form.fps} onChange={(event) => setForm({ ...form, fps: Number(event.target.value) })}><option value="60">60 fps · smooth</option><option value="30">30 fps · faster</option></select></label><label><span>Render quality</span><select value={form.quality} onChange={(event) => setForm({ ...form, quality: event.target.value })}><option value="fast">Fast draft</option><option value="balanced">Balanced · recommended</option><option value="max">Maximum detail</option></select></label></div>
    <div className="form-grid voice-grid"><label><span>Voice engine</span><select value={form.voice_provider} onChange={(event) => { const provider = event.target.value; setForm({ ...form, voice_provider: provider, voice_speed: provider === "kokoro" ? 0.98 : 1.0 }); }}><option value="chatterbox">Chatterbox · expressive GPU local</option><option value="kokoro">Kokoro · fast local fallback</option><option value="elevenlabs">ElevenLabs · premium jump</option><option value="openai">OpenAI · premium</option><option value="gemini">Gemini · premium</option></select></label><label><span>Performance</span><select value={form.voice_profile} onChange={(event) => setForm({ ...form, voice_profile: event.target.value })}><option value="dynamic_host">Dynamic host · recommended</option><option value="warm_documentary">Warm documentary</option><option value="confident_female">Confident female</option><option value="grounded_male">Grounded male</option><option value="editorial_blend">Editorial blend</option></select></label><label><span>Pace · {form.voice_speed.toFixed(2)}×</span><input type="range" min="0.75" max="1.2" step="0.01" value={form.voice_speed} onChange={(event) => setForm({ ...form, voice_speed: Number(event.target.value) })} /></label></div>
    <div className="form-grid editorial-controls"><label><span>Edit rhythm</span><select value={form.engagement_mode} onChange={(event) => setForm({ ...form, engagement_mode: event.target.value })}><option value="retention">Retention cut · recommended</option><option value="classic">Calm classic explainer</option></select></label><div className="retention-contract"><strong>Retention cut</strong><small>Cold open, early promise, 4–9 sec beats, re-hooks, proof cards, and a resolved payoff.</small></div></div>
    {form.voice_provider === "chatterbox" && <div className="voice-reference"><input ref={voiceInputRef} className="visually-hidden" type="file" accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/flac,audio/ogg,.mp3,.wav,.m4a,.aac,.flac,.ogg" onChange={(event) => uploadVoice(event.target.files?.[0])} /><button type="button" className={`drop-track ${voiceReference?.upload_id ? "has-track" : ""}`} onClick={() => voiceInputRef.current?.click()} disabled={uploadingVoice}>{uploadingVoice ? <CircleNotch className="spin" /> : voiceReference?.upload_id ? <CheckCircle weight="fill" /> : <Microphone />}<span><strong>{uploadingVoice ? "Preparing voice identity…" : voiceReference?.filename || "Optional: add your real voice character"}</strong><small>{voiceReference?.upload_id ? `${voiceReference.duration_seconds}s clean reference · stored locally` : voiceReference?.error || "5–30 sec, one speaker, no music · only a voice you own or have permission to use"}</small></span></button></div>}
    <div className="toggle-row"><button type="button" className={form.stock_images ? "active" : ""} onClick={() => setForm({ ...form, stock_images: !form.stock_images })}><FilmReel /> Matching real clips first <span>{form.stock_images ? "On" : "Off"}</span></button><button type="button" className={form.local_ai ? "active" : ""} onClick={() => setForm({ ...form, local_ai: !form.local_ai })}><Sparkle weight="fill" /> Strict AI fallback <span>{form.local_ai ? "Armed" : "Off"}</span></button><button type="button" className={form.captions ? "active" : ""} onClick={() => setForm({ ...form, captions: !form.captions })}><ClosedCaptioning /> Script-locked captions <span>{form.captions ? "On" : "Off"}</span></button></div>
    <div className="dialog-foot"><p><strong>Generation never auto-publishes.</strong> The finished package stays local until you review and use Upload all.</p><button className="primary-button" disabled={submitting || !system.openrouter}>{submitting ? <CircleNotch className="spin" /> : <Sparkle weight="fill" />} Start generation</button></div>
  </motion.form></motion.div>;
}

function RemotionLab({ form, setForm, system, startGeneration, submitting, activeJob, outputUrl, posterUrl, setToast, runDetail }) {
  const [uploading, setUploading] = useState(false);
  const [music, setMusic] = useState(null);
  const [performerUploads, setPerformerUploads] = useState({});
  const [uploadingPerformer, setUploadingPerformer] = useState("");
  const [viewerMode, setViewerMode] = useState(outputUrl ? "final" : "preview");
  const inputRef = useRef(null);
  const maleInputRef = useRef(null);
  const femaleInputRef = useRef(null);
  const beatMap = music?.beat_map;
  const duration = Math.min(form.music_seconds, beatMap?.duration_seconds || 30);
  const fullTrackSeconds = Math.max(15, Math.min(300, Math.ceil(beatMap?.duration_seconds || 60)));
  const renderLengths = [...new Set([15, 30, 60, 90, 180, 300, fullTrackSeconds].filter((value) => value <= fullTrackSeconds))].sort((a, b) => a - b);
  useEffect(() => { if (outputUrl) setViewerMode("final"); }, [outputUrl]);
  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const result = await fetchJson("/api/music/uploads", { method: "POST", body: payload });
      setMusic(result);
      setForm((current) => ({ ...current, mode: "music_film", music_upload_id: result.upload_id, music_seconds: Math.max(15, Math.min(300, Math.ceil(result.beat_map.duration_seconds))) }));
      setToast(`Track mapped · ${Math.round(result.beat_map.bpm)} BPM · ${Math.round(result.beat_map.rhythm_confidence * 100)}% grid confidence`);
    } catch (error) { setToast(error.message); } finally { setUploading(false); }
  };
  const uploadPerformer = async (file, role) => {
    if (!file) return;
    setUploadingPerformer(role);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const result = await fetchJson("/api/reference/uploads", { method: "POST", body: payload });
      setPerformerUploads((current) => ({ ...current, [role]: result }));
      setForm((current) => ({ ...current, [`music_${role}_reference_upload_id`]: result.upload_id }));
      setToast(`${role === "male" ? "Male" : "Female"} identity locked · ${result.width}×${result.height}`);
    } catch (error) { setToast(error.message); } finally { setUploadingPerformer(""); }
  };
  const submit = (event) => {
    event.preventDefault();
    if (!music) { inputRef.current?.click(); return; }
    startGeneration(event);
  };
  return <main className="remotion-lab">
    <section className="remotion-preview panel-surface">
      <div className="lab-heading"><div><span className="eyebrow">Music film director</span><h1>{outputUrl ? "Your finished film is ready" : "Directed, not stock-assembled"}</h1><p>{outputUrl ? "The actual rendered MP4 is now the primary stage. Switch to previsualization only when you want to tune the graphic language for the next cut." : "Your visual brief controls the clip world, while measured anchors drive scene cuts, kinetic type, impact flashes, punch-ins, and section-aware pacing."}</p></div><span className="remotion-badge">{outputUrl && viewerMode === "final" ? "FINAL MASTER" : "AUDIO-MAP LOCKED"}</span></div>
      {outputUrl && <div className="viewer-switch" role="tablist" aria-label="Music film viewer"><button type="button" role="tab" aria-selected={viewerMode === "final"} className={viewerMode === "final" ? "active" : ""} onClick={() => setViewerMode("final")}><FilmReel weight="fill" /> Final film</button><button type="button" role="tab" aria-selected={viewerMode === "preview"} className={viewerMode === "preview" ? "active" : ""} onClick={() => setViewerMode("preview")}><Waveform /> Live previsualization</button></div>}
      <div className={`player-shell ${viewerMode === "final" ? "is-final" : ""}`}>{outputUrl && viewerMode === "final" ? <FinalFilmPlayer outputUrl={outputUrl} posterUrl={posterUrl} title={form.music_title} runDetail={runDetail} /> : <Suspense fallback={<div className="player-loading"><CircleNotch className="spin" /> Loading Remotion engine…</div>}><RemotionPreview duration={duration} music={music} title={form.music_title} brand={form.music_brand} beatMap={beatMap} editStyle={form.music_edit_style} hookWords={form.music_hook_words} visualDirection={form.music_visual_direction} /></Suspense>}</div>
      {outputUrl && <div className="output-actions"><a className="latest-output" href={outputUrl} target="_blank" rel="noreferrer"><Play weight="fill" /> Open master in a new tab</a><a className="latest-output" href={outputUrl} download><FolderOpen /> Save MP4</a></div>}
    </section>
    <form className="music-console panel-surface" onSubmit={submit}>
      <div className="console-head"><div><span className="eyebrow">Master track</span><h2>Race Cut Director</h2></div><MusicNotes weight="duotone" /></div>
      <input ref={inputRef} className="visually-hidden" type="file" accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/flac,audio/ogg,.mp3,.wav,.m4a,.aac,.flac,.ogg" onChange={(event) => upload(event.target.files?.[0])} />
      <button type="button" className={`drop-track ${music ? "has-track" : ""}`} onClick={() => inputRef.current?.click()} disabled={uploading}>{uploading ? <CircleNotch className="spin" /> : music ? <CheckCircle weight="fill" /> : <UploadSimple />}<span><strong>{uploading ? "Mapping beats, phrases, drops, and energy…" : music?.filename || "Upload your final song"}</strong><small>{music ? `${Math.round(beatMap.duration_seconds)} sec · ${Math.round(beatMap.bpm)} BPM · ${beatMap.analysis_backend === "beat_this" ? "learned beat/downbeat model" : "local DSP map"}` : "MP3, WAV, M4A, FLAC, AAC or OGG · stays local"}</small></span></button>
      {beatMap && <><div className="beat-overview"><div><strong>{Math.round(beatMap.bpm)}</strong><small>BPM</small></div><div><strong>{Math.round(beatMap.rhythm_confidence * 100)}%</strong><small>Pulse confidence</small></div><div><strong>{beatMap.downbeat_confidence >= 0.35 ? "BAR" : "LYRIC"}</strong><small>{beatMap.downbeat_confidence >= 0.35 ? "Downbeat phase" : "Phase authority"}</small></div><div><strong>{beatMap.key_moments.length}</strong><small>Drops + surges</small></div></div><div className="music-structure" aria-label="Detected song structure"><div className="structure-bars">{beatMap.sections.filter((section) => section.start_seconds < duration).map((section, index) => <div key={`${section.start_seconds}-${index}`} className={`structure-section ${section.label}`} style={{ width: `${Math.max(1, ((Math.min(section.end_seconds, duration) - section.start_seconds) / duration) * 100)}%` }} title={`${section.label} · ${section.start_seconds.toFixed(1)}–${section.end_seconds.toFixed(1)} sec`}><span>{section.label}</span></div>)}</div><div className="structure-markers">{beatMap.key_moments.filter((moment) => moment.time_seconds <= duration).map((moment, index) => <i key={`${moment.time_seconds}-${index}`} className={moment.kind} style={{ left: `${(moment.time_seconds / duration) * 100}%` }} title={`${moment.kind} at ${moment.time_seconds.toFixed(2)} sec`} />)}</div><small>{beatMap.sections.length} structural sections · {beatMap.downbeat_confidence >= 0.35 ? `${beatMap.downbeats_seconds.length} trusted downbeats` : `${Math.round(beatMap.downbeat_confidence * 100)}% downbeat phase confidence · lyrics will set phrase phase`} · {beatMap.rolls.length} fills/rolls</small></div></>}
      <div className="form-grid music-identity"><label><span>Brand wordmark</span><input maxLength="32" value={form.music_brand} onChange={(event) => setForm({ ...form, music_brand: event.target.value })} /></label><label><span>Event title</span><input value={form.music_title} onChange={(event) => setForm({ ...form, music_title: event.target.value })} /></label></div>
      <section className="creative-direction">
        <div className="creative-direction-head"><div><span className="eyebrow">Visual direction</span><strong>Build the world you actually want</strong></div><small>{form.music_visual_direction.length}/1200</small></div>
        <div className="edit-style-grid">{musicEditStyles.map((style) => <button type="button" key={style.id} className={form.music_edit_style === style.id ? "active" : ""} onClick={() => setForm({ ...form, music_edit_style: style.id })}><span>{style.name}</span><small>{style.note}</small></button>)}</div>
        <label className="director-prompt"><span>Custom clip prompt <small>subjects · locations · wardrobe · atmosphere · camera language</small></span><textarea rows="4" maxLength="1200" value={form.music_visual_direction} onChange={(event) => setForm({ ...form, music_visual_direction: event.target.value })} placeholder="Example: Clearly adult smokers in a neon pit garage, cigarette embers and tire smoke, aggressive circuit racing, wet asphalt reflections, handheld flash photography, no visible brands." /></label>
        <label className="hook-words"><span>Beat text <small>comma-separated · short phrases hit hardest</small></span><input maxLength="300" value={form.music_hook_words} onChange={(event) => setForm({ ...form, music_hook_words: event.target.value })} placeholder="LIGHT IT UP, REDLINE, NO BRAKES, AFTER DARK" /></label>
        <label className="director-prompt lyrics-director"><span>Approved lyrics <small>exact words · keep [sections] and [female/male vocals] notes</small></span><textarea rows="12" maxLength="12000" value={form.music_lyrics} onChange={(event) => setForm({ ...form, music_lyrics: event.target.value })} placeholder="Paste the final lyrics. Exact text is aligned to the uploaded vocal and exported as JSON + LRC." /></label>
        <label className="hook-words"><span>Lyric language</span><select value={form.music_lyrics_language} onChange={(event) => setForm({ ...form, music_lyrics_language: event.target.value })}><option value="ms">Malay</option><option value="id">Indonesian</option><option value="en">English</option><option value="auto">Auto-detect</option></select></label>
        <p className="direction-proof"><Sparkle weight="fill" /> Approved lyrics are aligned word-by-word without forcing the ASR to hallucinate the brand. Vocal onsets set phrase phase; beat pulses handle micro-accents. The supplied master remains the only audio clock.</p>
      </section>
      <section className="performer-director">
        <div className="creative-direction-head"><div><span className="eyebrow">Footage policy</span><strong>Licensed footage · real people · real places</strong></div><span className="performer-ready ready">STOCK-ONLY LOCKED</span></div>
        <div className="performer-mode" role="group" aria-label="Footage mode"><button type="button" className="active" onClick={() => setForm({ ...form, music_performer_mode: "stock_mix", local_ai: false })}><FilmReel weight="fill" /><span><strong>Directed existing-footage story</strong><small>Friends, smoke details, guitar, dance and cars are sourced from licensed clips; no generated people or lip-sync</small></span></button><button type="button" disabled><Sparkle /><span><strong>One owned AI closing plate</strong><small>Only the final cigarette ember/smoke frame is synthetic; PRAGON lettering is added exactly in post</small></span></button></div>
        <div className="proof-before-spend"><CheckCircle weight="fill" /><p><strong>Coverage gate</strong>The render stops if any non-outro scene lacks a licensed video clip. Identity-safe wides, silhouettes, hands and over-shoulders keep the friendship cut coherent without pretending unrelated stock actors are one recurring cast.</p></div>
      </section>
      <div className="form-grid music-options"><label><span>Render length</span><select value={form.music_seconds} onChange={(event) => setForm({ ...form, music_seconds: Number(event.target.value) })}>{renderLengths.map((seconds) => <option value={seconds} key={seconds}>{beatMap && seconds === fullTrackSeconds ? `${seconds} sec · ${beatMap.duration_seconds <= 300 ? "full track" : "five-minute cap"}` : `${seconds} sec cut`}</option>)}</select></label><label><span>Output</span><select value={form.fps} onChange={(event) => setForm({ ...form, fps: Number(event.target.value) })}><option value="60">1080p · 60 fps master</option><option value="30">1080p · 30 fps draft</option></select></label></div>
      <div className="shot-stack"><span>Automatic creative stack</span>{[["01", "Directed retrieval", "Your world is rotated through character, detail, geography, and action searches"], ["02", "Motion-fit footage", "Source windows are ranked for the section’s measured energy"], ["03", "Beat typography", "Hook phrases hit selected downbeats with style-specific treatment"], ["04", "Dynamic restraint", "Peaks intensify; breaks breathe; flashes never fire on every beat"]].map(([index, title, note]) => <div key={index}><b>{index}</b><span><strong>{title}</strong><small>{note}</small></span></div>)}</div>
      <div className="toggle-row lab-toggles"><button type="button" disabled><Sparkle weight="fill" /> AI filler <span>Blocked</span></button><button type="button" className={form.stock_images ? "active" : ""} onClick={() => setForm({ ...form, stock_images: !form.stock_images })}><FilmReel /> Licensed clips required <span>{form.stock_images ? "On" : "Off"}</span></button></div>
      <p className="hardware-note"><StatusDot ok={system.nvenc} /> One canonical audio map drives preview and export. Rhythmic sections cut on downbeats; sparse sections hold through phrases. Source windows are motion-ranked and reject windows that cross detected source cuts. Final audio remains the supplied master at 320 kbps.</p>
      <button className="primary-button race-render" disabled={submitting || activeJob?.state === "running" || !music}>{submitting || activeJob?.state === "running" ? <CircleNotch className="spin" /> : <FilmReel weight="fill" />} {activeJob?.state === "running" ? "Building structure-locked cut…" : "Build exceptional music film"}</button>
    </form>
  </main>;
}

function LogDrawer({ open, onClose, job, log, onCancel }) {
  return <AnimatePresence>{open && <motion.aside className="log-drawer" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 280 }}><div className="log-head"><div><span className="eyebrow">Generation log</span><h2>{job ? titleCase(job.state) : "No active job"}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close log"><X /></button></div>{job && <div className="job-meta"><span>Job {job.job_id}</span><span>{job.profile}</span>{job.pid && <span>PID {job.pid}</span>}</div>}<pre>{log || "The log will appear here once generation starts."}</pre>{job?.state === "running" && <button className="danger-button" onClick={onCancel}><StopCircle /> Cancel generation</button>}</motion.aside>}</AnimatePresence>;
}

const prettyBytes = (bytes = 0) => bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(2)} GB` : `${Math.max(0, bytes / 1024 ** 2).toFixed(1)} MB`;

function PublishDrawer({ open, onClose, run, onPublished, setToast }) {
  const [packageData, setPackageData] = useState(null);
  const [publishForm, setPublishForm] = useState({ title: "", description: "", tags: "", privacy: "private", schedule: false, publishAt: "", uploadThumbnail: true, uploadCaptions: true, confirmPublic: false });
  const [publishJob, setPublishJob] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadPackage = async ({ preserve = false } = {}) => {
    if (!run?.run_id) return;
    try {
      const payload = await fetchJson(`/api/runs/${run.run_id}/publish-package`);
      setPackageData(payload);
      if (!preserve) setPublishForm({ title: payload.title, description: payload.description, tags: payload.tags.join(", "), privacy: "private", schedule: false, publishAt: "", uploadThumbnail: true, uploadCaptions: payload.captions_available, confirmPublic: false });
    } catch (error) { setToast(error.message); }
  };

  useEffect(() => {
    if (!open || !run?.run_id) return;
    setPackageData(null); setPublishJob(null); loadPackage();
  }, [open, run?.run_id]);
  useEffect(() => {
    if (!open || !packageData?.client_configured || packageData.authorized) return undefined;
    const timer = window.setInterval(() => loadPackage({ preserve: true }), 2200);
    return () => window.clearInterval(timer);
  }, [open, packageData?.client_configured, packageData?.authorized, run?.run_id]);
  useEffect(() => {
    const connected = (event) => { if (event.origin === window.location.origin && event.data?.type === "atlasforge-youtube-connected") loadPackage({ preserve: true }); };
    window.addEventListener("message", connected);
    return () => window.removeEventListener("message", connected);
  }, [run?.run_id]);
  useEffect(() => {
    if (!publishJob || !["queued", "running"].includes(publishJob.state)) return undefined;
    const check = () => fetchJson(`/api/publishing/jobs/${publishJob.publish_id}`).then((next) => {
      setPublishJob(next);
      if (next.state === "completed") { setToast("Complete YouTube package uploaded"); loadPackage({ preserve: true }); onPublished(); }
      if (next.state === "failed") setToast("Upload paused safely — retry will resume");
    }).catch((error) => setToast(error.message));
    const timer = window.setInterval(check, 1200); check();
    return () => window.clearInterval(timer);
  }, [publishJob?.publish_id, publishJob?.state]);

  const authorize = async () => {
    try {
      const payload = await fetchJson("/api/publishing/oauth/start", { method: "POST" });
      window.open(payload.authorization_url, "atlasforge-youtube-oauth", "popup,width=620,height=760");
      setToast("Finish YouTube authorization in the opened window");
    } catch (error) { setToast(error.message); }
  };
  const submitPackage = async () => {
    if (!packageData) return;
    setLoading(true);
    try {
      const tags = publishForm.tags.split(",").map((tag) => tag.trim()).filter(Boolean).slice(0, 30);
      const publishAt = publishForm.schedule && publishForm.publishAt ? new Date(publishForm.publishAt).toISOString() : null;
      const job = await fetchJson(`/api/runs/${run.run_id}/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: publishForm.title, description: publishForm.description, tags, privacy: publishForm.privacy, publish_at: publishAt, upload_thumbnail: publishForm.uploadThumbnail, upload_captions: publishForm.uploadCaptions, confirm_public: publishForm.privacy === "public" && publishForm.confirmPublic }) });
      setPublishJob(job); setToast("YouTube package upload started");
    } catch (error) { setToast(error.message); } finally { setLoading(false); }
  };
  const busy = loading || ["queued", "running"].includes(publishJob?.state);
  const hardBlockers = packageData?.blockers.filter((item) => item !== "YouTube is not authorized") || [];
  const publicReady = publishForm.privacy !== "public" || publishForm.confirmPublic;
  const scheduledReady = !publishForm.schedule || Boolean(publishForm.publishAt);

  return <AnimatePresence>{open && <><motion.button className="publish-scrim" aria-label="Close publishing" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} /><motion.aside className="publish-drawer" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 280 }}>
    <div className="publish-head"><div><span className="eyebrow">One-click YouTube package</span><h2>{publishJob ? titleCase(publishJob.state) : "Review once. Upload everything."}</h2><p>Final video, metadata, thumbnail, captions, visibility, and synthetic-media disclosure travel together.</p></div><button className="icon-button" onClick={onClose} aria-label="Close publishing"><X /></button></div>
    {!packageData ? <div className="publish-loading"><CircleNotch className="spin" /> Assembling the upload package…</div> : <div className="publish-scroll">
      <section className="publish-hero"><img src={packageData.thumbnail_url} alt="YouTube thumbnail" /><div><span className="release-chip"><LockKey /> Private by default</span><strong>{prettyBytes(packageData.video_bytes)} final master</strong><small>{packageData.existing_video_id ? `YouTube ID ${packageData.existing_video_id}` : "No upload has started"}</small>{packageData.youtube_url && <a href={packageData.youtube_url} target="_blank" rel="noreferrer">Open on YouTube <ArrowSquareOut /></a>}</div></section>
      <section className="package-checks" aria-label="Package readiness">
        {[["Final MP4", packageData.video_bytes > 0, prettyBytes(packageData.video_bytes)], ["Thumbnail", packageData.thumbnail_bytes > 0, prettyBytes(packageData.thumbnail_bytes)], ["Timed captions", packageData.captions_available, packageData.captions_available ? "SRT ready" : "Not generated"], ["Quality gate", packageData.quality_state !== "failed", titleCase(packageData.quality_state)]].map(([label, ready, detail]) => <div className={ready ? "ready" : "blocked"} key={label}>{ready ? <CheckCircle weight="fill" /> : <Warning weight="fill" />}<span><strong>{label}</strong><small>{detail}</small></span></div>)}
      </section>
      <section className={`youtube-connection ${packageData.authorized ? "connected" : ""}`}><YoutubeLogo weight="fill" /><div><strong>{packageData.authorized ? "YouTube connected" : packageData.client_configured ? "Connect your channel once" : "OAuth file required once"}</strong><small>{packageData.client_configured ? packageData.auth_detail : "Save a Desktop OAuth JSON as secrets/youtube_client_secret.json, then restart Studio."}</small></div>{!packageData.authorized && packageData.client_configured && <button className="secondary-button" type="button" onClick={authorize}>Authorize</button>}</section>
      <div className="publish-fields"><label><span>Title <b>{publishForm.title.length}/100</b></span><input value={publishForm.title} maxLength={100} onChange={(event) => setPublishForm({ ...publishForm, title: event.target.value })} /></label><label><span>Description <b>{publishForm.description.length}/5000</b></span><textarea value={publishForm.description} maxLength={5000} onChange={(event) => setPublishForm({ ...publishForm, description: event.target.value })} /></label><label><span>Tags <b>{publishForm.tags.split(",").filter(Boolean).length}/30</b></span><input value={publishForm.tags} onChange={(event) => setPublishForm({ ...publishForm, tags: event.target.value })} placeholder="Atomy, joining guide, membership" /></label></div>
      <section className="release-controls"><label><span>Visibility</span><select value={publishForm.privacy} onChange={(event) => setPublishForm({ ...publishForm, privacy: event.target.value, schedule: event.target.value === "private" ? publishForm.schedule : false, confirmPublic: false })}><option value="private">Private · safest review</option><option value="unlisted">Unlisted · anyone with link</option><option value="public">Public · release immediately</option></select></label><button type="button" className={publishForm.schedule ? "active" : ""} disabled={publishForm.privacy !== "private"} onClick={() => setPublishForm({ ...publishForm, schedule: !publishForm.schedule })}><CalendarBlank /> Schedule release</button>{publishForm.schedule && <label><span>Local publish time</span><input type="datetime-local" value={publishForm.publishAt} onChange={(event) => setPublishForm({ ...publishForm, publishAt: event.target.value })} /></label>}</section>
      <section className="package-toggles"><label><input type="checkbox" checked={publishForm.uploadThumbnail} onChange={(event) => setPublishForm({ ...publishForm, uploadThumbnail: event.target.checked })} /><ImageIcon /> Custom thumbnail</label><label className={!packageData.captions_available ? "disabled" : ""}><input type="checkbox" disabled={!packageData.captions_available} checked={publishForm.uploadCaptions} onChange={(event) => setPublishForm({ ...publishForm, uploadCaptions: event.target.checked })} /><ClosedCaptioning /> Caption track</label></section>
      {publishForm.privacy === "public" && <label className="public-confirm"><input type="checkbox" checked={publishForm.confirmPublic} onChange={(event) => setPublishForm({ ...publishForm, confirmPublic: event.target.checked })} /><span><strong>I reviewed this package</strong><small>Public uploads can become visible immediately. Private is recommended for the first review.</small></span></label>}
      {hardBlockers.length > 0 && <div className="publish-blockers"><Warning weight="fill" /><div><strong>Upload blocked</strong>{hardBlockers.map((item) => <small key={item}>{item}</small>)}</div></div>}
      {publishJob && <section className={`publish-progress ${publishJob.state}`}><div><span>{titleCase(publishJob.stage)}</span><strong>{publishJob.progress}%</strong></div><div className="progress-track"><i style={{ width: `${publishJob.progress}%` }} /></div><p>{publishJob.message}</p>{publishJob.youtube_url && <a href={publishJob.youtube_url} target="_blank" rel="noreferrer">View uploaded video <ArrowSquareOut /></a>}</section>}
    </div>}
    {packageData && <div className="publish-foot"><div><strong>No duplicate uploads</strong><small>If thumbnail or captions fail, Retry resumes from that step.</small></div><button className="primary-button" onClick={submitPackage} disabled={busy || !packageData.authorized || hardBlockers.length > 0 || !publishForm.title.trim() || !publishForm.description.trim() || !publicReady || !scheduledReady}>{busy ? <CircleNotch className="spin" /> : <UploadSimple weight="bold" />} {busy ? `${titleCase(publishJob?.stage || "uploading")}…` : publishJob?.state === "failed" || packageData.existing_video_id ? "Resume / sync package" : "Upload complete package"}</button></div>}
  </motion.aside></>}</AnimatePresence>;
}

export function App() {
  const [profiles, setProfiles] = useState(fallbackProfiles);
  const [system, setSystem] = useState({});
  const [jobs, setJobs] = useState([]);
  const [runs, setRuns] = useState([]);
  const [runDetail, setRunDetail] = useState(null);
  const [scenes, setScenes] = useState(initialScenes);
  const [selectedId, setSelectedId] = useState(1);
  const [activeTab, setActiveTab] = useState("chapters");
  const [playing, setPlaying] = useState(false);
  const [playhead, setPlayhead] = useState(2);
  const [setupOpen, setSetupOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [log, setLog] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState("");
  const [workspace, setWorkspace] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get("workspace");
    return ["editor", "remotion", "viral", "ai"].includes(requested) ? requested : "editor";
  });
  const [form, setForm] = useState({ profile: "pragon-sepang", topic: "", duration_minutes: 7, fps: 60, quality: "balanced", stock_images: true, local_ai: false, captions: true, fresh: true, mode: "faceless_narrated", music_upload_id: null, music_brand: "PRAGON", music_title: "PRA-GON · SELAMANYA", music_seconds: 209, music_visual_direction: "A life-filled Malaysian night music video assembled only from licensed existing clips. Clearly adult Malaysian or Southeast Asian friends arrive at a private circuit garage, gather around a mamak table, share real laughter, close glances, kopi and teh tarik, take elegant ciggies breaks with restrained smoke, watch an existing male guitarist perform and an existing female dancer move with the female verse, then cruise in a polished black performance car. Use identity-safe wides, silhouettes, hands, details and over-shoulders so unrelated stock faces are never presented as one recurring person. Drifting and speed appear only on real musical surges and the guitar solo—not as the backbone. Premium 35mm realism, warm amber skin, cyan edge light, humid night air and candid chemistry; no minors, generated people, synthetic lip-sync, alcohol, product packaging, readable third-party brands, or Fast & Furious footage. Only the final PRAGON cigarette-ember plate may be AI-generated.", music_hook_words: "PRA-GON, SELAMANYA, SATU, BERDUA", music_lyrics: pragonLyrics, music_lyrics_language: "ms", music_edit_style: "pragon_neon", music_gap_provider: "auto", music_performer_mode: "stock_mix", music_male_reference_upload_id: null, music_female_reference_upload_id: null, music_performer_mix: 0.35, music_performer_budget_usd: 0, voice_provider: "chatterbox", voice_profile: "dynamic_host", voice_speed: 1.0, voice_upload_id: null, engagement_mode: "retention", viral_recipe: "beat_creature", viral_prompt: "", viral_provider: "local_wan", viral_seconds: 5, viral_candidates: 2, reference_upload_id: null, dialogue_a: "", dialogue_b: "" });

  const selectedScene = scenes.find((scene) => scene.id === selectedId) || scenes[0];
  const selectedProfile = profiles.find((profile) => profile.id === form.profile) || profiles[0];
  const totalDuration = scenes.reduce((sum, scene) => sum + scene.duration, 0);
  const activeJob = jobs.find((job) => ["queued", "running"].includes(job.state)) || jobs[0] || null;
  const editorialRun = runs.find((run) => (run.pipeline_kind || "narrated") === "narrated") || null;
  const desiredPipeline = ["viral", "ai"].includes(workspace) ? "viral_short" : workspace === "remotion" ? "music_film" : "narrated";
  const latestRun = runs.find((run) => (run.pipeline_kind || "narrated") === desiredPipeline) || null;
  const outputUrl = latestRun && ["ready", "published"].includes(latestRun.status) ? `/api/runs/${latestRun.run_id}/video` : null;
  const posterUrl = latestRun && ["ready", "published"].includes(latestRun.status) ? `/api/runs/${latestRun.run_id}/thumbnail` : null;

  const refresh = async () => {
    const results = await Promise.allSettled([fetchJson("/api/profiles"), fetchJson("/api/system"), fetchJson("/api/jobs"), fetchJson("/api/runs")]);
    if (results[0].status === "fulfilled" && results[0].value.length) setProfiles(results[0].value.filter((item) => !item.error));
    if (results[1].status === "fulfilled") setSystem(results[1].value);
    if (results[2].status === "fulfilled") setJobs(results[2].value);
    if (results[3].status === "fulfilled") {
      setRuns(results[3].value);
    }
  };

  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 3500); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    const mode = ["viral", "ai"].includes(workspace) ? "viral_short" : workspace === "remotion" ? "music_film" : "faceless_narrated";
    setForm((current) => {
      if (workspace === "ai") {
        const aiDefaults = { ...current, mode, viral_recipe: "cinematic_insert", viral_provider: "local_wan", quality: "max" };
        return current.mode === mode && current.viral_recipe === "cinematic_insert" && current.viral_provider === "local_wan" && current.quality === "max" ? current : aiDefaults;
      }
      return current.mode === mode ? current : { ...current, mode };
    });
  }, [workspace]);
  useEffect(() => { if (!playing) return undefined; const timer = window.setInterval(() => setPlayhead((current) => current + 1 >= totalDuration ? 0 : current + 1), 100); return () => window.clearInterval(timer); }, [playing, totalDuration]);
  useEffect(() => { if (!activeJob || !logOpen) return undefined; const loadLog = () => fetchJson(`/api/jobs/${activeJob.job_id}/log`).then((data) => setLog(data.log)).catch(() => {}); loadLog(); const timer = window.setInterval(loadLog, 2000); return () => window.clearInterval(timer); }, [activeJob?.job_id, logOpen]);
  useEffect(() => { if (!toast) return undefined; const timer = window.setTimeout(() => setToast(""), 3200); return () => window.clearTimeout(timer); }, [toast]);
  useEffect(() => {
    if (!latestRun?.run_id) { setRunDetail(null); return; }
    fetchJson(`/api/runs/${latestRun.run_id}`).then(setRunDetail).catch(() => setRunDetail(null));
  }, [latestRun?.run_id]);
  useEffect(() => {
    const runId = editorialRun?.run_id;
    if (!runId || !["ready", "published"].includes(editorialRun.status)) return undefined;
    let current = true;
    fetchJson(`/api/runs/${runId}/storyboard`).then((storyboard) => {
      if (!current || !storyboard.scenes?.length) return;
      setScenes(storyboardToScenes(storyboard, runId));
      setSelectedId(storyboard.scenes[0].index);
      setPlayhead(0);
      setPlaying(false);
    }).catch(() => {});
    return () => { current = false; };
  }, [editorialRun?.run_id, editorialRun?.status]);

  const updateScene = (patch) => { setScenes((current) => current.map((scene) => scene.id === selectedId ? { ...scene, ...patch } : scene)); setToast("Scene change saved for the next render"); };
  const selectProfile = (profileId) => {
    const profile = profiles.find((item) => item.id === profileId);
    setForm((current) => ({
      ...current,
      profile: profileId,
      duration_minutes: profile?.duration_minutes || current.duration_minutes,
      fps: profile?.fps || current.fps,
      voice_provider: profile?.voice_provider || current.voice_provider,
    }));
  };
  const startGeneration = async (event) => {
    event?.preventDefault(); setSubmitting(true);
    try {
      const created = await fetchJson("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, topic: form.topic.trim() || null }) });
      setJobs((current) => [created, ...current]); setSetupOpen(false); setLogOpen(true); setToast("Generation started — no automatic upload");
    } catch (error) { setToast(error.message); } finally { setSubmitting(false); }
  };
  const cancelJob = async () => {
    if (!activeJob) return;
    try { const cancelled = await fetchJson(`/api/jobs/${activeJob.job_id}/cancel`, { method: "POST" }); setJobs((current) => current.map((job) => job.job_id === cancelled.job_id ? cancelled : job)); setToast("Generation cancelled safely"); } catch (error) { setToast(error.message); }
  };
  const addScene = () => { const next = { ...initialScenes.at(-1), id: scenes.length + 1, title: "New supporting scene", caption: "Add one clear idea for this moment.", duration: 30 }; setScenes((current) => [...current, next]); setSelectedId(next.id); setToast("Scene added to the working storyboard"); };
  const lastRunLabel = latestRun ? `${titleCase(latestRun.status)} · ${latestRun.publication_date}` : "No renders yet";

  return <div className="studio-shell">
    <header className="topbar"><button className="menu-button" aria-label="Open menu"><List /></button><BrandMark /><div className="workspace-switch"><button className={workspace === "editor" ? "active" : ""} onClick={() => { setWorkspace("editor"); setForm((current) => ({ ...current, mode: "faceless_narrated" })); }}>Editorial</button><button className={workspace === "remotion" ? "active" : ""} onClick={() => { setWorkspace("remotion"); setForm((current) => ({ ...current, mode: "music_film" })); }}><Waveform /> Remotion Lab</button><button className={workspace === "viral" ? "active" : ""} onClick={() => { setWorkspace("viral"); setForm((current) => ({ ...current, mode: "viral_short" })); }}><Sparkle weight="fill" /> AI Viral Lab</button><button className={workspace === "ai" ? "active" : ""} onClick={() => { setWorkspace("ai"); setForm((current) => ({ ...current, mode: "viral_short", quality: "max", viral_recipe: "cinematic_insert" })); }}><FilmReel weight="fill" /> AI Generation</button></div><div className="project-title"><strong>{workspace === "remotion" ? form.music_title : workspace === "viral" ? "AI-native viral short" : workspace === "ai" ? "Quarantined AI candidate workshop" : selectedProfile?.name || "AtlasForge project"}</strong><StatusDot ok /><span>Autosaved</span></div>{workspace === "editor" && <label className="usecase-select"><span>Use case</span><select value={form.profile} onChange={(event) => selectProfile(event.target.value)}>{profiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.name}</option>)}</select><CaretDown /></label>}<button className="primary-button generate-button" onClick={() => workspace === "remotion" ? document.querySelector(".drop-track")?.click() : ["viral", "ai"].includes(workspace) ? document.querySelector(".viral-prompt textarea")?.focus() : setSetupOpen(true)} disabled={activeJob?.state === "running"}><Sparkle weight="fill" /> {activeJob?.state === "running" ? "Generating…" : workspace === "remotion" ? "Load song" : workspace === "viral" ? "Direct shot" : workspace === "ai" ? "New candidate" : "Generate film"}</button>{latestRun && ["ready", "published"].includes(latestRun.status) && <button className={`publish-button ${latestRun.status === "published" ? "is-published" : ""}`} onClick={() => setPublishOpen(true)}><YoutubeLogo weight="fill" /> {latestRun.status === "published" ? "Published" : "Upload all"}</button>}<span className="shortcut"><Command />K</span><button className="top-icon" title="Help" aria-label="Help"><Question /></button><button className="top-icon" title="Notifications" aria-label="Notifications"><Bell /></button><div className="avatar" title="Local owner">AF</div></header>
    <div className="stagebar"><StageRail stages={runDetail?.stages || []} activeJob={activeJob?.state === "running" ? activeJob : null} published={latestRun?.status === "published"} /><div className="last-run"><span>Last run: {lastRunLabel}</span><button className="secondary-button" onClick={() => setLogOpen(true)}>View log <CaretRight /></button></div></div>
    {workspace === "editor" ? <main className="editor-grid"><ChapterRail scenes={scenes} selectedId={selectedId} onSelect={setSelectedId} activeTab={activeTab} setActiveTab={setActiveTab} onAddScene={addScene} /><div className="edit-canvas"><Preview scene={selectedScene} playing={playing} setPlaying={setPlaying} playhead={playhead} setPlayhead={setPlayhead} totalDuration={totalDuration} outputUrl={outputUrl} /><Timeline scenes={scenes} selectedId={selectedId} onSelect={setSelectedId} playhead={playhead} setPlayhead={setPlayhead} /></div><SceneInspector scene={selectedScene} sceneCount={scenes.length} onChange={updateScene} onRegenerate={() => setSetupOpen(true)} busy={activeJob?.state === "running"} /></main> : workspace === "remotion" ? <RemotionLab form={form} setForm={setForm} system={system} startGeneration={startGeneration} submitting={submitting} activeJob={activeJob} outputUrl={outputUrl} posterUrl={posterUrl} setToast={setToast} runDetail={runDetail} /> : <Suspense fallback={<main className="viral-lab"><div className="panel-surface player-loading"><CircleNotch className="spin" /> Loading generation workspace…</div></main>}>{workspace === "ai" ? <AIGenerationLab form={form} setForm={setForm} system={system} startGeneration={startGeneration} submitting={submitting} activeJob={activeJob} outputUrl={outputUrl} setToast={setToast} runDetail={runDetail} /> : <ViralLab form={form} setForm={setForm} system={system} startGeneration={startGeneration} submitting={submitting} activeJob={activeJob} outputUrl={outputUrl} setToast={setToast} runDetail={runDetail} />}</Suspense>}
    <ProviderStrip system={system} selectedProfile={selectedProfile} quality={form.quality} workspace={workspace} />
    <AnimatePresence><GenerateDialog open={setupOpen} onClose={() => setSetupOpen(false)} profiles={profiles} form={form} setForm={setForm} onSelectProfile={selectProfile} onSubmit={startGeneration} submitting={submitting} system={system} /></AnimatePresence><LogDrawer open={logOpen} onClose={() => setLogOpen(false)} job={activeJob} log={log} onCancel={cancelJob} /><PublishDrawer open={publishOpen} onClose={() => setPublishOpen(false)} run={latestRun} onPublished={refresh} setToast={setToast} />
    <AnimatePresence>{toast && <motion.div className="toast" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}><CheckCircle weight="fill" /> {toast}</motion.div>}</AnimatePresence>
  </div>;
}

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Bell, CaretDown, CaretLeft, CaretRight, Check, CheckCircle, CircleNotch,
  ClosedCaptioning, Command, Desktop, DotsThree, Eye, FilmReel, FolderOpen,
  Image as ImageIcon, List, MagnifyingGlassPlus, Microphone, Minus, MusicNotes,
  Pause, Play, Plus, Question, Queue, SlidersHorizontal, Sparkle, SpeakerHigh,
  StopCircle, UploadSimple, Warning, Waveform, X,
} from "@phosphor-icons/react";
import "@fontsource/dm-sans/latin-400.css";
import "@fontsource/dm-sans/latin-500.css";
import "@fontsource/dm-sans/latin-600.css";
import "@fontsource/cormorant-garamond/latin-600.css";

const fallbackProfiles = [
  { id: "atomy-us-openrouter", name: "Atomy USA — Joining Guide", brand: "Atomy", region: "United States", duration_minutes: 7, text_provider: "openrouter", voice_provider: "kokoro", fps: 60 },
  { id: "atomy-us-preview", name: "Atomy USA — Fast Preview", brand: "Atomy", region: "United States", duration_minutes: 2, text_provider: "openrouter", voice_provider: "kokoro", fps: 60 },
  { id: "general-explainer", name: "General Explainer", brand: "", region: "Global", duration_minutes: 5, text_provider: "openrouter", voice_provider: "kokoro", fps: 60 },
];

const RemotionPreview = lazy(() => import("./remotion/RemotionPreview"));
const ViralLab = lazy(() => import("./viral/ViralLab"));

const initialScenes = [
  { id: 1, title: "How to Join Atomy USA", caption: "A clear, practical member-registration guide.", duration: 55, image: "/assets/scenes/city-waterfront.webp", source: "Pexels or generated still", motion: "Slow push-in", transition: "Crossfade" },
  { id: 2, title: "Before You Begin", caption: "Prepare a sponsor ID and accurate personal details.", duration: 88, image: "/assets/scenes/member-guidance.webp", source: "Pexels people", motion: "Gentle drift right", transition: "Crossfade" },
  { id: 3, title: "Understand the Products", caption: "Review official product information before deciding.", duration: 96, image: "/assets/scenes/product-education.webp", source: "Product still", motion: "Parallax push-in", transition: "Dip to black" },
  { id: 4, title: "Know the Model", caption: "Results vary; there are no guaranteed earnings.", duration: 94, image: "/assets/scenes/member-education.webp", source: "Education footage", motion: "Locked frame", transition: "Crossfade" },
  { id: 5, title: "Complete Registration", caption: "Use the official regional site and verify every field.", duration: 87, image: "/assets/scenes/registration.webp", source: "Pexels lifestyle", motion: "Slow push-in", transition: "Fade out" },
];

const sceneFallbackImages = initialScenes.map((scene) => scene.image);
const storyboardToScenes = (storyboard, runId) => storyboard.scenes.map((scene, position) => {
  const angle = scene.camera_angle?.toLowerCase() || "";
  const transition = scene.transition?.toLowerCase() || "";
  const searchTitle = titleCase(scene.visual_search_query || scene.environment || `Scene ${scene.index}`);
  const sourceLabel = {
    pexels_video: "Pexels matching clip",
    comfyui_wan22: "Wan 2.2 local AI clip",
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
  { label: "Visuals", stages: ["images", "premium_video", "local_video", "stock_video"] },
  { label: "Edit", stages: ["render", "finalize"] },
  { label: "Captions", stages: ["subtitles"] },
  { label: "Quality", stages: ["metadata", "quality_gate"] },
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

function StageRail({ stages = [], activeJob }) {
  const stageMap = useMemo(() => new Map(stages.map((stage) => [stage.stage, stage.status])), [stages]);
  const hasJob = Boolean(activeJob);
  return <nav className="stage-rail" aria-label="Production stages">{productionSteps.map((step, index) => {
    const statuses = step.stages.map((stage) => stageMap.get(stage)).filter(Boolean);
    const complete = statuses.length > 0 && statuses.every((status) => status === "completed");
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
      [FolderOpen, "Local hero shots", "Wan 2.2 via ComfyUI"],
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
    <label><span>Visual source</span><div className="source-select"><img src={scene.image} alt="" /><select value={scene.source} onChange={(event) => onChange({ source: event.target.value })}><option>Pexels matching clip</option><option>Wan 2.2 local AI clip</option><option>Local information card</option><option>Stable photo motion</option><option>Veo premium clip</option><option>MiniMax premium clip</option><option>Pexels or generated still</option></select></div></label>
    <label><span>Motion</span><select value={scene.motion} onChange={(event) => onChange({ motion: event.target.value })}><option>Slow push-in</option><option>Gentle drift right</option><option>Parallax push-in</option><option>Locked frame</option></select></label>
    <label><span>Transition</span><div className="split-field"><select value={scene.transition} onChange={(event) => onChange({ transition: event.target.value })}><option>Crossfade</option><option>Dip to black</option><option>Fade out</option></select><select defaultValue="0.55"><option value="0.35">0.35s</option><option value="0.55">0.55s</option><option value="0.75">0.75s</option></select></div></label>
    <button className="secondary-button regenerate" onClick={onRegenerate} disabled={busy}>{busy ? <CircleNotch className="spin" /> : <Sparkle weight="fill" />} Regenerate with this scene</button><p className="inspector-note">Scene edits shape the next full render. Publishing always stays off in Studio.</p>
  </aside>;
}

function ProviderStrip({ system, selectedProfile, quality, workspace }) {
  const qualityLabel = quality === "max" ? "Max detail" : quality === "fast" ? "Fast draft" : "Balanced";
  const providers = [
    { label: "Local project", detail: "Autosaved", ok: true },
    { label: "OpenRouter", detail: "Script", ok: Boolean(system.openrouter) },
    { label: "Kokoro", detail: "Voice", ok: Boolean(system.kokoro) },
    { label: "Whisper", detail: "Captions · CPU", ok: Boolean(system.whisper) },
    { label: "Wan 2.2", detail: system.comfyui ? "Local hero shots" : "Optional · offline", ok: Boolean(system.comfyui) },
    { label: system.gpu_name || "NVIDIA GPU", detail: system.nvenc ? "NVENC" : "CPU fallback", ok: Boolean(system.gpu || system.ffmpeg) },
    { label: workspace === "viral" ? "1080×1920" : `${system.width || 1920}×${system.height || 1080}`, detail: `${system.fps || selectedProfile?.fps || 60} fps`, ok: true },
    { label: "$0 media API", detail: `${qualityLabel} · local + Pexels`, ok: true },
  ];
  return <footer className="provider-strip">{providers.map((provider) => <div className="provider-cell" key={provider.label}><StatusDot ok={provider.ok} /><span><strong>{provider.label}</strong><small>{provider.detail}</small></span></div>)}</footer>;
}

function GenerateDialog({ open, onClose, profiles, form, setForm, onSubmit, submitting, system }) {
  if (!open) return null;
  return <motion.div className="dialog-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}><motion.form className="generate-dialog" initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.98 }} onSubmit={onSubmit} onMouseDown={(event) => event.stopPropagation()}>
    <div className="dialog-head"><div><span className="eyebrow">Production setup</span><h2>Generate a complete film</h2><p>OpenRouter writes. Matching clips lead. Voice, exact captions, local hero shots, audio, and render stay on your machine.</p></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close setup"><X /></button></div>
    <div className="readiness-line"><span className={system.openrouter ? "ready" : "missing"}>{system.openrouter ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} OpenRouter</span><span className={system.pexels ? "ready" : "missing"}>{system.pexels ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Pexels Video</span><span className={system.comfyui ? "ready" : "missing"}>{system.comfyui ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Wan 2.2</span><span className={system.nvenc ? "ready" : "missing"}>{system.nvenc ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} NVENC</span><span className={system.kokoro ? "ready" : "missing"}>{system.kokoro ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} Kokoro</span></div>
    <label><span>Use case</span><select value={form.profile} onChange={(event) => setForm({ ...form, profile: event.target.value })}>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
    <label><span>Topic or angle <small>optional</small></span><textarea value={form.topic} onChange={(event) => setForm({ ...form, topic: event.target.value })} placeholder="Example: A calm, factual walkthrough of joining Atomy USA" rows="3" /></label>
    <div className="form-grid"><label><span>Length</span><select value={form.duration_minutes} onChange={(event) => setForm({ ...form, duration_minutes: Number(event.target.value) })}><option value="2">2 min preview</option><option value="5">5 minutes</option><option value="7">7 minutes</option><option value="10">10 minutes</option></select></label><label><span>Frame rate</span><select value={form.fps} onChange={(event) => setForm({ ...form, fps: Number(event.target.value) })}><option value="60">60 fps · smooth</option><option value="30">30 fps · faster</option></select></label><label><span>Render quality</span><select value={form.quality} onChange={(event) => setForm({ ...form, quality: event.target.value })}><option value="fast">Fast draft</option><option value="balanced">Balanced · recommended</option><option value="max">Maximum detail</option></select></label></div>
    <div className="form-grid voice-grid"><label><span>Voice engine</span><select value={form.voice_provider} onChange={(event) => setForm({ ...form, voice_provider: event.target.value })}><option value="kokoro">Kokoro · free local</option><option value="elevenlabs">ElevenLabs · premium jump</option><option value="openai">OpenAI · premium</option><option value="gemini">Gemini · premium</option></select></label><label><span>Voice character</span><select value={form.voice_profile} onChange={(event) => setForm({ ...form, voice_profile: event.target.value })}><option value="warm_documentary">Warm documentary</option><option value="confident_female">Confident female</option><option value="grounded_male">Grounded male</option><option value="editorial_blend">Editorial blend</option></select></label><label><span>Pace · {form.voice_speed.toFixed(2)}×</span><input type="range" min="0.8" max="1.2" step="0.01" value={form.voice_speed} onChange={(event) => setForm({ ...form, voice_speed: Number(event.target.value) })} /></label></div>
    <div className="toggle-row"><button type="button" className={form.stock_images ? "active" : ""} onClick={() => setForm({ ...form, stock_images: !form.stock_images })}><FilmReel /> Matching stock clips <span>{form.stock_images ? "On" : "Off"}</span></button><button type="button" className={form.local_ai ? "active" : ""} onClick={() => setForm({ ...form, local_ai: !form.local_ai })}><Sparkle weight="fill" /> Local Wan hero shot <span>{form.local_ai ? "On" : "Off"}</span></button><button type="button" className={form.captions ? "active" : ""} onClick={() => setForm({ ...form, captions: !form.captions })}><ClosedCaptioning /> Script-locked captions <span>{form.captions ? "On" : "Off"}</span></button></div>
    <div className="dialog-foot"><p><strong>Publishing is disabled.</strong> The finished video and thumbnail stay in your local output folder.</p><button className="primary-button" disabled={submitting || !system.openrouter}>{submitting ? <CircleNotch className="spin" /> : <Sparkle weight="fill" />} Start generation</button></div>
  </motion.form></motion.div>;
}

function RemotionLab({ form, setForm, system, startGeneration, submitting, activeJob, outputUrl, setToast }) {
  const [uploading, setUploading] = useState(false);
  const [music, setMusic] = useState(null);
  const inputRef = useRef(null);
  const beatMap = music?.beat_map;
  const duration = Math.min(form.music_seconds, beatMap?.duration_seconds || 30);
  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const result = await fetchJson("/api/music/uploads", { method: "POST", body: payload });
      setMusic(result);
      setForm((current) => ({ ...current, mode: "music_film", music_upload_id: result.upload_id, music_seconds: Math.min(60, Math.floor(result.beat_map.duration_seconds)) }));
      setToast(`Track mapped at ${Math.round(result.beat_map.bpm)} BPM`);
    } catch (error) { setToast(error.message); } finally { setUploading(false); }
  };
  const submit = (event) => {
    event.preventDefault();
    if (!music) { inputRef.current?.click(); return; }
    startGeneration(event);
  };
  return <main className="remotion-lab">
    <section className="remotion-preview panel-surface">
      <div className="lab-heading"><div><span className="eyebrow">Remotion motion lab</span><h1>Music-led faceless films</h1><p>The live composition reacts to your BPM. The final cut replaces this graphic proof with locally ranked race footage and one optional Wan hero shot.</p></div><span className="remotion-badge">FRAME-DETERMINISTIC</span></div>
      <div className="player-shell"><Suspense fallback={<div className="player-loading"><CircleNotch className="spin" /> Loading Remotion engine…</div>}><RemotionPreview duration={duration} music={music} title={form.music_title} bpm={beatMap?.bpm} /></Suspense></div>
      {outputUrl && <a className="latest-output" href={outputUrl} target="_blank" rel="noreferrer"><Play weight="fill" /> Open latest full render</a>}
    </section>
    <form className="music-console panel-surface" onSubmit={submit}>
      <div className="console-head"><div><span className="eyebrow">Master track</span><h2>Race Cut Director</h2></div><MusicNotes weight="duotone" /></div>
      <input ref={inputRef} className="visually-hidden" type="file" accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/flac,audio/ogg,.mp3,.wav,.m4a,.aac,.flac,.ogg" onChange={(event) => upload(event.target.files?.[0])} />
      <button type="button" className={`drop-track ${music ? "has-track" : ""}`} onClick={() => inputRef.current?.click()} disabled={uploading}>{uploading ? <CircleNotch className="spin" /> : music ? <CheckCircle weight="fill" /> : <UploadSimple />}<span><strong>{uploading ? "Analyzing rhythm…" : music?.filename || "Upload your final song"}</strong><small>{music ? `${Math.round(beatMap.duration_seconds)} sec · ${Math.round(beatMap.bpm)} BPM · ${beatMap.beats_seconds.length} beats` : "MP3, WAV, M4A, FLAC, AAC or OGG · stays local"}</small></span></button>
      {beatMap && <div className="beat-overview"><div><strong>{Math.round(beatMap.bpm)}</strong><small>BPM</small></div><div><strong>{beatMap.sections.filter((section) => section.label === "peak").length}</strong><small>Peak blocks</small></div><div><strong>{beatMap.downbeats_seconds.length}</strong><small>Downbeats</small></div></div>}
      <label><span>Event title</span><input value={form.music_title} onChange={(event) => setForm({ ...form, music_title: event.target.value })} /></label>
      <div className="form-grid music-options"><label><span>Render length</span><select value={form.music_seconds} onChange={(event) => setForm({ ...form, music_seconds: Number(event.target.value) })}><option value="30">30 sec teaser</option><option value="60">60 sec boss sample</option><option value="90">90 sec launch film</option><option value="180">3 min full track</option></select></label><label><span>Output</span><select value={form.fps} onChange={(event) => setForm({ ...form, fps: Number(event.target.value) })}><option value="60">1080p · 60 fps</option><option value="30">1080p · 30 fps draft</option></select></label></div>
      <div className="shot-stack"><span>Automatic shot grammar</span>{[["01", "Circuit geography", "Aerials and pit-lane orientation"], ["02", "Mechanical tension", "Wheel, brake, cockpit, helmet detail"], ["03", "Velocity release", "Tracking, cornering, side-by-side action"], ["04", "Event payoff", "Crowd, finish line, night-light closure"]].map(([index, title, note]) => <div key={index}><b>{index}</b><span><strong>{title}</strong><small>{note}</small></span></div>)}</div>
      <div className="toggle-row lab-toggles"><button type="button" className={form.local_ai ? "active" : ""} onClick={() => setForm({ ...form, local_ai: !form.local_ai })}><Sparkle weight="fill" /> Wan hero shot <span>{form.local_ai ? "1" : "0"}</span></button><button type="button" className={form.stock_images ? "active" : ""} onClick={() => setForm({ ...form, stock_images: !form.stock_images })}><FilmReel /> CLIP-ranked footage <span>{form.stock_images ? "On" : "Off"}</span></button></div>
      <p className="hardware-note"><StatusDot ok={system.nvenc} /> Beat analysis runs on CPU; CLIP ranking uses CPU; only the optional Wan shot occupies GPU VRAM. Final audio is your untouched master encoded at 320 kbps.</p>
      <button className="primary-button race-render" disabled={submitting || activeJob?.state === "running" || !music}>{submitting || activeJob?.state === "running" ? <CircleNotch className="spin" /> : <FilmReel weight="fill" />} {activeJob?.state === "running" ? "Building race cut…" : "Build beat-synced race film"}</button>
    </form>
  </main>;
}

function LogDrawer({ open, onClose, job, log, onCancel }) {
  return <AnimatePresence>{open && <motion.aside className="log-drawer" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 280 }}><div className="log-head"><div><span className="eyebrow">Generation log</span><h2>{job ? titleCase(job.state) : "No active job"}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close log"><X /></button></div>{job && <div className="job-meta"><span>Job {job.job_id}</span><span>{job.profile}</span>{job.pid && <span>PID {job.pid}</span>}</div>}<pre>{log || "The log will appear here once generation starts."}</pre>{job?.state === "running" && <button className="danger-button" onClick={onCancel}><StopCircle /> Cancel generation</button>}</motion.aside>}</AnimatePresence>;
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
  const [log, setLog] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState("");
  const [workspace, setWorkspace] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get("workspace");
    return ["editor", "remotion", "viral"].includes(requested) ? requested : "editor";
  });
  const [form, setForm] = useState({ profile: "atomy-us-openrouter", topic: "", duration_minutes: 7, fps: 60, quality: "balanced", stock_images: true, local_ai: true, captions: true, fresh: true, mode: "faceless_narrated", music_upload_id: null, music_title: "Sepang Track Experience", music_seconds: 60, voice_provider: "kokoro", voice_profile: "warm_documentary", voice_speed: 0.98, viral_recipe: "beat_creature", viral_prompt: "", viral_provider: "local_wan", viral_seconds: 5, reference_upload_id: null, dialogue_a: "", dialogue_b: "" });

  const selectedScene = scenes.find((scene) => scene.id === selectedId) || scenes[0];
  const selectedProfile = profiles.find((profile) => profile.id === form.profile) || profiles[0];
  const totalDuration = scenes.reduce((sum, scene) => sum + scene.duration, 0);
  const activeJob = jobs.find((job) => ["queued", "running"].includes(job.state)) || jobs[0] || null;
  const editorialRun = runs.find((run) => (run.pipeline_kind || "narrated") === "narrated") || null;
  const desiredPipeline = workspace === "viral" ? "viral_short" : workspace === "remotion" ? "music_film" : "narrated";
  const latestRun = runs.find((run) => (run.pipeline_kind || "narrated") === desiredPipeline) || null;
  const outputUrl = latestRun && ["ready", "published"].includes(latestRun.status) ? `/api/runs/${latestRun.run_id}/video` : null;

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
    const mode = workspace === "viral" ? "viral_short" : workspace === "remotion" ? "music_film" : "faceless_narrated";
    setForm((current) => current.mode === mode ? current : { ...current, mode });
  }, [workspace]);
  useEffect(() => { if (!playing) return undefined; const timer = window.setInterval(() => setPlayhead((current) => current + 1 >= totalDuration ? 0 : current + 1), 100); return () => window.clearInterval(timer); }, [playing, totalDuration]);
  useEffect(() => { if (!activeJob || !logOpen) return undefined; const loadLog = () => fetchJson(`/api/jobs/${activeJob.job_id}/log`).then((data) => setLog(data.log)).catch(() => {}); loadLog(); const timer = window.setInterval(loadLog, 2000); return () => window.clearInterval(timer); }, [activeJob?.job_id, logOpen]);
  useEffect(() => { if (!toast) return undefined; const timer = window.setTimeout(() => setToast(""), 3200); return () => window.clearTimeout(timer); }, [toast]);
  useEffect(() => {
    if (!latestRun?.run_id) { setRunDetail(null); return; }
    fetchJson(`/api/runs/${latestRun.run_id}`).then(setRunDetail).catch(() => setRunDetail(null));
  }, [latestRun?.run_id]);
  useEffect(() => { const profile = profiles.find((item) => item.id === form.profile); if (profile && !submitting) setForm((current) => ({ ...current, duration_minutes: profile.duration_minutes || current.duration_minutes, fps: profile.fps || current.fps })); }, [form.profile, profiles]);
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
  const startGeneration = async (event) => {
    event?.preventDefault(); setSubmitting(true);
    try {
      const created = await fetchJson("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, topic: form.topic.trim() || null }) });
      setJobs((current) => [created, ...current]); setSetupOpen(false); setLogOpen(true); setToast("Generation started — publishing remains off");
    } catch (error) { setToast(error.message); } finally { setSubmitting(false); }
  };
  const cancelJob = async () => {
    if (!activeJob) return;
    try { const cancelled = await fetchJson(`/api/jobs/${activeJob.job_id}/cancel`, { method: "POST" }); setJobs((current) => current.map((job) => job.job_id === cancelled.job_id ? cancelled : job)); setToast("Generation cancelled safely"); } catch (error) { setToast(error.message); }
  };
  const addScene = () => { const next = { ...initialScenes.at(-1), id: scenes.length + 1, title: "New supporting scene", caption: "Add one clear idea for this moment.", duration: 30 }; setScenes((current) => [...current, next]); setSelectedId(next.id); setToast("Scene added to the working storyboard"); };
  const lastRunLabel = latestRun ? `${titleCase(latestRun.status)} · ${latestRun.publication_date}` : "No renders yet";

  return <div className="studio-shell">
    <header className="topbar"><button className="menu-button" aria-label="Open menu"><List /></button><BrandMark /><div className="workspace-switch"><button className={workspace === "editor" ? "active" : ""} onClick={() => { setWorkspace("editor"); setForm((current) => ({ ...current, mode: "faceless_narrated" })); }}>Editorial</button><button className={workspace === "remotion" ? "active" : ""} onClick={() => { setWorkspace("remotion"); setForm((current) => ({ ...current, mode: "music_film" })); }}><Waveform /> Remotion Lab</button><button className={workspace === "viral" ? "active" : ""} onClick={() => { setWorkspace("viral"); setForm((current) => ({ ...current, mode: "viral_short" })); }}><Sparkle weight="fill" /> AI Viral Lab</button></div><div className="project-title"><strong>{workspace === "remotion" ? form.music_title : workspace === "viral" ? "AI-native viral short" : selectedProfile?.name || "AtlasForge project"}</strong><StatusDot ok /><span>Autosaved</span></div>{workspace === "editor" && <label className="usecase-select"><span>Use case</span><select value={form.profile} onChange={(event) => setForm({ ...form, profile: event.target.value })}>{profiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.name}</option>)}</select><CaretDown /></label>}<button className="primary-button generate-button" onClick={() => workspace === "remotion" ? document.querySelector(".drop-track")?.click() : workspace === "viral" ? document.querySelector(".viral-prompt textarea")?.focus() : setSetupOpen(true)} disabled={activeJob?.state === "running"}><Sparkle weight="fill" /> {activeJob?.state === "running" ? "Generating…" : workspace === "remotion" ? "Load song" : workspace === "viral" ? "Direct shot" : "Generate film"}</button><span className="shortcut"><Command />K</span><button className="top-icon" title="Help" aria-label="Help"><Question /></button><button className="top-icon" title="Notifications" aria-label="Notifications"><Bell /></button><div className="avatar" title="Local owner">AF</div></header>
    <div className="stagebar"><StageRail stages={runDetail?.stages || []} activeJob={activeJob?.state === "running" ? activeJob : null} /><div className="last-run"><span>Last run: {lastRunLabel}</span><button className="secondary-button" onClick={() => setLogOpen(true)}>View log <CaretRight /></button></div></div>
    {workspace === "editor" ? <main className="editor-grid"><ChapterRail scenes={scenes} selectedId={selectedId} onSelect={setSelectedId} activeTab={activeTab} setActiveTab={setActiveTab} onAddScene={addScene} /><div className="edit-canvas"><Preview scene={selectedScene} playing={playing} setPlaying={setPlaying} playhead={playhead} setPlayhead={setPlayhead} totalDuration={totalDuration} outputUrl={outputUrl} /><Timeline scenes={scenes} selectedId={selectedId} onSelect={setSelectedId} playhead={playhead} setPlayhead={setPlayhead} /></div><SceneInspector scene={selectedScene} sceneCount={scenes.length} onChange={updateScene} onRegenerate={() => setSetupOpen(true)} busy={activeJob?.state === "running"} /></main> : workspace === "remotion" ? <RemotionLab form={form} setForm={setForm} system={system} startGeneration={startGeneration} submitting={submitting} activeJob={activeJob} outputUrl={outputUrl} setToast={setToast} /> : <Suspense fallback={<main className="viral-lab"><div className="panel-surface player-loading"><CircleNotch className="spin" /> Loading AI Viral Lab…</div></main>}><ViralLab form={form} setForm={setForm} system={system} startGeneration={startGeneration} submitting={submitting} activeJob={activeJob} outputUrl={outputUrl} setToast={setToast} /></Suspense>}
    <ProviderStrip system={system} selectedProfile={selectedProfile} quality={form.quality} workspace={workspace} />
    <AnimatePresence><GenerateDialog open={setupOpen} onClose={() => setSetupOpen(false)} profiles={profiles} form={form} setForm={setForm} onSubmit={startGeneration} submitting={submitting} system={system} /></AnimatePresence><LogDrawer open={logOpen} onClose={() => setLogOpen(false)} job={activeJob} log={log} onCancel={cancelJob} />
    <AnimatePresence>{toast && <motion.div className="toast" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}><CheckCircle weight="fill" /> {toast}</motion.div>}</AnimatePresence>
  </div>;
}

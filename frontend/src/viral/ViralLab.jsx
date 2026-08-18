import { lazy, Suspense, useRef, useState } from "react";
import {
  Buildings, ChatCircleDots, CheckCircle, CircleNotch, Cloud, FilmReel,
  Gauge, Image as ImageIcon, MusicNotes, Sparkle, UploadSimple, Warning,
} from "@phosphor-icons/react";

const ViralPreview = lazy(() => import("../remotion/ViralPreview"));

const recipes = [
  { id: "cinematic_insert", icon: FilmReel, title: "Cinematic Insert", note: "Reference-led car, product or environment shot with restrained believable motion." },
  { id: "beat_creature", icon: Sparkle, title: "Beat Creature", note: "Reference-led animal or character performance, choreographed to your song." },
  { id: "talking_duo", icon: ChatCircleDots, title: "Talking Duo", note: "Native voices, turn-taking and lip sync for fictional characters." },
  { id: "physics_spectacle", icon: Buildings, title: "Physics Spectacle", note: "Fictional destruction, believable mass, dust, impacts and camera response." },
];

const providers = [
  { id: "local_wan", title: "Free Local", model: "Real plate → Wan 2.2 → RIFE", cost: "$0", note: "Pexels/uploaded plate first · best-of seeds · strict admission gate" },
  { id: "gemini_omni", title: "Native Realism", model: "Gemini Omni Flash", cost: "$0.10/s", note: "Image continuity · native voices · coherent motion" },
  { id: "veo", title: "Budget Native", model: "Veo 3.1 Lite", cost: "$0.05/s", note: "Native audio · lower cost · prompt-led generation" },
];

const promptHints = {
  cinematic_insert: "An unbranded silver GT race car remains parked alone in a clean wet pit lane at blue hour while light rain and soft practical reflections move naturally; locked low camera, no people.",
  beat_creature: "A ginger cat in a miniature racing suit performs crisp footwork in a glossy pit garage; low tracking camera, warm practical lights, playful confidence.",
  talking_duo: "Two fictional expressive baby characters sit opposite each other in a softly lit premium podcast nook and trade one playful observation.",
  physics_spectacle: "An empty futuristic parking structure folds inward in a controlled chain reaction at blue hour; wide locked lens, volumetric dust and realistic debris.",
};

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

export default function ViralLab({ form, setForm, system, startGeneration, submitting, activeJob, outputUrl, setToast, runDetail, labMode = "viral" }) {
  const referenceInput = useRef(null);
  const musicInput = useRef(null);
  const [reference, setReference] = useState(null);
  const [music, setMusic] = useState(null);
  const [uploading, setUploading] = useState("");
  const selectedProvider = providers.find((item) => item.id === form.viral_provider) || providers[0];
  const cloudReady = Boolean(system.gemini_omni);
  const providerReady = form.viral_provider === "local_wan" ? Boolean(system.comfyui) : cloudReady;
  const expectedCost = form.viral_provider === "local_wan" ? 0 : form.viral_seconds * (form.viral_provider === "veo" ? .05 : .1);
  const needsMusic = form.viral_recipe === "beat_creature";
  const needsDialogue = form.viral_recipe === "talking_duo";
  const canSubmit = Boolean(providerReady && (!needsMusic || music) && (!needsDialogue || (form.dialogue_a.trim() && form.dialogue_b.trim())) && form.viral_prompt.trim());
  const promptHint = promptHints[form.viral_recipe];
  const admission = runDetail?.ai_quality;
  const isGenerationLab = labMode === "generation";

  const upload = async (file, kind) => {
    if (!file) return;
    setUploading(kind);
    const payload = new FormData();
    payload.append("file", file);
    try {
      const result = await requestJson(kind === "music" ? "/api/music/uploads" : "/api/reference/uploads", { method: "POST", body: payload });
      if (kind === "music") {
        setMusic(result);
        setForm((current) => ({ ...current, music_upload_id: result.upload_id }));
        setToast(`Music locked at ${Math.round(result.beat_map.bpm)} BPM`);
      } else {
        setReference(result);
        setForm((current) => ({ ...current, reference_upload_id: result.upload_id }));
        setToast(`Reference locked · ${result.width}×${result.height}`);
      }
    } catch (error) { setToast(error.message); } finally { setUploading(""); }
  };

  const selectRecipe = (recipe) => {
    setForm((current) => ({
      ...current,
      mode: "viral_short",
      viral_recipe: recipe,
      viral_provider: recipe === "talking_duo" && current.viral_provider === "local_wan" ? "gemini_omni" : current.viral_provider,
    }));
  };

  const submit = (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    startGeneration(event);
  };

  return <main className="viral-lab">
    <section className="viral-director panel-surface">
      <div className="viral-heading"><div><span className="eyebrow">{isGenerationLab ? "Isolated synthetic candidate workshop" : "AI-native one-shot studio"}</span><h1>{isGenerationLab ? "Generate here. Admit nowhere automatically." : "Impossible shots. Coherent subjects."}</h1><p>{isGenerationLab ? "This separate workspace creates and audits local AI candidates. A candidate remains quarantined unless real footage was unavailable and every admission check passes." : "The local chain starts from a real licensed or uploaded plate whenever possible, ranks multiple seeds, then uses neural interpolation only after motion survives the realism gate."}</p></div><span className="synthetic-badge"><Sparkle weight="fill" /> SYNTHETIC MEDIA</span></div>
      <div className="viral-stage">
        <div className="phone-frame"><Suspense fallback={<div className="viral-player-loading"><CircleNotch className="spin" /> Loading motion previsualization…</div>}><ViralPreview recipe={form.viral_recipe} concept={form.viral_prompt || promptHint} music={music} reference={reference} seconds={form.viral_seconds} /></Suspense></div>
        <div className="continuity-stack">
          <span className="eyebrow">Continuity stack</span>
          {["One continuous shot", reference ? "Uploaded identity locked" : "Real Pexels plate first · SDXL fallback", music ? `${Math.round(music.beat_map.bpm)} BPM master attached` : "Audio input optional", `${form.viral_candidates || 2} seeds ranked locally`, "Synthetic provenance saved"].map((item) => <div key={item}><CheckCircle weight="fill" /><span>{item}</span></div>)}
          {admission && <div className={`admission-chip ${admission.decision === "accepted" ? "accepted" : "quarantined"}`}><strong>{String(admission.decision).toUpperCase()}</strong><span>{Math.round((admission.selected_score || 0) * 100)} / 100 admission score</span></div>}
          {outputUrl && <a className="latest-output" href={outputUrl} target="_blank" rel="noreferrer"><FilmReel weight="fill" /> Open latest finished render</a>}
        </div>
      </div>
    </section>

    <form className="viral-console panel-surface" onSubmit={submit}>
      <div className="console-head"><div><span className="eyebrow">{isGenerationLab ? "Candidate generator" : "Reality director"}</span><h2>{isGenerationLab ? "AI Generation Lab" : "Viral Shot Lab"}</h2></div><Gauge weight="duotone" /></div>
      <div className="recipe-grid">{recipes.map(({ id, icon: Icon, title, note }) => <button type="button" key={id} className={form.viral_recipe === id ? "active" : ""} onClick={() => selectRecipe(id)}><Icon weight="duotone" /><span><strong>{title}</strong><small>{note}</small></span></button>)}</div>
      <label className="viral-prompt"><span>Shot concept</span><textarea value={form.viral_prompt} placeholder={promptHint} onChange={(event) => setForm({ ...form, viral_prompt: event.target.value })} /></label>

      {needsDialogue && <div className="dialogue-pair"><label><span>Speaker A · exact line</span><input value={form.dialogue_a} placeholder="Did you hear what happened?" onChange={(event) => setForm({ ...form, dialogue_a: event.target.value })} /></label><label><span>Speaker B · exact reply</span><input value={form.dialogue_b} placeholder="I was literally there." onChange={(event) => setForm({ ...form, dialogue_b: event.target.value })} /></label></div>}

      <div className="viral-uploads">
        <input ref={referenceInput} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => upload(event.target.files?.[0], "reference")} />
        <button type="button" onClick={() => referenceInput.current?.click()} className={reference ? "attached" : ""} disabled={Boolean(uploading)}>{uploading === "reference" ? <CircleNotch className="spin" /> : reference ? <img src={reference.image_url} alt="Uploaded subject reference" /> : <ImageIcon />}<span><strong>{reference?.filename || "Optional reference override"}</strong><small>{reference ? `${reference.width}×${reference.height} · identity source` : "Omit it: a real Pexels plate is searched first; SDXL is fallback only"}</small></span></button>
        <input ref={musicInput} className="visually-hidden" type="file" accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/flac,audio/ogg,.mp3,.wav,.m4a,.aac,.flac,.ogg" onChange={(event) => upload(event.target.files?.[0], "music")} />
        <button type="button" onClick={() => musicInput.current?.click()} className={music ? "attached" : ""} disabled={Boolean(uploading)}>{uploading === "music" ? <CircleNotch className="spin" /> : music ? <CheckCircle weight="fill" /> : <MusicNotes />}<span><strong>{music?.filename || (needsMusic ? "Master song · required" : "Optional music")}</strong><small>{music ? `${Math.round(music.beat_map.bpm)} BPM · passed to timing engine` : "Original audio remains untouched in final master"}</small></span></button>
      </div>

      <span className="console-label">Reality lane</span>
      <div className="provider-lanes">{providers.map((provider) => {
        const ready = provider.id === "local_wan" ? system.comfyui : cloudReady;
        const blocked = needsDialogue && provider.id === "local_wan";
        return <button type="button" key={provider.id} disabled={blocked} className={form.viral_provider === provider.id ? "active" : ""} onClick={() => setForm({ ...form, viral_provider: provider.id })}><span className="lane-top"><strong>{provider.title}</strong><b>{provider.cost}</b></span><span className="lane-model">{provider.id === "local_wan" ? <Gauge /> : <Cloud />} {provider.model}</span><small>{blocked ? "Not honest for exact local lip sync" : provider.note}</small><span className={`lane-status ${ready ? "ready" : ""}`}>{ready ? "READY" : provider.id === "local_wan" ? "START COMFYUI" : "ADD GOOGLE KEY"}</span></button>;
      })}</div>

      <div className="viral-master-row"><label><span>Shot length</span><select value={form.viral_seconds} onChange={(event) => setForm({ ...form, viral_seconds: Number(event.target.value) })}><option value="5">5 seconds · strongest local</option><option value="8">8 seconds · story beat</option><option value="10">10 seconds · maximum</option></select></label><label><span>Local detail</span><select value={form.quality} onChange={(event) => setForm({ ...form, quality: event.target.value })}><option value="fast">Fast · 512×896</option><option value="balanced">Balanced · 576×1024</option><option value="max">Maximum · 640×1136</option></select></label><label><span>Candidate seeds</span><select value={form.viral_candidates || 2} onChange={(event) => setForm({ ...form, viral_candidates: Number(event.target.value) })}><option value="1">1 · fastest</option><option value="2">2 · recommended</option><option value="3">3 · maximum search</option></select></label></div>
      <div className="cost-meter ai-cost"><span>Estimated generation</span><strong>{expectedCost ? `$${expectedCost.toFixed(2)}` : "$0.00"}</strong><small>{expectedCost ? "before tax · cloud clip" : `${form.viral_candidates || 2} local candidate${(form.viral_candidates || 2) > 1 ? "s" : ""} · electricity only`}</small></div>
      <div className="admission-panel"><span className="console-label">Strict admission gate</span><div>{[["Isolated from editorial", true], ["Reference preserved", admission?.candidates?.[admission.selected_candidate - 1]?.checks?.reference_preserved], ["Sharp and exposure-safe", admission?.candidates?.[admission.selected_candidate - 1]?.checks?.sharp_enough && admission?.candidates?.[admission.selected_candidate - 1]?.checks?.exposure_safe], ["No light/color flash or cut", admission?.candidates?.[admission.selected_candidate - 1]?.checks?.no_brightness_flicker && admission?.candidates?.[admission.selected_candidate - 1]?.checks?.no_color_flash && admission?.candidates?.[admission.selected_candidate - 1]?.checks?.no_hard_scene_cut], ["Coherent real motion", admission?.candidates?.[admission.selected_candidate - 1]?.checks?.has_coherent_motion], ["Physics and anatomy supervisor", admission?.candidates?.[admission.selected_candidate - 1]?.checks?.semantic_realism]].map(([label, passed]) => <span key={label} className={passed ? "pass" : admission ? "fail" : "pending"}>{passed ? <CheckCircle weight="fill" /> : <Warning weight="fill" />} {label}</span>)}</div><p>AI Lab output is never inserted into an editorial film automatically. A real clip has priority; a failed candidate stays available only for inspection.</p></div>
      <div className={`truth-callout ${providerReady ? "ready" : ""}`}>{providerReady ? <CheckCircle weight="fill" /> : <Warning weight="fill" />}<p><strong>{selectedProvider.model}</strong>{form.viral_provider === "local_wan" ? " is the best officially supported lane that fits this 8 GB GPU comfortably. It now begins with real photographic pixels, uses conservative OpenRouter direction, compares multiple seeds, and quarantines candidates with blur, flicker, cuts, weak motion, reference drift, or low camera-realism scores. It can still fail at subtle anatomy or physics, so no local result is described as guaranteed real." : " can generate native synchronized audio and stronger temporal coherence. Your prompt and optional image go to Google only when you press Generate; the song stays local, supplies BPM timing, and is muxed afterward."}</p></div>
      <button className="primary-button viral-generate" disabled={!canSubmit || submitting || activeJob?.state === "running"}>{submitting || activeJob?.state === "running" ? <CircleNotch className="spin" /> : <Sparkle weight="fill" />} {activeJob?.state === "running" ? "Generating coherent shot…" : canSubmit ? isGenerationLab ? "Generate and audit candidates" : "Generate viral master" : !providerReady ? "Provider needs setup" : needsMusic && !music ? "Attach the master song" : "Complete the shot brief"}</button>
      <p className="no-publish"><Warning /> Publishing remains disabled. Never present physics spectacle footage as real news or documentary evidence.</p>
    </form>
  </main>;
}

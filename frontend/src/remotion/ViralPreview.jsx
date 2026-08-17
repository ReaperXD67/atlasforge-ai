import { Player } from "@remotion/player";

import { ViralConcept } from "./ViralConcept";

export default function ViralPreview({ recipe, concept, music, reference, seconds }) {
  return <Player
    component={ViralConcept}
    durationInFrames={Math.max(180, Math.round(seconds * 60))}
    compositionWidth={1080}
    compositionHeight={1920}
    fps={60}
    controls
    inputProps={{
      recipe,
      concept,
      audioUrl: music?.audio_url || null,
      bpm: music?.beat_map?.bpm || 120,
      referenceUrl: reference?.image_url || null,
    }}
    style={{ width: "100%", aspectRatio: "9 / 16" }}
  />;
}

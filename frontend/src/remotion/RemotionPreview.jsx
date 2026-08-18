import { Player } from "@remotion/player";

import { RacingPulse } from "./RacingPulse";

export default function RemotionPreview({ duration, music, title, bpm }) {
  return <Player
    component={RacingPulse}
    durationInFrames={Math.max(60, Math.round(duration * 60))}
    compositionWidth={1920}
    compositionHeight={1080}
    fps={60}
    controls
    inputProps={{ audioUrl: music?.audio_url || null, title, bpm: bpm || 128 }}
    style={{ width: "100%", aspectRatio: "16 / 9" }}
  />;
}

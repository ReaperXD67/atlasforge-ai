import { memo, useCallback, useMemo } from "react";
import { Player } from "@remotion/player";

import { RacingPulse } from "./RacingPulse";

const PREVIEW_FPS = 30;

function RemotionPreview({ duration, music, title, brand, beatMap, editStyle, hookWords, visualDirection }) {
  const inputProps = useMemo(() => ({
    audioUrl: music?.audio_url || null,
    title,
    brand,
    beatMap: beatMap || null,
    editStyle,
    hookWords,
    visualDirection,
  }), [music?.audio_url, title, brand, beatMap, editStyle, hookWords, visualDirection]);
  const renderPoster = useCallback(({ isBuffering }) => isBuffering ? <div className="remotion-buffer"><span /><strong>Buffering audio map…</strong></div> : null, []);

  return <Player
    component={RacingPulse}
    durationInFrames={Math.max(PREVIEW_FPS, Math.round(duration * PREVIEW_FPS))}
    compositionWidth={1920}
    compositionHeight={1080}
    fps={PREVIEW_FPS}
    controls
    playbackRate={1}
    inputProps={inputProps}
    bufferStateDelayInMilliseconds={80}
    renderPoster={renderPoster}
    showPosterWhenBuffering
    showPosterWhenBufferingAndPaused
    _experimentalKeepAudioContextAlive
    acknowledgeRemotionLicense
    logLevel="warn"
    style={{ width: "100%", aspectRatio: "16 / 9" }}
  />;
}

export default memo(RemotionPreview);

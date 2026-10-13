# For my Sweetheart

A 6:12.76 fifth-month anniversary music film: 42 lyric-directed shots, six generated plates, two approved locally generated Wan motion clips across six inserts, deterministic cosmic worlds, real shared-photo memories, and 122 measured subtitles.

The original song remains the audio master. The generated images, song, photograph, subtitle text, and `film-data.js` are local inputs excluded from Git.

The lily and flower-ocean motion candidates were rejected during exported-film review: the lily abruptly changed framing and focus, while the flower ocean introduced flashing blue bands even after deflickering. Their four planned inserts use the approved image plates with deterministic camera and atmosphere movement. The stairway and shattered-moon clips remain admitted.

## Rebuild

1. Supply the approved image set in `output/sweetheart-assets/`, the master at `assets/bgm.wav`, and the photograph at `assets/private/couple.jpg`.
2. Place aligned `captions.json` and `captions.srt` in this project. Cue shape: `{start,end,text,section,confidence}`. The supplied-lyric alignment uses AtlasForge's lyric engine and focused transcription of quiet passages.
3. Run `.venv/Scripts/python.exe videos/for-my-sweetheart/prepare.py` from the repository root.
4. Run `npm run check`, then `npm run dev` from this folder to inspect the full film.
5. Run `videos/for-my-sweetheart/render.ps1` from the repository root for the hardware browser/GPU H.264 render profile. It defaults to one worker: the full production export required an automatic single-worker retry after parallel browser startup failures. HyperFrames probes the available hardware encoder. The existing `scripts/render_hyperframes_windows.ps1` remains the conservative software-browser fallback.
6. Run `.venv/Scripts/python.exe videos/for-my-sweetheart/verify_delivery.py videos/for-my-sweetheart/renders/For-my-Sweetheart-Anniversary.mp4` to check the complete export, original audio alignment, and cue bounds.
7. Run `videos/for-my-sweetheart/share.ps1` for a 720p H.264/AAC copy with fast-start playback and capped video bitrate.

Every frame is derived from absolute song time. `scene-plan.json` holds the edit; `cinema.js` draws plates and subtitles; `atmosphere.js` builds seeded cosmic and weather motion. This permits exact seeking and repeatable exports without clocks, live APIs, or random frame state.

The musical map records a Windows-compatible FFmpeg/SciPy fallback. Its rhythm grid is estimated; the film follows measured vocal phrases rather than claiming exact beat cuts. All assets load locally before the registered timeline becomes ready.

## Verified delivery

The full production export is 372.766667 seconds, 1920 by 1080 at 30 fps, H.264 with 48 kHz stereo AAC. All 11,183 frames decode successfully. The exported audio correlates 0.998994 with the original master at the same sample positions. All 122 subtitle cues are in bounds and do not overlap. HyperFrames runtime, layout, and contrast checks passed before export. The local `renders/delivery-verification.json` records the machine-readable results.

The reviewed delivery uses `polish_delivery.py` to replace four rejected motion windows with short, validated renders of the corrected composition. It checks exact patch frame counts and preserves the original encoded audio payload byte for byte. A fresh full render already contains these corrections and does not need this optional repair step. The 720p sharing profile can also be checked with `verify_delivery.py --share`.

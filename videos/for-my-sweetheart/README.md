# For my Sweetheart

A 6:12.76 fifth-month anniversary music film: 42 lyric-directed shots, six generated plates, four locally generated Wan motion clips across ten inserts, deterministic cosmic worlds, real shared-photo memories, and 122 measured subtitles.

The original song remains the audio master. The generated images, song, photograph, subtitle text, and `film-data.js` are local inputs excluded from Git.

## Rebuild

1. Supply the approved image set in `output/sweetheart-assets/`, the master at `assets/bgm.wav`, and the photograph at `assets/private/couple.jpg`.
2. Place aligned `captions.json` and `captions.srt` in this project. Cue shape: `{start,end,text,section,confidence}`. The supplied-lyric alignment uses AtlasForge's lyric engine and focused transcription of quiet passages.
3. Run `.venv/Scripts/python.exe videos/for-my-sweetheart/prepare.py` from the repository root.
4. Run `npm run check`, then `npm run dev` from this folder to inspect the full film.
5. Run `videos/for-my-sweetheart/render.ps1` from the repository root for the validated hardware-GPU/NVENC render profile. The existing `scripts/render_hyperframes_windows.ps1` remains the conservative software-browser fallback.

Every frame is derived from absolute song time. `scene-plan.json` holds the edit; `cinema.js` draws plates and subtitles; `atmosphere.js` builds seeded cosmic and weather motion. This permits exact seeking and repeatable exports without clocks, live APIs, or random frame state.

The musical map records a Windows-compatible FFmpeg/SciPy fallback. Its rhythm grid is estimated; the film follows measured vocal phrases rather than claiming exact beat cuts. All assets load locally before the registered timeline becomes ready.

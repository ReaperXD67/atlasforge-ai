---
name: stock-music-film
description: Author, rebuild, or review a full-song AtlasForge music film from curated licensed footage when the supplied song sets the edit and the project uses the stock_film renderer.
---

# Stock music film

Use the repository's stock footage renderer for a linear edit built from licensed clips and one supplied song master. The music film guide documents the command and manifest. [Music film workflow](../../../docs/MUSIC_VIDEO.md#authored-stock-music-films)

1. Probe the original song and keep its SHA-256 in the edit. Measure structural and vocal cues on the actual recording. If the beat grid is uncertain, place cuts on audible phrases and section changes.
2. Find an editorial motif that can recur across the full song. Review complete candidate source windows for motion, internal cuts, cropping, visible branding, and casting continuity. When stock actors differ, use silhouettes, hands, reflections, and details to imply the story without implying they are the same person.
3. Record each selected clip's exact CDN variant, hash, safe filename, original page, creator where available, and license. Use the correct license for the individual item. Keep source clips and the song in local storage. The renderer stages only pinned assets and uses the song as the sole audio stream.
4. Author adjacent `start` and `end` frame numbers at 24 fps. Keep the source range in bounds after `speed`. Set the crop focal point for each shot and review it inside the 1920 × 804 active picture. Use fades where a real pause or visual resolution warrants one.
5. Render with the same work directory during revisions so unchanged shots reuse their encoded segments. Read the verification JSON for full decode, exact frame count, and zero-offset soundtrack comparison. Review the film with sound for pacing and continuity, including the quietest passage, the main musical lifts, and the ending. Fix issues in the edit and rerun.
6. When the user requests GitHub delivery, commit the edit, source credits, and rebuild instructions. Use a release asset for the finished MP4 when publication is authorized. Keep the original audio master and standalone stock clips out of Git and the release.

# Media provenance

The cinematic revision uses moving footage throughout. [STOCK_CREDITS.md](STOCK_CREDITS.md) identifies all nine Pexels sources, creators, source pages and selected windows under the [Pexels License](https://www.pexels.com/license/). `motion-assets.json` pins all 20 silent derived files, original/derived SHA-256 hashes, exact crops/grades, source windows and reviewed usable ranges. The footage illustrates a celebration; it is not presented as documentary coverage of a Bosston event or as an endorsement by the people shown.

- Soundtrack: supplied `Boston Pragon 好运来 (1).wav`, 185.000 seconds, 48 kHz stereo PCM16. The original filename is retained. The song is the only audio stream; stock audio is removed.
- Brand: only the top-left B emblem and BOSSTON | Pragon wordmark from the supplied reference were isolated onto transparency with ImageGen. Its character, Chinese poster text and 2027 banner are not used.
- Display spelling: the user's correction to **Bosston** overrides the earlier pasted Boston spelling. All nine lyric occurrences and word records were corrected without changing their measured times, confidence or sections. Raw ASR evidence retains the recognized spelling.
- Finish: local FFmpeg crops, a restrained warm grade, H.264/yuv420p/BT.709 1080p30 preparation and an original lower-picture lyric veil. Source frame conversion uses duplication/drop, not generated optical-flow frames.
- Typography: Noto Serif CJK SC 2.003 under SIL OFL 1.1. [Font provenance and notices](assets/fonts/README.md)
- Runtime: local GSAP and pinned HyperFrames 0.8.152. HyperFrames owns all footage seeking and soundtrack playback. The short line entrance in `captions.js` adapts the inspected registry clip-wipe idea; estimated syllable times are not advertised as exact karaoke.

The seven generated image plates and experimental Three.js worlds belong to the earlier creative studies. They remain local source material but are not loaded in this revision. Blender 4.5.16 LTS was downloaded from its official publisher, checksum/signature checked and installed, but existing Windows signing policy blocks a bundled DLL before launch. The local Wan runtime is also policy-blocked. Neither generated media for this cut; no security settings were changed.

`asset-hashes.json` and the final delivery receipt record the actual local inputs and encoded output. Standalone source clips, original audio and large local assets remain outside Git.

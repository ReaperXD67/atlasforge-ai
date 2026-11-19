# Media provenance

**Recipient confirmed by the user:** this song is for Hock Siew / 拿督斯里谢惠福, identified by the user in the seaside photograph. The later Benz song will be a separate project. The chat labels the dark-coat portrait “benz”; that portrait is not used here. This mapping comes from the user's confirmation, not face-based identification.

The user's latest `有你，兄弟同心 (1).wav` is the sole soundtrack. Its earlier unnumbered copy is byte-identical. The staged `assets/bgm.wav` is 196.760 seconds, 48kHz stereo PCM16; SHA-256 `60ee65f074f36b2d31660bee652e111cd84538e51b74a0685cbd895291cd6547`. The edit preserves its speed, start and gain. Generated sources contain no selected audio, and no extra music or sound effects are mixed over this personal recording.

## Supplied photographs

| Original filename | Local source | Use / SHA-256 |
| --- | --- | --- |
| `photo_2026-11-19_14-36-56.jpg` | `assets/photos/brothers.jpg` | Reference for the short native group-photo animation; original hash `f689bf5ee345970581f6839c0afbc8b8347fd06b9454732680452e79e2e901ae`. |
| `photo_2026-11-19_14-36-47.jpg` | `assets/photos/seaside.jpg` | Original unretouched final dedication image, entirely fitted within the left side; hash `f82de273f4ca26487851dd402ecc7557c190c5f4af1c6dbeaca69f0fefa55b71`. A blurred duplicate supplies the background. |
| `photo_2026-11-19_14-37-02.jpg` | `assets/photos/portrait.jpg` | Preserved locally as supplied; not used in the final edit. Hash `e7c454849bbcac0851f7e6e01efcee5ef0805513a9f467ea0f584279da54bbb2`. |

Photographs were supplied for this tribute. The generated group movement is an AI interpretation, with faces, clothing and venue checked against the original. Fictional performers in the main scenes symbolise the lyrics; the film does not establish that those generated acts are documentary footage of Hock Siew.

## Native moving footage

[generation-jobs.json](generation-jobs.json) retains exact submitted prompts, task IDs, costs and output hashes. [native-clips.json](native-clips.json) binds the local files and admitted source ranges. Twelve Gen-4.5 text-to-video takes cost 1,440 credits; eight Turbo image-to-video takes cost 400; the 7-second real-photo Gen-4.5 animation cost 84. The workspace moved from 2,250 to **326 existing credits**. The final balance was read after all jobs completed. No top-up was made.

Eight AI-created still plates were produced with the built-in image generation tool, inspected and used only as starting frames for native Turbo clips. The final film selects the moving MP4 results, with independent people, cloth, hand, rain and water motion. Text is set locally in ASS, never entrusted to generated scenery. Native sources are 1280×720 at 24fps; final 1080p frames are upscaled and graded during assembly. Actual generated durations are approximately 10.04–10.08 seconds, or 7.04 seconds for the group memory; source-specific measured bounds control the edit.

Private assets, large exports, acoustic intermediate evidence and signed provider URLs are excluded from Git. The tracked ledger has no signed URLs or credentials. Remote task IDs identify the generated assets for the connected account; rebuilding locally requires the ignored local media files.

## Typography and runtimes

Noto Serif CJK SC Regular is used for Chinese and Latin titles and subtitles. Local font SHA-256: `2a2eae2628df83556c54018c41e20fa532c1b862c5256ae8b3f23feb918d12ca`. Font source: [Noto CJK](https://github.com/notofonts/noto-cjk); SIL Open Font License 1.1 notice is retained in [licenses/NotoSerifCJK-OFL.txt](licenses/NotoSerifCJK-OFL.txt).

The renderer uses installed ImageIO-FFmpeg 0.6.0 to locate the tested FFmpeg 7.1 Gyan essentials binary, with libass and NVENC. This binary was built with GPL/version3 options and is not distributed here. Local source scripts are original project code using installed APIs. Primary upstream comparisons and version observations are in the [research note](../../docs/research/hock-siew-native-tribute-2026-11-19.md).

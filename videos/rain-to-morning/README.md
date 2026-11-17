# Rain to Morning

A cinematic theme for lyric films. Eight original ImageGen backgrounds follow a rainy city
into amber morning light. A pair of cups, a red thread, and a blank notebook tie the scenes
together. Their lower thirds leave room for large lyrics in ivory or warm gold.

Use the plates with the [lyric film workflow](../../docs/MUSIC_VIDEO.md#lyric-films) for
an automatic first cut. To set the cuts yourself, start from [edit.example.json](edit.example.json),
which needs a recording longer than 17 seconds.

- Each shot starts at `at` in soundtrack seconds. The first starts at zero and the last runs
  through the end of the recording.
- `image` resolves relative to the edit file. `enter` and `leave` define camera zoom and
  normalized crop positions. `dissolve` controls the incoming transition in seconds.
- `accent_sections` uses exact section names from the cue file. Titles have their own
  `start`, `end`, and `text`.
- The sample uses Noto Serif CJK SC. Install or pass the matching
  [Noto Serif CJK SC font](https://github.com/notofonts/noto-cjk/blob/Serif2.003/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf)
  with `--font`. The font is published under the
  [SIL Open Font License](https://github.com/notofonts/noto-cjk/blob/Serif2.003/Serif/LICENSE).

The authored anniversary edit used this artwork in 22 shots over the complete 3:57.6
recording, with 39 reviewed Mandarin lyric cues. The 1080p export passed a full 5,703-frame
decode, frame-clock verification, and zero-offset soundtrack comparison. The personal
recording, dedication, timed lyrics, and MP4 stay local.

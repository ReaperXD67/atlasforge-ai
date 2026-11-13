# The Colour of You

A 4:34 music film in 52 shots. It starts inside a rain-dark city, returns to the same woman on a blue coast, and lets the last chorus open into morning light. The supplied song is the only soundtrack. The lyrics guide the cuts; the picture stays free of captions, with titles only at the bookends.

Follow the [creative brief](BRIEF.md) and [storyboard](STORYBOARD.md), or edit the frame numbers, source windows, crop points and grades in [edit.json](edit.json). Footage was provided by [Pexels](https://www.pexels.com/) under the [Pexels License](https://www.pexels.com/license/). The edit lists every clip's original page, creator, direct file and checksum. No video generation was used.

## Rebuild

From the repository root, use the [AtlasForge Python environment](../../SETUP.md), with `ffmpeg` and `ffprobe` on `PATH` and FFmpeg built with `libx264`. Supply the original 48 kHz stereo WAV separately.

```powershell
$song = 'C:/path/to/The Colour of You.wav'
$work = 'output/colour-of-you'
$film = "$work/The-Colour-of-You.mp4"
.venv/Scripts/python.exe -m daily_video_factory.stock_film videos/the-colour-of-you/edit.json --audio $song --work $work --output $film --workers 3
.venv/Scripts/python.exe videos/the-colour-of-you/review.py videos/the-colour-of-you/edit.json $film --output "$work/Contact-Sheet.jpg"
```

The renderer stages the exact stock files into the work directory without a search key. Keep that directory between revisions: only shots with changed source bytes or rendering settings need to encode again. The mux uses the master at its original timing and gain, encoding it as stereo AAC for playback compatibility. The verifier decodes the entire export and checks each audio channel against the WAV at zero offset. The contact sheet samples the finished export at each shot midpoint.

The original WAV, raw clips and local render cache stay outside Git. For another song, use the [stock film workflow](../../docs/MUSIC_VIDEO.md#authored-stock-music-films) and its [authoring skill](../../.agents/skills/stock-music-film/SKILL.md).

## Verified delivery

The finished 1080p24 export is 4:34.333. All 6,584 frames decoded and matched the exact 24 fps clock. The two AAC channels correlate 0.999918 and 0.999863 with the source WAV at zero offset. [Verification receipt and checksum](DELIVERY_VERIFICATION.json)

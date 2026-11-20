# Canonical analyzer recovery

On 2026-11-20, the existing canonical `music-to-video/scripts/analyze-beatgrid.py` completed successfully against the unchanged project `assets/bgm.wav` in about 35 seconds. This was one retry, using the existing project virtual environment.

Only the child process received `NUMBA_CPU_NAME=generic` and a newly created local `NUMBA_CACHE_DIR`. `NUMBA_DISABLE_JIT` was removed from that child's environment so normal compilation could run. No global environment variables, installed packages or analyzer source files were edited. No second beat-analysis tool was used.

The output, [audiomap-cpu-generic.json](audiomap-cpu-generic.json), parses as canonical version 2 and reports the expected 196.760-second source duration, 96 energy phases and 27 phrases. Its grid arrays are finite, ordered and within the source duration; event times are also within bounds. [Machine-readable evidence](canonical-analyzer-generic-result.json) includes return code, scoped environment, duration, source/analyzer/output SHA-256 hashes and validation; [the raw log](canonical-analyzer-generic.log) is retained.

This successful retry is consistent with a CPU-target or cached-compilation interaction, but does not establish which caused the earlier Windows crash. Preserve the original song and 40 canonical lyric cues. The analyzer's tempo remains a tracker estimate; use phrase-flow pacing unless musical review establishes that the grid is trustworthy. No BPM claim is adopted here.

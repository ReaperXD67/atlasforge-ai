# V3 context reuse

V3 replaces the earlier generated protagonist material. Its planned moving context combines new face-free Gen-4.5 footage with only two legacy sources: `assets/native/sea-dawn.mp4` and `assets/native/wet-footsteps.mp4`. Neither is footage of Hock Siew. The other legacy ensemble and tightly cropped detail shots are excluded from this revision's planned reuse.

| Source | Unique usable interval | Source format | SHA-256 |
| --- | --- | --- | --- |
| `sea-dawn.mp4` | 0.20–9.80s, 9.60s | 1280×720, 24fps, 242 frames | `71183de07a7c8b6a86eb8beb0c361ddd4ca4b1685a9b76397360a711cca2c826` |
| `wet-footsteps.mp4` | 0.20–9.75s, 9.55s | 1280×720, 24fps, 242 frames | `0553169381fe2ba220077f1c01980540f9dc47e50646a2a98f072abc65898bed` |

Both files match the existing source hashes. Reuse is full-frame, with no extreme face-excluding crop, and supplies at most **19.15 unique seconds**. These sources remain native 720p even when scaled into the 1080p delivery; scaling does not recover 1080p detail. The sea shot contains moving water and a distant boat; the footsteps shot shows generic people's lower bodies and wet pavement. Do not present the people as Hock Siew or label these generated events as his real history.

The existing [context review](context-review-v2.json) records eight chronological samples per source. Those samples show no identifiable faces in these two full-frame shots. This is sampled evidence, not a guarantee about every intervening frame or motion realism. Review the complete selected intervals in the assembled edit and record any reprise rather than silently replaying source time.

New downloaded source files are inspected with:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/inspect_sources_v3.py
```

The helper reads [generation-jobs-v3.json](generation-jobs-v3.json), probes and completely decodes each available listed MP4, records hashes and native metadata in `source-metadata-v3.json`, and writes ten chronological sample frames as a sheet under `renders/v3/source-review/`. `--allow-missing` supports an explicitly partial inspection while jobs are still downloading. None of these technical results automatically accepts likeness, body anatomy, backgrounds or natural movement.

# Third-party notices for the six BizNex pilots

The [MIT license](LICENSE) covers AtlasForge-authored code. It does not relicense
third-party fonts, JavaScript libraries, model weights, or media. This notice covers the
visual assets bundled in `config/batches/biznex-first-six.production.json`; it is not a
complete license inventory of every optional provider or dependency.

## Fonts

All six pilot projects contain the same three font files under `assets/fonts/`, with a
complete adjacent SIL Open Font License 1.1 notice for each. These notices and copyright
statements must remain with redistributed font software. The source projects preserve
them; the delivery ZIP contains rendered media rather than font binaries.

| Font | Version read from the bundled font's name table | Adjacent notice and upstream project |
| --- | --- | --- |
| Fraunces | `1.000;[b76b70a41]` | `Fraunces-OFL.txt`; [Fraunces project](https://github.com/undercasetype/Fraunces) |
| Montserrat | `9.000` | `Montserrat-OFL.txt`; [Montserrat project](https://github.com/JulietaUla/Montserrat) |
| IBM Plex Mono | `2.3` | `PlexMono-OFL.txt`; [IBM Plex project](https://github.com/IBM/plex) |

The font files were reused from existing repository assets. Their original download
URLs and retrieval commits were not recorded, so these are **local provenance checks**,
not claims of a newly verified upstream download. Font identity, version, embedded OFL
declaration, complete adjacent notices, and equal bytes across all six projects were
checked on 6 November 2026. SHA-256 identifies the audited files:

```text
177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb  Fraunces.ttf
0f7b311b2f3279e4eef9b2f968bcdbab6e28f4daeb1f049f4f278a902bcd82f7  Montserrat.ttf
6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46  PlexMono.ttf
```

For an example of the actual notices, see the first project's
[font directory](videos/biznex-two-paper-doors/assets/fonts).

## GSAP

Each pilot vendors GSAP **3.14.2** at `assets/vendor/gsap.min.js`. It retains the upstream
GreenSock copyright, version and license-link banner. GSAP uses the
[Standard No-Charge GSAP License](https://gsap.com/standard-license/), **not MIT**.
That license permits commercial use subject to its terms and includes restrictions
concerning competing visual animation builders; it must not be described as unrestricted
MIT software. Its FAQ expressly addresses AI-generated GSAP code.

On 6 November 2026, the bundled file matched this version-pinned
[published npm asset](https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js)
byte-for-byte, with SHA-256:

```text
c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280  gsap.min.js
```

The shareable delivery ZIP contains MP4s, thumbnails, copy and captions, not the vendored
GSAP implementation. Source redistribution retains its original banner and terms.

## Original artwork and audio

Paper props, textures, desk scenes and SVG constructions are authored procedural assets.
The project provenance files record no reused creator-reel footage, voice, music or script.
Score and foley are generated locally by AtlasForge code; narration uses the configured
Kokoro `af_heart` voice without reference-voice cloning. These statements describe the
recorded inputs; they do not grant additional rights over Atomy trademarks or change a
speech model's separate terms. See [upstream research](docs/UPSTREAM_RESEARCH.md) for model
and tool decisions, and per-project `assets/audio/provenance.json` for the actual audio
sources.

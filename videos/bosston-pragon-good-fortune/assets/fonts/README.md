# Film fonts

These local files keep rendering independent of system font substitutions.
Both families are licensed under the **SIL Open Font License 1.1**. Keep the
font copyright and license notices with redistributed editable sources.

| Local file | Verified embedded identity | Upstream source and local checksum |
| --- | --- | --- |
| `NotoSerifCJKsc-Regular.otf` | Noto Serif CJK SC Regular, version 2.003; copyright 2017–2024 Adobe | [Official Noto CJK Serif repository](https://github.com/notofonts/noto-cjk/tree/main/Serif). SHA-256 `2a2eae2628df83556c54018c41e20fa532c1b862c5256ae8b3f23feb918d12ca`. |
| `CormorantGaramond.ttf` | Cormorant Garamond, version 4.001; copyright 2015 the Cormorant Project Authors | [Official Cormorant repository](https://github.com/CatharsisFonts/Cormorant). SHA-256 `b20b7d9626dd956b2c5e558692ad328b1f19e3275e2782db4fa07670d83f35e0`. |

The identities and versions above were read from the actual local OpenType name
tables. Checksums identify these local font bytes; they are not a claim that the
files were downloaded during this production pass.

The accompanying unmodified license texts were retrieved on 18 November 2026
from pinned official upstream revisions:

- [OFL-NotoSerifCJK.txt](OFL-NotoSerifCJK.txt), from Noto CJK
  [`a99a4354`](https://github.com/notofonts/noto-cjk/blob/a99a4354c68964f6bfac488d01010b1fb6d9178a/Serif/LICENSE).
- [OFL-Cormorant.txt](OFL-Cormorant.txt), from Cormorant
  [`d1f2da8d`](https://github.com/CatharsisFonts/Cormorant/blob/d1f2da8db82d2803eb8582ae4acf58549cd69cea/OFL.txt).

The lyric renderer uses the CJK face; the review contact-sheet script uses the
same face so Chinese labels remain legible.

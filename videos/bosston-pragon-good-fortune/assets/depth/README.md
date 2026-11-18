# AI scene depth data

These 17 grayscale maps drive the film's depth-aware camera movement while preserving the generated scene artwork. `../../ai-assets.json` pins each source image and its generation origin; `../../ai-depths.json` pins each source/map pair by SHA-256 and records the model, dimensions and normalization.

The maps use [Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf/tree/5426e4f0f36572d16453bbda7a8389317b1bef99), revision `5426e4f0f36572d16453bbda7a8389317b1bef99`. The Small model is licensed under **Apache-2.0**; the official [upstream README](https://github.com/DepthAnything/Depth-Anything-V2/blob/a561b849ebae10a6f5ef49e26c83cbbcd36c71bf/README.md) distinguishes it from the noncommercial Base/Large/Giant weights. The unchanged Apache notice is included as [LICENSE-DepthAnything.txt](LICENSE-DepthAnything.txt). The helper verifies the pinned checkpoint and license checksums before use.

From the repository root, regenerate all maps with the existing Python environment:

```powershell
.venv/Scripts/python.exe videos/bosston-pragon-good-fortune/generate_ai_depth.py --manifest videos/bosston-pragon-good-fortune/ai-assets.json
```

The verified batch produced all 17 maps in 22.585 seconds on eight CPU threads using PyTorch `2.13.0+cpu` and Transformers `5.14.1`. No package versions or machine security settings were changed. The helper uses installed Hugging Face Depth Anything/DINOv2 classes with an explicit image backbone and strict checkpoint loading. The isolated model cache and raw float/16-bit fields remain under `output/bosston-ai-v3/depth/`; runtime assets are only the 8-bit PNGs and this documentation.

For rendering, load each PNG as **linear / NoColorSpace data**: white is nearer and black is farther. Each source-size map is 1672 × 941, estimated from a 924 × 518 model input. Values are clipped at the raw prediction's 2nd and 98th percentiles, then normalized to 0–255. Keep `requireDepth: true` in the AI manifest so missing or stale pairs fail validation.

These are relative monocular estimates, not metric geometry or native image-to-video output. Hidden surfaces cannot be reconstructed, and blurred foreground lanterns can be mis-ranked. Use restrained parallax, overscan and visual checks around silhouettes. Scene animation and camera rendering are original project implementations; no DepthFlow source was copied.

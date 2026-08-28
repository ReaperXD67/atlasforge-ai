param(
    [switch]$SkipCapture,
    [switch]$SkipNarration,
    [switch]$SkipRender
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Split-Path -Parent $scriptDirectory
$project = Join-Path $repository "videos\biznex-revive-pitch-001"
$atlasforge = Join-Path $repository ".venv\Scripts\atlasforge.exe"
$python = Join-Path $repository ".venv\Scripts\python.exe"
$captureOutput = Join-Path $repository "output\revive-pitch\captures"
$audioOutput = Join-Path $repository "output\revive-pitch\audio"
$deliverables = Join-Path $repository "output\revive-pitch\deliverables"

if (-not $SkipCapture) {
    & $atlasforge browser-capture `
        --recipe (Join-Path $repository "config\captures\revive-pitch.yaml") `
        --output $captureOutput
    if ($LASTEXITCODE -ne 0) { throw "Browser capture failed." }
}

if (-not $SkipNarration) {
    & $atlasforge narrate `
        --text-file (Join-Path $repository "docs\biznex\revive-pitch-narration.txt") `
        --output $audioOutput `
        --config (Join-Path $repository "config\profiles\biznex-revive-pitch.yaml")
    if ($LASTEXITCODE -ne 0) { throw "Narration generation failed." }
}

& $python -c "from pathlib import Path; from daily_video_factory.media.audio import generate_original_music; generate_original_music(300, Path(r'$audioOutput') / 'revive-score.wav')"
if ($LASTEXITCODE -ne 0) { throw "Original score generation failed." }

& node (Join-Path $repository "scripts\build_revive_pitch.mjs")
if ($LASTEXITCODE -ne 0) { throw "Composition build failed." }
Copy-Item -LiteralPath (Join-Path $captureOutput "capture-manifest.md") -Destination (Join-Path $deliverables "capture-manifest.md") -Force
Copy-Item -LiteralPath (Join-Path $project "PUBLIC_UPLOAD_CHECKLIST.md") -Destination (Join-Path $deliverables "PUBLIC_UPLOAD_CHECKLIST.md") -Force
Copy-Item -LiteralPath (Join-Path $project "UPLOAD_PACKAGE.md") -Destination (Join-Path $deliverables "UPLOAD_PACKAGE.md") -Force

Push-Location $project
try {
    # The managed headless-shell binary may be blocked by Windows Application Control. The signed
    # system Chrome installation is the deterministic renderer fallback on this workstation.
    $env:PRODUCER_HEADLESS_SHELL_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    & npx --yes hyperframes@0.8.17 check --samples 16 --at-transitions --snapshots --no-browser-gpu
    if ($LASTEXITCODE -ne 0) { throw "HyperFrames quality check failed." }

    New-Item -ItemType Directory -Path $deliverables -Force | Out-Null
    & npx --yes hyperframes@0.8.17 snapshot . --at "1,19,41,59,87,112,145,183,205,230,257,280,299" --no-end --no-browser-gpu --output (Join-Path $deliverables "review-frames")
    if ($LASTEXITCODE -ne 0) { throw "Review snapshot capture failed." }

    & npx --yes hyperframes@0.8.17 snapshot thumbnail --at "1" --no-end --no-browser-gpu --output (Join-Path $deliverables "thumbnail-frame")
    if ($LASTEXITCODE -ne 0) { throw "Thumbnail capture failed." }
    Copy-Item -LiteralPath (Get-ChildItem (Join-Path $deliverables "thumbnail-frame") -Filter *.png | Select-Object -First 1).FullName -Destination (Join-Path $deliverables "revive-thumbnail.png") -Force

    if (-not $SkipRender) {
        & npx --yes hyperframes@0.8.17 render . --fps 30 --quality high --video-bitrate 12M --workers 2 --no-browser-gpu --output (Join-Path $deliverables "revive-five-minute-pitch.mp4") --skill general-video
        if ($LASTEXITCODE -ne 0) { throw "Final video render failed." }
    }
}
finally {
    Pop-Location
}

Write-Host "Revive pitch package ready at $deliverables"

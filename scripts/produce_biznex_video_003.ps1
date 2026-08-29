[CmdletBinding()]
param(
    [switch]$ReuseAudio,
    [switch]$SkipRender,
    [ValidateSet("draft", "standard", "high")]
    [string]$Quality = "high"
)

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$project = Join-Path $repository "videos\biznex-atomy-video-003-short"
$audio = Join-Path $repository "output\biznex-video-003\audio"
$delivery = Join-Path $repository "output\biznex-video-003"
$spec = Join-Path $repository "docs\biznex\video-003\experiment-spec.json"
$shortSpec = Join-Path $repository "docs\biznex\video-003\short-spec.json"
$config = Join-Path $repository "config\profiles\biznex-atomy-video-003-short.yaml"
$atlasforge = Join-Path $repository ".venv\Scripts\atlasforge.exe"
$transitions = Join-Path $env:USERPROFILE ".agents\skills\faceless-explainer\scripts\transitions.mjs"
$chrome = Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"

foreach ($required in @($atlasforge, $transitions, $chrome, $spec, $shortSpec, $config)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required dependency is missing: $required"
    }
}
New-Item -ItemType Directory -Force -Path $audio, $delivery | Out-Null

& $atlasforge short-manifest --spec $spec --output (Join-Path $delivery "growth-experiment.json")
if (-not $ReuseAudio -or -not (Test-Path -LiteralPath (Join-Path $audio "narration.wav"))) {
    & $atlasforge narrate-script `
        --script (Join-Path $project "SCRIPT.md") `
        --output $audio `
        --config $config
}

$narrationSeconds = [double]((& ffprobe -v error -show_entries format=duration `
    -of default=noprint_wrappers=1:nokey=1 (Join-Path $audio "narration.wav")).Trim())
$totalSeconds = $narrationSeconds + 0.8
& $atlasforge original-music --duration $totalSeconds --output (Join-Path $audio "original-music.wav")
& $atlasforge short-sfx --output (Join-Path $project "public")

$env:BIZNEX_SHORT_SPEC = $shortSpec
$env:BIZNEX_SHORT_AUDIO_ROOT = $audio
Push-Location $repository
try {
    & node (Join-Path $repository "scripts\build_biznex_short.mjs")
} finally {
    Pop-Location
}

Push-Location $project
try {
    & node $transitions inject --storyboard STORYBOARD.md --index index.html --motion index.motion.json
    & node $transitions verify --storyboard STORYBOARD.md --index index.html --motion index.motion.json
    $env:PRODUCER_HEADLESS_SHELL_PATH = $chrome
    & npx hyperframes check --browser-gpu --at 3.6,10.6,17.5,24.8,33.6,44.7,48.3,54.2 `
        --caption-zone "x0=0;y0=.82;x1=1;y1=1;severity=error;seek=.25,1" --frame-check

    if (-not $SkipRender) {
        $rendered = Join-Path $project "renders\biznex-video-003.mp4"
        New-Item -ItemType Directory -Force -Path (Split-Path $rendered) | Out-Null
        & npx hyperframes render --skill=faceless-explainer --quality $Quality --workers 2 `
            --browser-gpu --output $rendered
        Copy-Item -LiteralPath $rendered -Destination (Join-Path $delivery "BizNex-Video-003-HemoHIM-PV-Short.mp4") -Force
    }
} finally {
    Pop-Location
}

$thumbnail = Join-Path $delivery "BizNex-Video-003-Thumbnail.png"
$thumbnailUri = [Uri]::new((Resolve-Path (Join-Path $project "thumbnail\thumbnail.html")).Path).AbsoluteUri
$thumbnailProfile = Join-Path $env:TEMP ("biznex-thumb-003-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $thumbnailProfile | Out-Null
& $chrome --headless=new --disable-gpu --hide-scrollbars --run-all-compositor-stages-before-draw `
    --user-data-dir=$thumbnailProfile --window-size=1280,720 --screenshot=$thumbnail $thumbnailUri

foreach ($sidecar in @("narration.exact.srt", "narration.caption-verification.json", "narration.performance.json")) {
    $source = Join-Path $audio $sidecar
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $delivery $sidecar) -Force
    }
}
Copy-Item -LiteralPath (Join-Path $repository "docs\biznex\VIDEO_003_LAUNCH.md") -Destination $delivery -Force

Write-Host "BizNex Video 003 package ready: $delivery"

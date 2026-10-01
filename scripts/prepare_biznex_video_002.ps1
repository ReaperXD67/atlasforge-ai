param(
    [string]$RunRoot = "",
    [string]$MusicSource = "",
    [switch]$SkipNarration
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Split-Path -Parent $scriptDirectory
$project = Join-Path $repository "videos\biznex-atomy-video-002"
$atlasforge = Join-Path $repository ".venv\Scripts\atlasforge.exe"
$humanVoiceOutput = Join-Path $repository "output\biznex-video-002\human-voice"

if (-not $RunRoot) {
    $candidate = Get-ChildItem -LiteralPath (Join-Path $repository "output") -Directory |
        Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName "audio\narration.wav") -PathType Leaf
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $candidate) {
        throw "No pipeline run containing audio\narration.wav was found. Pass -RunRoot explicitly."
    }
    $RunRoot = $candidate.FullName
}

$resolvedRun = (Resolve-Path -LiteralPath $RunRoot).Path
$script = Join-Path $resolvedRun "scripts\narration.txt"
$timedStoryboard = Join-Path $resolvedRun "storyboards\storyboard_timed.json"
foreach ($required in @($script, $timedStoryboard)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Video 002 source is missing: $required"
    }
}

if (-not $SkipNarration) {
    & $atlasforge narrate `
        --text-file $script `
        --output $humanVoiceOutput `
        --config (Join-Path $repository "config\profiles\biznex-atomy-video-002.yaml") `
        --target-seconds 325.03
    if ($LASTEXITCODE -ne 0) { throw "Human narration and exact caption generation failed." }
}

$narration = Join-Path $humanVoiceOutput "narration.wav"
$captionTimings = Join-Path $humanVoiceOutput "narration.captions.json"
$exactCaptions = Join-Path $humanVoiceOutput "narration.exact.srt"
foreach ($required in @($narration, $captionTimings, $exactCaptions)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required exact narration source is missing: $required"
    }
}

$projectAssets = Join-Path $project "assets"
New-Item -ItemType Directory -Path $projectAssets -Force | Out-Null
Copy-Item -LiteralPath $narration -Destination (Join-Path $projectAssets "narration.wav") -Force
$projectCaptions = Join-Path $project "captions"
New-Item -ItemType Directory -Path $projectCaptions -Force | Out-Null
Copy-Item -LiteralPath $exactCaptions `
    -Destination (Join-Path $projectCaptions "atomy-compensation-plan.en.srt") `
    -Force

if (-not $MusicSource) {
    $musicCandidate = Get-ChildItem -LiteralPath (Join-Path $repository "output") -Directory |
        ForEach-Object { Join-Path $_.FullName "music\original_ambient.wav" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Sort-Object { (Get-Item -LiteralPath $_).LastWriteTime } -Descending |
        Select-Object -First 1
    $MusicSource = $musicCandidate
}
if (-not $MusicSource -or -not (Test-Path -LiteralPath $MusicSource -PathType Leaf)) {
    throw "No original ambient bed was found. Pass -MusicSource explicitly."
}

$duration = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $narration
if ($LASTEXITCODE -ne 0 -or -not $duration) {
    throw "ffprobe could not read the narration duration."
}
& ffmpeg -hide_banner -loglevel error -y -stream_loop -1 -i $MusicSource `
    -t $duration -af "afade=t=in:st=0:d=1.2,afade=t=out:st=$([math]::Max(0, [double]$duration - 2.0)):d=2" `
    -c:a aac -b:a 128k (Join-Path $projectAssets "biznex-bed.m4a")
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg could not prepare the music bed."
}

$env:BIZNEX_VIDEO_002_RUN_ROOT = $resolvedRun
$env:BIZNEX_VIDEO_002_AUDIO_ROOT = $humanVoiceOutput
& node (Join-Path $scriptDirectory "build_biznex_video_002.mjs")
if ($LASTEXITCODE -ne 0) {
    throw "The Video 002 HyperFrames source build failed."
}

Write-Host "Video 002 assets and composition are ready at $project"

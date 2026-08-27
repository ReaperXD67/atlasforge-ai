param(
    [string]$RunRoot = "",
    [string]$MusicSource = ""
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Split-Path -Parent $scriptDirectory
$project = Join-Path $repository "videos\biznex-atomy-video-002"

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
$narration = Join-Path $resolvedRun "audio\narration.wav"
$timedStoryboard = Join-Path $resolvedRun "storyboards\storyboard_timed.json"
foreach ($required in @($narration, $timedStoryboard)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required Video 002 source is missing: $required"
    }
}

$projectAssets = Join-Path $project "assets"
New-Item -ItemType Directory -Path $projectAssets -Force | Out-Null
Copy-Item -LiteralPath $narration -Destination (Join-Path $projectAssets "narration.wav") -Force

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
& node (Join-Path $scriptDirectory "build_biznex_video_002.mjs")
if ($LASTEXITCODE -ne 0) {
    throw "The Video 002 HyperFrames source build failed."
}

Write-Host "Video 002 assets and composition are ready at $project"

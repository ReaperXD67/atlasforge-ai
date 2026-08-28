param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Revive", "Atomy")]
    [string]$Target,
    [string]$InputVideo = "",
    [string]$OutputVideo = "",
    [switch]$HardwareEncoder
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Split-Path -Parent $scriptDirectory

if ($Target -eq "Revive") {
    if (-not $InputVideo) {
        $InputVideo = Join-Path $repository "output\revive-pitch\deliverables\revive-five-minute-pitch.mp4"
    }
    if (-not $OutputVideo) {
        $OutputVideo = Join-Path $repository "output\revive-pitch\deliverables\revive-five-minute-pitch-human-voice-exact-captions.mp4"
    }
    $narration = Join-Path $repository "output\revive-pitch\audio\narration.wav"
    $music = Join-Path $repository "output\revive-pitch\audio\revive-score.wav"
    $subtitleRelative = "output/revive-pitch/deliverables/revive-five-minute-pitch-exact.srt"
    $subtitle = Join-Path $repository "output\revive-pitch\deliverables\revive-five-minute-pitch-exact.srt"
    $inputs = @("-i", $InputVideo, "-i", $narration, "-i", $music)
    $audioFilter = "[1:a]pan=stereo|c0=c0|c1=c0,adelay=700|700[n];[2:a]volume=0.055[m];[n][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:300[a]"
    $captionColor = "0x080d0b"
}
else {
    if (-not $InputVideo) {
        $InputVideo = Join-Path $repository "output\biznex-video-002\BizNex-Atomy-Business-Plan-2026.mp4"
    }
    if (-not $OutputVideo) {
        $OutputVideo = Join-Path $repository "output\biznex-video-002\BizNex-Atomy-Business-Plan-2026-human-voice-exact-captions.mp4"
    }
    $narration = Join-Path $repository "output\biznex-video-002\human-voice\narration.wav"
    $music = Join-Path $repository "videos\biznex-atomy-video-002\assets\biznex-bed.m4a"
    $sfx = Join-Path $repository "videos\biznex-atomy-video-002\.media\audio\sfx\sfx_001.mp3"
    $subtitleRelative = "output/biznex-video-002/video-002-exact-captions.srt"
    $subtitle = Join-Path $repository "output\biznex-video-002\video-002-exact-captions.srt"
    $inputs = @("-i", $InputVideo, "-i", $narration, "-i", $music, "-i", $sfx)
    $delays = @(32065, 64210, 101081, 155905, 216718, 260863, 303627)
    $splitOutputs = (0..6 | ForEach-Object { "[s$_]" }) -join ""
    $sfxFilters = (0..6 | ForEach-Object { "[s$_]volume=0.22,adelay=$($delays[$_])|$($delays[$_])[d$_]" }) -join ";"
    $mixInputs = "[n][m]" + ((0..6 | ForEach-Object { "[d$_]" }) -join "")
    $audioFilter = "[1:a]pan=stereo|c0=c0|c1=c0[n];[2:a]volume=0.075[m];[3:a]asplit=7$splitOutputs;$sfxFilters;$mixInputs" + "amix=inputs=9:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:325.041[a]"
    $captionColor = "0x050505"
}

foreach ($required in @($InputVideo, $narration, $music, $subtitle)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required delivery source is missing: $required"
    }
}
if ($Target -eq "Atomy" -and -not (Test-Path -LiteralPath $sfx -PathType Leaf)) {
    throw "Required transition sound is missing: $sfx"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $OutputVideo) -Force | Out-Null
$videoFilter = "drawbox=x=0:y=875:w=iw:h=205:color=$captionColor`:t=fill,subtitles=filename='$subtitleRelative':force_style='FontName=Segoe UI Semibold,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginL=35,MarginR=35,MarginV=9'"
$common = @("-y", "-hide_banner") + $inputs + @(
    "-vf", $videoFilter,
    "-filter_complex", $audioFilter,
    "-map", "0:v:0",
    "-map", "[a]",
    "-c:a", "aac",
    "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart"
)

Push-Location $repository
try {
    if ($HardwareEncoder) {
        & ffmpeg @common -c:v h264_nvenc -preset p5 -cq 19 -b:v 0 $OutputVideo
    }
    if (-not $HardwareEncoder -or $LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $OutputVideo) { Remove-Item -LiteralPath $OutputVideo -Force }
        & ffmpeg @common -c:v libx264 -preset fast -crf 19 $OutputVideo
    }
    if ($LASTEXITCODE -ne 0) { throw "$Target corrected delivery export failed." }
}
finally {
    Pop-Location
}

Write-Host "$Target human-voice delivery ready at $OutputVideo"

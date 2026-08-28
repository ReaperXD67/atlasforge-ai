param(
    [string]$InputVideo,
    [string]$OutputVideo,
    [switch]$HardwareEncoder
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Split-Path -Parent $scriptDirectory

if (-not $InputVideo) {
    $InputVideo = Join-Path $repository "output\biznex-video-002\BizNex-Atomy-Business-Plan-2026.mp4"
}
if (-not $OutputVideo) {
    $OutputVideo = Join-Path $repository "output\biznex-video-002\BizNex-Atomy-Business-Plan-2026-five-second-text-fix.mp4"
}

$subtitle = Join-Path $repository "output\biznex-video-002\video-002-five-second-captions.srt"
if (-not (Test-Path -LiteralPath $InputVideo)) { throw "Input video not found: $InputVideo" }
if (-not (Test-Path -LiteralPath $subtitle)) { throw "Subtitle file not found: $subtitle" }

New-Item -ItemType Directory -Path (Split-Path -Parent $OutputVideo) -Force | Out-Null
$filter = "drawbox=x=0:y=875:w=iw:h=205:color=0x050505:t=fill,subtitles=filename='output/biznex-video-002/video-002-five-second-captions.srt':force_style='FontName=Segoe UI Semibold,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginL=35,MarginR=35,MarginV=9'"

Push-Location $repository
try {
    $common = @("-y", "-hide_banner", "-i", $InputVideo, "-vf", $filter, "-map", "0:v:0", "-map", "0:a?", "-c:a", "copy", "-movflags", "+faststart")
    if ($HardwareEncoder) {
        & ffmpeg @common -c:v h264_nvenc -preset p5 -cq 19 -b:v 0 $OutputVideo
    }
    if (-not $HardwareEncoder -or $LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $OutputVideo) { Remove-Item -LiteralPath $OutputVideo -Force }
        & ffmpeg @common -c:v libx264 -preset fast -crf 19 $OutputVideo
    }
    if ($LASTEXITCODE -ne 0) { throw "Corrected Video 002 export failed." }
}
finally {
    Pop-Location
}

Write-Host "Corrected Video 002 ready at $OutputVideo"

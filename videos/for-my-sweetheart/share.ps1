param(
    [string]$InputVideo = (Join-Path $PSScriptRoot 'renders/For-my-Sweetheart-Anniversary.mp4'),
    [string]$OutputVideo = (Join-Path $PSScriptRoot 'renders/For-my-Sweetheart-Share.mp4')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $InputVideo -PathType Leaf)) {
    throw "Render the full film first: $InputVideo"
}
if ([IO.Path]::GetFullPath($InputVideo) -eq [IO.Path]::GetFullPath($OutputVideo)) {
    throw 'The sharing copy must use a different output path.'
}

# A portable CPU encoder keeps this delivery step independent of GPU hardware.
& ffmpeg -hide_banner -y -i $InputVideo -map 0:v:0 -map 0:a:0 `
    -vf 'scale=1280:720:flags=lanczos' -c:v libx264 -preset fast -crf 21 `
    -maxrate 3M -bufsize 6M -pix_fmt yuv420p -c:a aac -b:a 192k `
    -movflags +faststart $OutputVideo
if ($LASTEXITCODE -ne 0) { throw 'Sharing-copy encoding failed.' }

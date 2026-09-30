[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$Output = "renders/final.mp4",

    [ValidateSet("draft", "looks", "delivery", "standard", "high")]
    [string]$Quality = "delivery",

    [string]$Thumbnail,

    [switch]$VerifyShorts,

    [double]$MinDuration = 20,

    [double]$MaxDuration = 30,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$projectPath = (Resolve-Path -LiteralPath $Project).Path
$packagePath = Join-Path $projectPath "package.json"
if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf)) {
    throw "HyperFrames package.json not found: $packagePath"
}

$packageText = Get-Content -LiteralPath $packagePath -Raw
$versionMatch = [regex]::Match($packageText, 'hyperframes@(\d+\.\d+\.\d+)')
if (-not $versionMatch.Success) {
    throw "The project does not pin a HyperFrames version in package.json."
}
$hyperframesVersion = $versionMatch.Groups[1].Value

$chromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
$chromePath = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if ($chromePath) {
    $env:PRODUCER_HEADLESS_SHELL_PATH = $chromePath
}

$env:PRODUCER_BROWSER_GPU_MODE = "software"
$env:PRODUCER_LOW_MEMORY_MODE = "1"

$renderArgs = @(
    "--yes",
    "hyperframes@$hyperframesVersion",
    "render",
    ".",
    "--output", $Output,
    "--quality", $Quality,
    "--fps", "30",
    "--workers", "1",
    "--low-memory-mode",
    "--no-browser-gpu",
    "--browser-timeout", "120",
    "--protocol-timeout", "600000",
    "--player-ready-timeout", "120000",
    "--skill", "faceless-explainer"
)

Write-Host "HyperFrames $hyperframesVersion | software browser | low-memory mode | one worker"
if ($chromePath) {
    Write-Host "Browser: $chromePath"
}
Write-Host "Project: $projectPath"
Write-Host "Output: $Output"

if ($DryRun) {
    Write-Host "Dry run: npx $($renderArgs -join ' ')"
    exit 0
}

Push-Location $projectPath
try {
    & npx @renderArgs
    if ($LASTEXITCODE -ne 0) {
        throw "HyperFrames render failed with exit code $LASTEXITCODE."
    }

    $outputPath = if ([System.IO.Path]::IsPathRooted($Output)) { $Output } else { Join-Path $projectPath $Output }
    if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        throw "Render completed without producing the expected file: $outputPath"
    }

    if (Get-Command ffprobe -ErrorAction SilentlyContinue) {
        & ffprobe -v error -show_entries "stream=width,height,r_frame_rate:format=duration" -of default=noprint_wrappers=1 $outputPath
        if ($LASTEXITCODE -ne 0) {
            throw "ffprobe could not validate the rendered video."
        }
    }

    if ($VerifyShorts) {
        if (-not $Thumbnail) {
            throw "-Thumbnail is required when -VerifyShorts is enabled."
        }
        $thumbnailPath = if ([System.IO.Path]::IsPathRooted($Thumbnail)) { $Thumbnail } else { Join-Path $projectPath $Thumbnail }
        $repositoryPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        $pythonPath = Join-Path $repositoryPath ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "Python environment not found: $pythonPath"
        }
        & $pythonPath -m daily_video_factory.cli verify-shorts-delivery `
            --video $outputPath `
            --thumbnail $thumbnailPath `
            --min-seconds $MinDuration `
            --max-seconds $MaxDuration
        if ($LASTEXITCODE -ne 0) {
            throw "Shorts delivery verification failed."
        }
    }
}
finally {
    Pop-Location
}

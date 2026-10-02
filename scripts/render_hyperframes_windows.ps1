[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$Output = "renders/final.mp4",

    [ValidateSet("draft", "looks", "delivery", "standard", "high")]
    [string]$Quality = "delivery",

    [string]$Thumbnail,

    [switch]$VerifyShorts,

    [switch]$VerifyYouTube,

    [string]$UploadPackage,

    [string]$VoiceManifest,

    [string]$ExpectedVoice,

    [switch]$CheckFirst,

    [ValidateRange(5, 60)]
    [int]$CheckSamples = 17,

    [double]$MinDuration = 0,

    [double]$MaxDuration = 0,

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

$hyperframesConfigPath = Join-Path $projectPath "hyperframes.json"
$authoringSkill = $null
if (Test-Path -LiteralPath $hyperframesConfigPath -PathType Leaf) {
    $hyperframesConfig = Get-Content -LiteralPath $hyperframesConfigPath -Raw | ConvertFrom-Json
    $authoringSkill = $hyperframesConfig.authoringSkill
}

$chromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
$chromePath = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if ($chromePath) {
    $env:PRODUCER_HEADLESS_SHELL_PATH = $chromePath
    $env:HYPERFRAMES_BROWSER_PATH = $chromePath
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
    "--player-ready-timeout", "120000"
)
if ($authoringSkill) {
    $renderArgs += @("--skill", $authoringSkill)
}

Write-Host "HyperFrames $hyperframesVersion | software browser | low-memory mode | one worker"
if ($chromePath) {
    Write-Host "Browser: $chromePath"
}
Write-Host "Project: $projectPath"
Write-Host "Output: $Output"

if ($VerifyShorts -and $VerifyYouTube) {
    throw "Choose either -VerifyShorts or -VerifyYouTube, not both."
}

if ($MinDuration -le 0) {
    $MinDuration = if ($VerifyYouTube) { 300 } else { 20 }
}
if ($MaxDuration -le 0) {
    $MaxDuration = if ($VerifyYouTube) { 360 } else { 30 }
}
if ($MinDuration -ge $MaxDuration) {
    throw "-MinDuration must be lower than -MaxDuration."
}

if ($DryRun) {
    Write-Host "Dry run: npx $($renderArgs -join ' ')"
    exit 0
}

Push-Location $projectPath
try {
    if ($CheckFirst) {
        & npx --yes "hyperframes@$hyperframesVersion" check . `
            --samples $CheckSamples `
            --snapshots `
            --timeout 120000 `
            --no-browser-gpu
        if ($LASTEXITCODE -ne 0) {
            throw "HyperFrames pre-render check failed."
        }
    }

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
        $uploadPackagePath = if ($UploadPackage) { if ([System.IO.Path]::IsPathRooted($UploadPackage)) { $UploadPackage } else { Join-Path $projectPath $UploadPackage } } else { $null }
        $voiceManifestPath = if ($VoiceManifest) { if ([System.IO.Path]::IsPathRooted($VoiceManifest)) { $VoiceManifest } else { Join-Path $projectPath $VoiceManifest } } else { $null }
        if ($ExpectedVoice -and -not $voiceManifestPath) {
            throw "-VoiceManifest is required when -ExpectedVoice is set."
        }
        $repositoryPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        $pythonPath = Join-Path $repositoryPath ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "Python environment not found: $pythonPath"
        }
        $verifyShortArgs = @(
            "-m", "daily_video_factory.cli", "verify-shorts-delivery",
            "--video", $outputPath,
            "--thumbnail", $thumbnailPath,
            "--min-seconds", $MinDuration,
            "--max-seconds", $MaxDuration
        )
        if ($uploadPackagePath) {
            $verifyShortArgs += @("--upload-package", $uploadPackagePath)
        }
        if ($voiceManifestPath) {
            $verifyShortArgs += @("--voice-manifest", $voiceManifestPath, "--expected-voice", $ExpectedVoice)
        }
        & $pythonPath @verifyShortArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Shorts delivery verification failed."
        }
    }

    if ($VerifyYouTube) {
        if (-not $Thumbnail) {
            throw "-Thumbnail is required when -VerifyYouTube is enabled."
        }
        if (-not $UploadPackage) {
            throw "-UploadPackage is required when -VerifyYouTube is enabled."
        }
        $thumbnailPath = if ([System.IO.Path]::IsPathRooted($Thumbnail)) { $Thumbnail } else { Join-Path $projectPath $Thumbnail }
        $uploadPackagePath = if ([System.IO.Path]::IsPathRooted($UploadPackage)) { $UploadPackage } else { Join-Path $projectPath $UploadPackage }
        $repositoryPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        $pythonPath = Join-Path $repositoryPath ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "Python environment not found: $pythonPath"
        }
        & $pythonPath -m daily_video_factory.cli verify-youtube-delivery `
            --video $outputPath `
            --thumbnail $thumbnailPath `
            --upload-package $uploadPackagePath `
            --min-seconds $MinDuration `
            --max-seconds $MaxDuration
        if ($LASTEXITCODE -ne 0) {
            throw "YouTube delivery verification failed."
        }
    }
}
finally {
    Pop-Location
}

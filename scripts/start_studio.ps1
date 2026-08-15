[CmdletBinding()]
param(
    [switch]$NoBuild,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not on PATH. Install and start Docker Desktop, then run this script again.'
}

& docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop is installed but its engine is not running.'
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    throw 'Created .env. Paste your OPENROUTER_API_KEY into it, then run this script again.'
}

$OpenRouterConfigured = Select-String -LiteralPath '.env' -Pattern '^OPENROUTER_API_KEY=.+$' -Quiet
if (-not $OpenRouterConfigured) {
    throw 'OPENROUTER_API_KEY is empty in .env. Paste the key value after the equals sign.'
}

foreach ($Directory in @('output', 'models', 'secrets')) {
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
}

if ($NoBuild) {
    & docker compose --profile studio up -d atlasforge-studio
} else {
    & docker compose --profile studio up --build -d atlasforge-studio
}
if ($LASTEXITCODE -ne 0) {
    throw 'Docker could not start AtlasForge Studio. Run docker compose --profile studio logs atlasforge-studio for details.'
}

$StudioUrl = 'http://127.0.0.1:8741/'
$Ready = $false
for ($Attempt = 1; $Attempt -le 45; $Attempt++) {
    try {
        $Health = Invoke-RestMethod -Uri "${StudioUrl}health" -TimeoutSec 3
        if ($Health.status -eq 'ok') {
            $Ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $Ready) {
    & docker compose --profile studio logs --tail 80 atlasforge-studio
    throw 'AtlasForge Studio did not become healthy within 90 seconds.'
}

$System = Invoke-RestMethod -Uri "${StudioUrl}api/system" -TimeoutSec 10
Write-Host ''
Write-Host 'AtlasForge Studio is ready.' -ForegroundColor Green
Write-Host "Studio: $StudioUrl"
Write-Host "GPU: $($System.gpu_name)"
Write-Host "Render: $($System.width)x$($System.height) @ $($System.fps) fps using $($System.codec)"
Write-Host "OpenRouter: $($System.openrouter) | Pexels: $($System.pexels) | Kokoro: $($System.kokoro) | Whisper: $($System.whisper)"
Write-Host 'Publishing remains disabled.'

if (-not $NoBrowser) {
    Start-Process $StudioUrl
}

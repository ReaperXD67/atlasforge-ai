[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not on PATH.'
}

& docker compose --profile studio stop atlasforge-studio
if ($LASTEXITCODE -ne 0) {
    throw 'Docker could not stop AtlasForge Studio.'
}

Write-Host 'AtlasForge Studio stopped. Generated files remain in output/.' -ForegroundColor Green

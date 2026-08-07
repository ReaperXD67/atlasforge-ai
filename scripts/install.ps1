[CmdletBinding()]
param(
    [switch]$WithLocalTts,
    [switch]$WithTranscription
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python is not on PATH. Install Python 3.11 x64 and reopen PowerShell.'
}

$PythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($PythonVersion -notin @('3.11', '3.12')) {
    throw "Python $PythonVersion is unsupported. Install Python 3.11 or 3.12."
}

if (-not (Test-Path -LiteralPath '.venv')) {
    & python -m venv .venv
}

$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -e '.[google,youtube]'

if ($WithLocalTts) {
    & $VenvPython -m pip install -e '.[local-tts]'
}
if ($WithTranscription) {
    & $VenvPython -m pip install -e '.[transcription]'
}

foreach ($Directory in @('output', 'models', 'secrets')) {
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}

Write-Host ''
Write-Host 'Installation complete.' -ForegroundColor Green
Write-Host 'Next: edit .env, then run .\.venv\Scripts\atlasforge.exe doctor'

[CmdletBinding()]
param([ValidateRange(1,4)][int]$Workers=1,[string]$Output='renders/BOSSTON-Pragon-Good-Fortune-AI-Cinema.mp4')
$ErrorActionPreference='Stop'
$chromePath='C:\Program Files\Google\Chrome\Application\chrome.exe'
if(Test-Path -LiteralPath $chromePath){$env:PRODUCER_HEADLESS_SHELL_PATH=$chromePath;$env:HYPERFRAMES_BROWSER_PATH=$chromePath}
$env:PRODUCER_LOW_MEMORY_MODE='0'
$env:PRODUCER_BROWSER_GPU_MODE='hardware'
$env:PRODUCER_EXPERIMENTAL_FAST_CAPTURE='false'
Push-Location $PSScriptRoot
try {
  & npx --yes hyperframes@0.8.152 render . --output $Output --quality delivery --fps 30 --workers $Workers --no-low-memory-mode --browser-gpu --gpu --experimental-fast-capture=false --browser-timeout 120 --protocol-timeout 600000 --player-ready-timeout 120000
  if($LASTEXITCODE -ne 0){throw 'Film render failed.'}
  if(-not(Test-Path -LiteralPath $Output)){throw 'Expected MP4 is missing.'}
} finally {Pop-Location}

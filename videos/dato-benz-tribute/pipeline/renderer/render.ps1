[CmdletBinding()]
param([string]$Output='renders/Dato-Benz-Brothers-One-Heart.mp4',[ValidateSet('draft','looks','delivery','standard','high')][string]$Quality='delivery',[double]$Start=0,[double]$End=-1,[switch]$Software,[ValidateRange(1,4)][int]$Workers=1)
$ErrorActionPreference='Stop'
$rendererRoot=$PSScriptRoot
Set-Location -LiteralPath $rendererRoot
if(-not (Test-Path -LiteralPath 'index.html')){throw 'Build index.html using node build.mjs --plan ../../edit-plan.json first.'}
$receipt=Get-Content -LiteralPath 'build-receipt.json' -Raw | ConvertFrom-Json
$env:HYPERFRAMES_BROWSER_PATH='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:PRODUCER_HEADLESS_SHELL_PATH=$env:HYPERFRAMES_BROWSER_PATH
$env:PRODUCER_BROWSER_GPU_MODE=if($Software){'software'}else{'hardware'}
$env:PRODUCER_LOW_MEMORY_MODE=if($Workers -eq 1){'1'}else{'0'}
$renderArgs=@('--yes','hyperframes@0.9.72','render','.', '--output',$Output,'--quality',$Quality,'--fps', $receipt.fps,'--workers',$Workers,'--browser-timeout','120','--protocol-timeout','600000','--player-ready-timeout','120000')
$renderArgs+=if($Workers -eq 1){'--low-memory-mode'}else{'--no-low-memory-mode'}
$renderArgs+=if($Software){'--no-browser-gpu'}else{'--browser-gpu'}
if($Start -gt 0 -or $End -gt 0){
 if($End -gt 0 -and $End -le $Start){throw 'End must be greater than Start.'}
 $renderArgs+=@('--start',$Start)
 if($End -gt 0){$renderArgs+=@('--end',$End)}
}
npx @renderArgs
if($LASTEXITCODE -ne 0){throw 'HyperFrames render failed.'}

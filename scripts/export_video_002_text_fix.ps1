param(
    [string]$InputVideo = "",
    [string]$OutputVideo = "",
    [switch]$HardwareEncoder
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "export_human_voice_exact_captions.ps1") `
    -Target Atomy `
    -InputVideo $InputVideo `
    -OutputVideo $OutputVideo `
    -HardwareEncoder:$HardwareEncoder
exit $LASTEXITCODE

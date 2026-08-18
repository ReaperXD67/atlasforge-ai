param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\AtlasForge\ComfyUI",
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$Python = Join-Path $InstallRoot ".venv\Scripts\python.exe"
$Main = Join-Path $InstallRoot "main.py"
$RequiredModels = @(
    (Join-Path $InstallRoot "models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors"),
    (Join-Path $InstallRoot "models\vae\wan2.2_vae.safetensors"),
    (Join-Path $InstallRoot "models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors"),
    (Join-Path $InstallRoot "models\checkpoints\sd_xl_base_1.0.safetensors"),
    (Join-Path $InstallRoot "models\frame_interpolation\rife_v4.26.safetensors")
)

if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath $Main)) {
    throw "ComfyUI is not installed. Run .\scripts\install_comfyui_wan22.ps1 first."
}
$Missing = $RequiredModels | Where-Object { -not (Test-Path -LiteralPath $_) }
if ($Missing) {
    throw "Missing local video quality models:`n$($Missing -join "`n")"
}

$Arguments = @(
    $Main,
    "--listen", "127.0.0.1",
    "--port", "8188",
    "--lowvram",
    "--preview-method", "none"
)
if ($Foreground) {
    & $Python @Arguments
    exit $LASTEXITCODE
}

$Process = Start-Process -FilePath $Python -ArgumentList $Arguments `
    -WorkingDirectory $InstallRoot -WindowStyle Hidden -PassThru
Write-Host "ComfyUI started in the background (PID $($Process.Id))."
Write-Host "Local API: http://127.0.0.1:8188"

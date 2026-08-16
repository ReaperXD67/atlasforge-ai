param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\AtlasForge\ComfyUI",
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$Parent = Split-Path -Parent $InstallRoot
$VenvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($InstallRoot).TrimEnd('\').TrimEnd(':'))
if (-not $SkipModels -and $drive.Free -lt 30GB) {
    throw "Wan 2.2 setup needs at least 30 GB free on $($drive.Name):."
}

New-Item -ItemType Directory -Force -Path $Parent | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot ".git"))) {
    git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git $InstallRoot
} else {
    git -C $InstallRoot pull --ff-only
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    uv venv (Join-Path $InstallRoot ".venv") --python 3.11
}

uv pip install --python $VenvPython torch torchvision torchaudio `
    --extra-index-url https://download.pytorch.org/whl/cu130
uv pip install --python $VenvPython -r (Join-Path $InstallRoot "requirements.txt")

function Get-LargeFile {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if ((Test-Path -LiteralPath $Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 1MB) {
        Write-Host "Already present: $Destination"
        return
    }
    $directory = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $partial = "$Destination.part"
    Write-Host "Downloading: $(Split-Path -Leaf $Destination)"
    & curl.exe -L --fail --retry 20 --retry-all-errors --retry-delay 4 `
        --connect-timeout 30 --speed-time 60 --speed-limit 1024 -C - -o $partial $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Url"
    }
    Move-Item -Force -LiteralPath $partial -Destination $Destination
}

if (-not $SkipModels) {
    Get-LargeFile `
        -Url "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors?download=true" `
        -Destination (Join-Path $InstallRoot "models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors")
    Get-LargeFile `
        -Url "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors?download=true" `
        -Destination (Join-Path $InstallRoot "models\vae\wan2.2_vae.safetensors")
    Get-LargeFile `
        -Url "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors?download=true" `
        -Destination (Join-Path $InstallRoot "models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors")
}

& $VenvPython -c "import torch; assert torch.cuda.is_available(); print('CUDA ready:', torch.cuda.get_device_name(0), 'torch', torch.__version__)"
if ($SkipModels) {
    Write-Host "ComfyUI runtime is ready at $InstallRoot; Wan model downloads were skipped."
} else {
    Write-Host "ComfyUI + Wan 2.2 are ready at $InstallRoot"
    Write-Host "Start with: .\scripts\start_comfyui.ps1"
}

param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\AtlasForge\ComfyUI",
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$Parent = Split-Path -Parent $InstallRoot
$VenvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($InstallRoot).TrimEnd('\').TrimEnd(':'))
if (-not $SkipModels -and $drive.Free -lt 38GB) {
    throw "The SDXL + Wan + RIFE setup needs at least 38 GB free on $($drive.Name):."
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
        [Parameter(Mandatory = $true)][string]$Destination,
        [string]$ExpectedSha256 = ""
    )
    if ((Test-Path -LiteralPath $Destination) -and (Get-Item -LiteralPath $Destination).Length -gt 1MB) {
        if ($ExpectedSha256) {
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
            if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
                throw "Checksum mismatch for existing model: $Destination"
            }
        }
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
    if ($ExpectedSha256) {
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash.ToLowerInvariant()
        if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
            Remove-Item -LiteralPath $partial -Force
            throw "Checksum mismatch after downloading: $Destination"
        }
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
    Get-LargeFile `
        -Url "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true" `
        -Destination (Join-Path $InstallRoot "models\checkpoints\sd_xl_base_1.0.safetensors") `
        -ExpectedSha256 "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
    Get-LargeFile `
        -Url "https://huggingface.co/Comfy-Org/frame_interpolation/resolve/main/frame_interpolation/rife_v4.26.safetensors?download=true" `
        -Destination (Join-Path $InstallRoot "models\frame_interpolation\rife_v4.26.safetensors") `
        -ExpectedSha256 "151874592c877740e5db11522f4514df569eeafb0a0fcb2696f16e9e8d317c94"
}

& $VenvPython -c "import torch; assert torch.cuda.is_available(); print('CUDA ready:', torch.cuda.get_device_name(0), 'torch', torch.__version__)"
if ($SkipModels) {
    Write-Host "ComfyUI runtime is ready at $InstallRoot; Wan model downloads were skipped."
} else {
    Write-Host "ComfyUI + SDXL + Wan 2.2 + RIFE are ready at $InstallRoot"
    Write-Host "Start with: .\scripts\start_comfyui.ps1"
}

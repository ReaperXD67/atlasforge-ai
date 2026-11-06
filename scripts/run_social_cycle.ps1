param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [string]$Config = "config/default.yaml",
    [switch]$SkipRender,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$pythonExe = Join-Path $projectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Install the project virtual environment first; see SETUP.md."
}

Push-Location -LiteralPath $projectRoot
try {
    $campaignPath = (Resolve-Path -LiteralPath $Campaign).Path
    $configPath = (Resolve-Path -LiteralPath $Config).Path
    try {
        $campaignData = Get-Content -LiteralPath $campaignPath -Raw | ConvertFrom-Json
    }
    catch {
        throw "Campaign JSON could not be read or parsed; sensitive input is omitted."
    }
    $manifestReference = [string]$campaignData.production_manifest
    if ([string]::IsNullOrWhiteSpace($manifestReference) -or [IO.Path]::IsPathRooted($manifestReference)) {
        throw "production_manifest must be a repository-relative path."
    }
    $manifestPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $manifestReference))
    $rootPrefix = $projectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $manifestPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "production_manifest escapes the repository."
    }
    if (-not $SkipRender) {
        & $pythonExe -m daily_video_factory.cli render-production-batch --manifest $manifestPath
        if ($LASTEXITCODE -ne 0) { throw "Production failed; publication was not attempted." }
    }
    & $pythonExe -m daily_video_factory.cli social enqueue --campaign $campaignPath --config $configPath
    if ($LASTEXITCODE -ne 0) { throw "Queue validation failed; publication was not attempted." }
    $workerArgs = @("-m", "daily_video_factory.cli", "social", "run-due", "--config", $configPath)
    if ($Publish) { $workerArgs += "--execute" }
    & $pythonExe @workerArgs
    if ($LASTEXITCODE -ne 0) { throw "A publish job needs attention. Inspect social status before retrying." }
    & $pythonExe -m daily_video_factory.cli social report --output output/social/learning.json
    if ($LASTEXITCODE -ne 0) { throw "Analytics report failed. Publication receipts remain saved." }
}
catch {
    Write-Error "Social cycle stopped. Check the campaign schema, repository paths and structured CLI status. Sensitive error details are omitted." -ErrorAction Continue
    exit 1
}
finally {
    Pop-Location
}

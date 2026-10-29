param(
    [ValidateSet("cpu", "demo_gpu", "safe_gpu")]
    [string]$Profile = "demo_gpu",
    [switch]$SkipTests,
    [switch]$SkipHealth,
    [switch]$Strict,
    [switch]$Offline
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
$py = Get-MedhaPython -Root $root
Set-Location -LiteralPath $root
if ($Offline) { Set-MedhaOffline }

$script:failed = @()
function Invoke-Step {
    param([string]$Name, [scriptblock]$Body)
    Write-Host ""
    Write-Host "== $Name =="
    & $Body
    if ($LASTEXITCODE -ne 0) {
        $script:failed += $Name
        Write-Warning "$Name failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "ruff" { & $py -m ruff check . }
Invoke-Step "mypy" { & $py -m mypy medha tests tools }

if (-not $SkipTests) {
    Invoke-Step "pytest" { & $py -m pytest -q }
}

Invoke-Step "pip check" { & $py -m pip check }
Invoke-Step "license audit" { & $py (Join-Path $root "tools\license_audit.py") }

if (-not $SkipHealth) {
    Invoke-Step "environment health" {
        $healthArgs = @("--health")
        if ($Strict) { $healthArgs += "--strict" }
        & $py -m medha @healthArgs
    }
}

Invoke-Step "offline audit" {
    & $py (Join-Path $root "tools\offline_audit.py") --profile $Profile
}

Write-Host ""
if ($script:failed.Count -gt 0) {
    Write-Host "Verification failed: $($script:failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "All checks passed." -ForegroundColor Green
exit 0

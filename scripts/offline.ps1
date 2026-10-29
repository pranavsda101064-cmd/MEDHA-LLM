param(
    [ValidateSet("cpu", "demo_gpu", "safe_gpu")]
    [string]$Profile = "demo_gpu",
    [switch]$AuditOnly,
    [string]$Lesson,
    [switch]$NoTTS
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
$py = Get-MedhaPython -Root $root
Set-Location -LiteralPath $root
Set-MedhaOffline

$null = Start-MedhaOllama
Write-Host "Auditing offline readiness for profile $Profile..."
& $py (Join-Path $root "tools\offline_audit.py") --profile $Profile
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Offline audit failed. Fix the items above before demoing."
    exit $LASTEXITCODE
}

if ($AuditOnly) {
    exit 0
}

$launch = Join-Path $PSScriptRoot "launch.ps1"
$launchArgs = @("-Offline")
if ($Lesson) { $launchArgs += @("-Lesson", $Lesson) }
if ($NoTTS) { $launchArgs += "-NoTTS" }

& $launch @launchArgs
exit $LASTEXITCODE

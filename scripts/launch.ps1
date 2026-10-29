param(
    [string]$Lesson,
    [switch]$NoTTS,
    [switch]$Health,
    [switch]$Strict,
    [switch]$Smoke,
    [string]$Screenshot,
    [double]$At = 8.0,
    [switch]$Offline
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
$py = Get-MedhaPython -Root $root
Set-Location -LiteralPath $root

if ($Offline) {
    Set-MedhaOffline
}

if ($Health) {
    $healthArgs = @("--health")
    if ($Strict) { $healthArgs += "--strict" }
    & $py -m medha @healthArgs
    exit $LASTEXITCODE
}

$null = Start-MedhaOllama

$medhaArgs = @()
if ($Lesson) {
    $medhaArgs += @("--lesson", (Resolve-Path -LiteralPath $Lesson).Path)
}
if ($NoTTS) { $medhaArgs += "--no-tts" }
if ($Smoke) { $medhaArgs += "--smoke" }
if ($Screenshot) {
    $medhaArgs += @("--screenshot", [System.IO.Path]::GetFullPath($Screenshot))
}
if ($At -gt 0) { $medhaArgs += @("--at", $At.ToString([System.Globalization.CultureInfo]::InvariantCulture)) }

& $py -m medha @medhaArgs
exit $LASTEXITCODE

param(
    [switch]$NoTTS,
    [switch]$Offline
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
Set-Location -LiteralPath $root

$lesson = Join-Path $root "content\lessons\newton.json"
if (-not (Test-Path -LiteralPath $lesson)) {
    $lesson = Join-Path $root "spec\board-action\v1\examples\newton.json"
}
if (-not (Test-Path -LiteralPath $lesson)) {
    throw "Demo lesson not found. Run scripts\setup.ps1 first."
}

$launch = Join-Path $PSScriptRoot "launch.ps1"
$launchArgs = @("-Lesson", $lesson)
if ($NoTTS) { $launchArgs += "-NoTTS" }
if ($Offline) { $launchArgs += "-Offline" }

& $launch @launchArgs
exit $LASTEXITCODE

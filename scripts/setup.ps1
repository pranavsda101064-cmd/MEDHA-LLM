param(
    [ValidateSet("cpu", "demo_gpu", "safe_gpu")]
    [string]$Profile = "demo_gpu",
    [string]$Python = "python",
    [switch]$SkipModels,
    [switch]$WithIndic,
    [switch]$SkipHealth
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
Set-Location -LiteralPath $root
$exitCode = 0

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12 was not found. Install it from https://www.python.org/downloads/."
}
& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Medha needs Python 3.12 or newer."
}

$venv = Join-Path $root ".venv"
if (-not (Test-Path -LiteralPath $venv)) {
    Write-Host "Creating .venv..."
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }
}

$py = Get-MedhaPython -Root $root
& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

Write-Host "Installing Medha requirements..."
& $py -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Requirement installation failed." }

if ($WithIndic) {
    Write-Host "Installing optional Hindi/Kannada requirements..."
    & $py -m pip install -r (Join-Path $root "requirements\indic.txt")
    if ($LASTEXITCODE -ne 0) { throw "Indic requirement installation failed." }
}

if (-not $SkipModels) {
    $null = Start-MedhaOllama
    Write-Host "Fetching models for profile $Profile..."
    & $py (Join-Path $root "tools\fetch_models.py") --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        $exitCode = 1
        Write-Warning "Some models are missing. Re-run scripts\setup.ps1 when Ollama is available."
    }
    & $py (Join-Path $root "tools\fetch_docling.py")
    if ($LASTEXITCODE -ne 0) {
        $exitCode = 1
        Write-Warning "Docling artifacts are incomplete; PDF and DOCX ingestion may be unavailable."
    }
}

if (-not $SkipHealth) {
    Write-Host "Checking the environment..."
    & $py -m medha --health
    if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Setup finished. Start Medha with: .\scripts\launch.ps1"
} else {
    Write-Warning "Setup finished with missing pieces. Review the warnings above."
}
exit $exitCode

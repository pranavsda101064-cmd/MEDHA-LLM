Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-MedhaRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-MedhaPython {
    param([Parameter(Mandatory = $true)][string]$Root)
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Missing .venv. Run scripts\setup.ps1 first."
    }
    return $python
}

function Set-MedhaOffline {
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_DATASETS_OFFLINE = "1"
    $env:HF_HUB_DISABLE_TELEMETRY = "1"
    $env:DO_NOT_TRACK = "1"
}

function Test-MedhaOllama {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

function Start-MedhaOllama {
    if (Test-MedhaOllama) {
        return $true
    }
    if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
        Write-Warning "Ollama is not installed. Install it from https://ollama.com/download."
        return $false
    }
    Write-Host "Starting Ollama..."
    $env:OLLAMA_FLASH_ATTENTION = "1"
    $env:OLLAMA_KV_CACHE_TYPE = "q8_0"
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
    $env:OLLAMA_NUM_PARALLEL = "1"
    $env:OLLAMA_KEEP_ALIVE = "15m"
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-MedhaOllama) {
            return $true
        }
    }
    Write-Warning "Ollama did not become ready at http://127.0.0.1:11434."
    return $false
}

param(
    [switch]$NoDesktop,
    [switch]$NoStartMenu
)

. (Join-Path $PSScriptRoot "_common.ps1")

$root = Get-MedhaRoot
$launch = Join-Path $root "scripts\launch.ps1"
$icon = Join-Path $root "assets\medha.ico"

if (-not (Test-Path -LiteralPath $launch)) {
    throw "Missing launcher: $launch"
}
if (-not (Test-Path -LiteralPath $icon)) {
    throw "Missing icon: $icon"
}

$powershell = Join-Path $PSHOME "powershell.exe"
$launchArguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launch`""
$shell = New-Object -ComObject WScript.Shell
$created = @()

function New-MedhaShortcut {
    param([Parameter(Mandatory = $true)][string]$Path)

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = $launchArguments
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = "Medha offline AI blackboard teacher"
    $shortcut.Save()
    $script:created += $Path
}

if (-not $NoDesktop) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    New-MedhaShortcut -Path (Join-Path $desktop "Medha Studio.lnk")
}

if (-not $NoStartMenu) {
    $programs = [Environment]::GetFolderPath("Programs")
    New-MedhaShortcut -Path (Join-Path $programs "Medha Studio.lnk")
}

Write-Host "Created shortcut(s):"
foreach ($path in $created) {
    Write-Host "  $path"
}
Write-Host ""
Write-Host "Double-click 'Medha Studio' to launch. You can also pin it to the taskbar."

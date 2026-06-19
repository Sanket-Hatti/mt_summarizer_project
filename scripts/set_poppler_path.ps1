<#
sets POPPLER_PATH for the current user and updates the current PowerShell session PATH
Usage: run as normal user PowerShell (no admin required):
    .\scripts\set_poppler_path.ps1 -PopplerBin "C:\Program Files\poppler-23.12.0\bin"
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$PopplerBin
)

if (-not (Test-Path $PopplerBin)) {
    Write-Error "The path '$PopplerBin' does not exist. Please extract Poppler and pass the path to its 'bin' folder."
    return 1
}

# Persist for current user
[Environment]::SetEnvironmentVariable('POPPLER_PATH', $PopplerBin, 'User')

# Update current session environment
$env:POPPLER_PATH = $PopplerBin
if ($env:PATH -notlike "*$PopplerBin*") {
    $env:PATH = $PopplerBin + ';' + $env:PATH
}

Write-Output "POPPLER_PATH set to: $PopplerBin"
Write-Output "Added to current session PATH. To make this change visible in other shells, sign out/in or start a new shell."

# Quick verification
Write-Output "\nVerifying pdftoppm availability (in this session):"
try {
    $pp = Get-Command pdftoppm -ErrorAction Stop
    Write-Output "pdftoppm found at: $($pp.Path)"
    pdftoppm -v 2>&1 | Select-String -Pattern '.'
} catch {
    Write-Output "pdftoppm still not found in PATH. Check that you passed the correct 'bin' folder containing pdftoppm.exe." 
}

return 0

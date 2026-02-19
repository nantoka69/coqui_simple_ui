# PowerShell script to run the Coqui TTS Simple UI
# This script activates the 'coqui_env' conda environment and runs app.py

# Set working directory to the script's location
Set-Location -Path $PSScriptRoot

# Hardcoded standard path for Miniconda on Windows 11
$CondaPath = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"

# If conda doesn't exist, try to report it (though it might be hidden)
if (!(Test-Path $CondaPath)) {
    Write-Error "Conda not found at $CondaPath."
    exit 1
}

# Run the UI using conda run (which sets up environment variables) and python (for debugging)
& "$CondaPath" run -n coqui_env --no-capture-output python app.py



if ($LASTEXITCODE -ne 0) {
    Write-Host "Application exited with an error (Code: $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Press any key to close..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
else {
    Write-Host "Application closed successfully." -ForegroundColor Cyan
}

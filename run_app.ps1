# PowerShell script to launch Coqui TTS Simple UI without lingering wrappers
# Uses `conda run` to execute pythonw.exe inside the environment and detaches the process.

$CondaExe = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
$PythonW = "$env:USERPROFILE\miniconda3\envs\coqui_env\pythonw.exe"
$AppPath = "$PSScriptRoot\app.py"

# Build the argument list for conda run
$Args = "run -n coqui_env --no-capture-output $PythonW `"$AppPath`""

# Start the process hidden; PowerShell exits immediately after spawning.
Start-Process -FilePath $CondaExe -ArgumentList $Args -WorkingDirectory $PSScriptRoot -WindowStyle Hidden

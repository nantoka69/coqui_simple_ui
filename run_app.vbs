Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Launch run_app.ps1 in a hidden PowerShell window.
' The PS1 activates the conda env, then detaches pythonw.exe via Start-Process and exits.
strPS1 = strPath & "\run_app.ps1"
strCmd = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & strPS1 & """"

WshShell.Run strCmd, 0, False






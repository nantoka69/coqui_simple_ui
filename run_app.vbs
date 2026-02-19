Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strUserProf = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")
strConda = strUserProf & "\miniconda3\Scripts\conda.exe"

' Construct command: "C:\...\conda.exe" run -n coqui_env --no-capture-output pythonw.exe "C:\...\app.py"
strArgs = """" & strConda & """ run -n coqui_env --no-capture-output pythonw.exe """ & strPath & "\app.py"""

' Run hidden (0) and don't wait (False)
WshShell.Run strArgs, 0, False



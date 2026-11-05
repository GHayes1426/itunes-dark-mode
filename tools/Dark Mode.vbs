Option Explicit
Dim folder, shell, python, app
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
python = folder & "\diagnostics-venv\Scripts\pythonw.exe"
app = folder & "\Dark Mode.pyw"
Set shell = CreateObject("WScript.Shell")
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & app & Chr(34), 0, False

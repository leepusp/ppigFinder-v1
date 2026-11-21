Option Explicit

Dim shell, files, scripts, root, python, installer, launch, problem
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
scripts = files.GetParentFolderName(WScript.ScriptFullName)
root = files.GetParentFolderName(scripts)
installer = files.BuildPath(scripts, "install_ppigfinder.py")
python = files.BuildPath(root, ".venv\Scripts\pythonw.exe")

If files.FileExists(python) Then
    launch = Quote(python)
Else
    launch = "pyw.exe -3"
End If

On Error Resume Next
shell.Run launch & " " & Quote(installer), 0, False
problem = Err.Number
On Error GoTo 0
If problem <> 0 Then
    MsgBox "Install Python 3.11 or newer with Tcl/Tk and the Windows Python launcher, then open this installer again.", vbExclamation, "ppigFinder Setup"
End If

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function

' AgentForge, with no console window at all.
'
' Double-clicking start.bat opens a console for as long as the checks and any
' first-run install take, and a desktop shortcut to a .bat always shows one.
' wscript.exe is not a console program, so nothing is created here: the batch
' file runs hidden and Electron appears on its own.
'
' AGENTFORGE_QUIET tells start.bat not to `pause` on an error. A pause in a
' hidden window waits forever for a keypress nobody can give it, which is a
' launcher that silently never returns.
'
' The run is waited on, which costs nothing - start.bat hands Electron its own
' process and exits immediately - and means a refusal can be reported instead
' of disappearing.

Option Explicit

Dim shell, fso, here, logFile, command, code
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

here = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = fso.BuildPath(here, "start.log")

shell.CurrentDirectory = here
shell.Environment("PROCESS")("AGENTFORGE_QUIET") = "1"

command = "cmd /c """"" & fso.BuildPath(here, "start.bat") & """ > """ & logFile & """ 2>&1"""

' 0 = hidden window, True = wait for it to finish.
code = shell.Run(command, 0, True)

If code <> 0 Then
  MsgBox "AgentForge could not start." & vbCrLf & vbCrLf & _
         "What went wrong is written in:" & vbCrLf & logFile, _
         vbExclamation, "AgentForge"
End If

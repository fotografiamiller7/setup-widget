' Abre o widget como administrador (necessário para temperatura da CPU) sem janela de console.
Set sh = CreateObject("Shell.Application")
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)

' Localiza o pythonw.exe: primeiro pelo PATH, depois nas pastas padrão do instalador.
pyw = ""
On Error Resume Next
pyw = ws.Exec("cmd /c where pythonw.exe").StdOut.ReadLine()
On Error GoTo 0
If pyw = "" Or Not fso.FileExists(pyw) Then
    base = ws.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python"
    If fso.FolderExists(base) Then
        For Each d In fso.GetFolder(base).SubFolders
            If fso.FileExists(d.Path & "\pythonw.exe") Then pyw = d.Path & "\pythonw.exe"
        Next
    End If
End If
If pyw = "" Then
    MsgBox "pythonw.exe não encontrado. Instale o Python 3 e rode o setup.ps1.", 16, "Setup Widget"
    WScript.Quit 1
End If

sh.ShellExecute pyw, """" & pasta & "\widget.py""", pasta, "runas", 0

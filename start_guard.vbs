' start_guard.vbs
'
' Silent launcher for Windows. Runs the guard in the background (no console window).
' To auto-start on login, place a shortcut to this file in your Startup folder:
'   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
'
' IMPORTANT: Edit the two paths below to match your setup.

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\path\to\telegram-undelete"          ' ← Change this
WshShell.Run "pythonw.exe guard.py", 0, False                       ' ← Change "pythonw.exe" to full path if not in PATH

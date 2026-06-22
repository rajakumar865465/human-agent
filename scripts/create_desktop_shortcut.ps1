# Creates a Windows desktop shortcut to the Visual Supervisor Dashboard launcher
$projectRoot = Split-Path -Parent $PSScriptRoot
$batFile = Join-Path $projectRoot "scripts\start_desktop_ui.bat"
$shortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Visual Supervisor.lnk"

$WScript = New-Object -ComObject WScript.Shell
$shortcut = $WScript.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batFile
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Start Visual Supervisor Dashboard"
$shortcut.IconLocation = "shell32.dll,137"
$shortcut.Save()

Write-Host "Shortcut created at: $shortcutPath"
Write-Host "Double-click 'Visual Supervisor' on your desktop to launch the dashboard."

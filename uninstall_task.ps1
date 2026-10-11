$ErrorActionPreference = 'Stop'
$taskName = 'CodexClassReminder'
$schtasks = Join-Path $env:SystemRoot 'System32\schtasks.exe'
& $schtasks /Delete /TN $taskName /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Output '没有找到课程提醒任务。'
} else {
    Write-Output '已移除课程提醒任务。程序和课表文件仍保留。'
}
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
foreach ($name in @('课程助手.lnk', '每日课程提醒-系统通知.lnk')) {
    $shortcut = Join-Path $startMenu $name
    if (Test-Path -LiteralPath $shortcut) { Remove-Item -LiteralPath $shortcut -Force }
}
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) '课程助手.lnk'
if (Test-Path -LiteralPath $desktopShortcut) { Remove-Item -LiteralPath $desktopShortcut -Force }

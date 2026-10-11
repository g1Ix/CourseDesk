param([Parameter(Mandatory=$true)][string]$Executable,[string]$Arguments='--notify-tomorrow',[string]$Time='23:55',[string]$Enabled='true',[string]$TaskName='CodexClassReminder',[switch]$Preview)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
if ($Time -notmatch '^([01][0-9]|2[0-3]):[0-5][0-9]$') { throw '提醒时间格式无效。' }
$identity=[Security.SecurityElement]::Escape([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$command=[Security.SecurityElement]::Escape($Executable)
$argument=[Security.SecurityElement]::Escape($Arguments)
$directory=[Security.SecurityElement]::Escape((Split-Path -Parent $Executable))
$flag=if($Enabled -eq 'true'){'true'}else{'false'}
$boundary=(Get-Date -Format 'yyyy-MM-dd')+'T'+$Time+':00'
$xml=@"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo><Description>课程助手：每天提醒次日课程，无课时保持安静。</Description></RegistrationInfo>
<Triggers><CalendarTrigger><StartBoundary>$boundary</StartBoundary><Enabled>$flag</Enabled><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers>
<Principals><Principal id="Author"><UserId>$identity</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
<Settings><Enabled>$flag</Enabled><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><WakeToRun>true</WakeToRun><ExecutionTimeLimit>PT2M</ExecutionTimeLimit></Settings>
<Actions Context="Author"><Exec><Command>$command</Command><Arguments>$argument</Arguments><WorkingDirectory>$directory</WorkingDirectory></Exec></Actions>
</Task>
"@
if($Preview){Write-Output $xml;exit 0}
$temp=Join-Path $env:TEMP ('coursedesk-'+[Guid]::NewGuid().ToString('N')+'.xml')
try {
    [IO.File]::WriteAllText($temp,$xml,[Text.Encoding]::Unicode)
    & "$env:SystemRoot\System32\schtasks.exe" /Create /TN $TaskName /XML $temp /F | Out-Null
    if($LASTEXITCODE -ne 0){throw "Windows 未能保存提醒任务（代码 $LASTEXITCODE）。"}
} finally { if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force} }
Write-Output 'OK'

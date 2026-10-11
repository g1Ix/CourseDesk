param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Body
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

$safeTitle=[Security.SecurityElement]::Escape($Title)
$lines=$Body -split "`n"
$content=for($i=0;$i -lt $lines.Count;$i++) {
    $safeLine=[Security.SecurityElement]::Escape($lines[$i])
    $style=if($i % 2 -eq 0){'body'}else{'captionSubtle'}
    "<text hint-style='$style' hint-wrap='true' hint-maxLines='2'>$safeLine</text>"
}
$xml=[Windows.Data.Xml.Dom.XmlDocument]::new()
$xml.LoadXml("<toast duration='long'><visual><binding template='ToastGeneric'><text>$safeTitle</text><group><subgroup>$($content -join '')</subgroup></group></binding></visual><audio silent='false'/></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Codex.ClassReminder')
$notifier.Show($toast)

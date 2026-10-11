$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $root 'CourseAssistant.exe')) {
    $app = Join-Path $root 'CourseAssistant.exe'
} else {
    $app = Join-Path $root 'desktop\CourseAssistant\CourseAssistant.exe'
}

if (-not (Test-Path -LiteralPath $app)) { throw "找不到桌面版程序：$app。请先运行 build_desktop.ps1。" }

$appId = 'Codex.ClassReminder'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shortcutPath = Join-Path $startMenu '课程助手.lnk'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
$desktopPath = [Environment]::GetFolderPath('Desktop')
$desktopShortcutPath = Join-Path $desktopPath '课程助手.lnk'
$iconDirectory = Join-Path $env:LOCALAPPDATA 'CourseDesk\icons'
New-Item -ItemType Directory -Path $iconDirectory -Force | Out-Null
$iconPath = Join-Path $iconDirectory 'coursedesk-1.0.0.ico'
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $app) '_internal\assets\app.ico') -Destination $iconPath -Force

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;

[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IReminderShellLink {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int maxPath, IntPtr findData, uint flags);
    void GetIDList(out IntPtr idList);
    void SetIDList(IntPtr idList);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int maxName);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder directory, int maxPath);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string directory);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder arguments, int maxPath);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
    void GetHotkey(out short hotkey);
    void SetHotkey(short hotkey);
    void GetShowCmd(out int showCommand);
    void SetShowCmd(int showCommand);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder iconPath, int maxPath, out int iconIndex);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string iconPath, int iconIndex);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
    void Resolve(IntPtr window, uint flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
}

[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IReminderPropertyStore {
    [PreserveSig] int GetCount(out uint count);
    [PreserveSig] int GetAt(uint index, out ReminderPropertyKey key);
    [PreserveSig] int GetValue(ref ReminderPropertyKey key, out ReminderPropVariant value);
    [PreserveSig] int SetValue(ref ReminderPropertyKey key, ref ReminderPropVariant value);
    [PreserveSig] int Commit();
}

[ComImport, Guid("0000010B-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IReminderPersistFile {
    void GetClassID(out Guid classId);
    [PreserveSig] int IsDirty();
    void Load([MarshalAs(UnmanagedType.LPWStr)] string fileName, uint mode);
    void Save([MarshalAs(UnmanagedType.LPWStr)] string fileName, bool remember);
    void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string fileName);
    void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string fileName);
}

[StructLayout(LayoutKind.Sequential)]
public struct ReminderPropertyKey {
    public Guid FormatId;
    public uint PropertyId;
    public ReminderPropertyKey(Guid formatId, uint propertyId) { FormatId = formatId; PropertyId = propertyId; }
}

[StructLayout(LayoutKind.Explicit, Size = 16)]
public struct ReminderPropVariant {
    [FieldOffset(0)] public ushort VariantType;
    [FieldOffset(8)] public IntPtr StringValue;
}

public static class ReminderShortcutBuilder {
    [DllImport("shell32.dll", CharSet=CharSet.Unicode)]
    static extern void SHChangeNotify(uint eventId, uint flags, string item1, string item2);
    public static void Refresh(string path) { SHChangeNotify(0x00002000, 0x1005, path, null); SHChangeNotify(0x08000000, 0x1000, null, null); }
    public static void Create(string shortcutPath, string target, string arguments, string workingDirectory, string description, string appId, string iconPath) {
        Type shellLinkType = Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046"));
        object shellLinkObject = Activator.CreateInstance(shellLinkType);
        IReminderShellLink shellLink = (IReminderShellLink)shellLinkObject;
        shellLink.SetPath(target);
        shellLink.SetArguments(arguments);
        shellLink.SetWorkingDirectory(workingDirectory);
        shellLink.SetDescription(description);
        shellLink.SetIconLocation(iconPath, 0);
        shellLink.SetShowCmd(1);
        IReminderPropertyStore store = (IReminderPropertyStore)shellLinkObject;
        ReminderPropertyKey key = new ReminderPropertyKey(new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5);
        IntPtr text = Marshal.StringToCoTaskMemUni(appId);
        try {
            ReminderPropVariant value = new ReminderPropVariant { VariantType = 31, StringValue = text };
            Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value));
            Marshal.ThrowExceptionForHR(store.Commit());
            ((IReminderPersistFile)shellLinkObject).Save(shortcutPath, true);
        } finally {
            Marshal.FreeCoTaskMem(text);
            Marshal.ReleaseComObject(shellLinkObject);
        }
    }
}
'@
[ReminderShortcutBuilder]::Create($shortcutPath, $app, '', (Split-Path -Parent $app), '浏览课表并提醒明天的课程', $appId, $iconPath)
[ReminderShortcutBuilder]::Create($desktopShortcutPath, $app, '', (Split-Path -Parent $app), '浏览课表并提醒明天的课程', $appId, $iconPath)
[ReminderShortcutBuilder]::Refresh($shortcutPath)
[ReminderShortcutBuilder]::Refresh($desktopShortcutPath)

$preferencesPath = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'CourseDesk\preferences.json'
$time = '23:55'
$enabled = 'true'
if (Test-Path -LiteralPath $preferencesPath) {
    $preferences = Get-Content -LiteralPath $preferencesPath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($preferences.reminder_time) { $time = $preferences.reminder_time }
    if ($preferences.reminder_enabled -eq $false) { $enabled = 'false' }
}
$helper = Join-Path (Split-Path -Parent $app) '_internal\register_reminder.ps1'
& $helper -Executable $app -Time $time -Enabled $enabled
foreach ($oldName in @('课程提醒.lnk', '每日课程提醒.lnk', '每日课程提醒-系统通知.lnk')) {
    $oldShortcut = Join-Path $startMenu $oldName
    if (Test-Path -LiteralPath $oldShortcut) { Remove-Item -LiteralPath $oldShortcut -Force }
}

Write-Output "已设置每日 $time 提醒任务（启用状态：$enabled）。"
Write-Output '任务仅在当前用户已登录时显示通知；错过计划时间后会在下次可运行时补执行。'

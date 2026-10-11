$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$archive = Get-ChildItem -LiteralPath (Join-Path $root 'release') -Filter 'CourseDesk-*-Windows-x64.zip' | Select-Object -First 1
if (-not $archive) { throw 'Build a portable release first.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive.FullName)
try {
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -match '(^|[/\\])(timetable\.json|schedule\.json|preferences\.json|last-preview\.json|ui-greetings\.json|backups|previews)([/\\]|$)' -or $entry.FullName -match '\.log$') {
            throw "Private data path in archive: $($entry.FullName)"
        }
    }
} finally { $zip.Dispose() }
$profile = Join-Path $root ('build\package-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profile -Force | Out-Null
$previousData = $env:COURSEDESK_DATA_DIR
$previousActions = $env:COURSEDESK_NO_OS_ACTIONS
try {
    $env:COURSEDESK_DATA_DIR = $profile
    $env:COURSEDESK_NO_OS_ACTIONS = '1'
    $exe = Join-Path $root 'portable\CourseAssistant.exe'
    $process = Start-Process -FilePath $exe -ArgumentList '--dry-run' -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(30000)) { $process.Kill();throw 'Packaged first launch timed out.' }
    if ($process.ExitCode -ne 0) { throw "Packaged launch failed: $($process.ExitCode)" }
    $data = Get-Content -LiteralPath (Join-Path $profile 'schedule.json') -Raw -Encoding utf8 | ConvertFrom-Json
    $preview = Get-Content -LiteralPath (Join-Path $profile 'last-preview.json') -Raw -Encoding utf8 | ConvertFrom-Json
    if (@($data.weekly_rules).Count -ne 0 -or @($data.exceptions).Count -ne 0 -or @($preview.classes).Count -ne 0) { throw 'New users must start with an empty timetable.' }
    Write-Output 'PASS: archive contains no user data; packaged EXE starts without Python and creates an empty timetable.'
} finally {
    $env:COURSEDESK_DATA_DIR = $previousData
    $env:COURSEDESK_NO_OS_ACTIONS = $previousActions
}

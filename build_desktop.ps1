param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $PythonExe) {
    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) { $PythonExe = $venvPython }
    else { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$dist = Join-Path $root 'desktop'
$work = Join-Path $root 'build\pyinstaller'
$portable = Join-Path $root 'portable'
foreach ($required in @('course_assistant.py', 'assets\app.ico', 'assets\app.png', 'toast_notification.ps1', 'windows_ocr.ps1', 'register_reminder.ps1', 'LICENSE', 'USER_GUIDE.md', 'THIRD_PARTY_NOTICES.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $required))) { throw "Missing build input: $required" }
}
function Clear-BuildDirectory([string]$name) {
    $target = [IO.Path]::GetFullPath((Join-Path $root $name))
    $boundary = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
    if (-not $target.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase) -or $name -notin @('desktop', 'portable')) { throw 'Unsafe build cleanup path.' }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
Clear-BuildDirectory 'desktop'
& $PythonExe -m PyInstaller --noconfirm --clean --onedir --windowed --name CourseAssistant `
    --distpath $dist --workpath $work --specpath $work --icon "$root\assets\app.ico" `
    --version-file "$root\version_info.txt" --add-data "$root\assets;assets" `
    --add-data "$root\toast_notification.ps1;." --add-data "$root\windows_ocr.ps1;." `
    --add-data "$root\register_reminder.ps1;." --hidden-import PySide6.QtPdf "$root\course_assistant.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
$appFolder = Join-Path $dist 'CourseAssistant'
Copy-Item -LiteralPath "$root\LICENSE", "$root\USER_GUIDE.md", "$root\THIRD_PARTY_NOTICES.txt" -Destination $appFolder
$sourceFolder = Join-Path $appFolder 'source'
New-Item -ItemType Directory -Path $sourceFolder -Force | Out-Null
Get-ChildItem -LiteralPath $root -File | Where-Object { $_.Name -match '^(course_.*|desktop_entry)\.py$' } | Copy-Item -Destination $sourceFolder
$licenses = Join-Path $appFolder 'licenses'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
Copy-Item -LiteralPath "$root\licenses\uiverse-smart-emu-83.txt" -Destination $licenses
# Locate distribution licenses from the selected interpreter, including virtualenvs.
$licenseScript = @'
import importlib.metadata as md, pathlib, shutil, sys
target=pathlib.Path(sys.argv[1])
for name in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','pyinstaller'):
    dist=md.distribution(name)
    for f in dist.files or []:
        if '.dist-info/licenses/' in str(f).replace('\\','/'):
            suffix=str(f).replace('\\','/').split('.dist-info/licenses/',1)[1]
            dest=target/name/suffix
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dist.locate_file(f),dest)
for base in (pathlib.Path(sys.base_prefix),pathlib.Path(sys.executable).parent):
    p=base/'LICENSE.txt'
    if p.exists():shutil.copy2(p,target/'Python.txt');break
else:raise SystemExit('Python LICENSE.txt not found; cannot distribute without notices.')
'@
& $PythonExe -c $licenseScript $licenses
if ($LASTEXITCODE -ne 0) { throw 'Dependency license collection failed.' }
# Host applications can pollute PATH with incompatible ICU DLLs.
foreach ($name in @('icuuc.dll', 'icudt78.dll')) {
    $candidate = Join-Path $appFolder "_internal\$name"
    if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
}
Clear-BuildDirectory 'portable'
New-Item -ItemType Directory -Path $portable -Force | Out-Null
Copy-Item -Path "$appFolder\*" -Destination $portable -Recurse
Copy-Item -LiteralPath "$root\install_task.ps1", "$root\uninstall_task.ps1" -Destination $portable
$version = (& $PythonExe -c "import sys;sys.path.insert(0,sys.argv[1]);from course_data import VERSION;print(VERSION)" $root | Select-Object -Last 1).Trim()
$release = Join-Path $root 'release'
New-Item -ItemType Directory -Path $release -Force | Out-Null
$zip = Join-Path $release "CourseDesk-$version-Windows-x64.zip"
Compress-Archive -Path "$portable\*" -DestinationPath $zip -CompressionLevel Optimal -Force
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($zip))" | Set-Content -LiteralPath "$release\SHA256SUMS.txt" -Encoding ascii
Write-Output "Portable application: $appFolder\CourseAssistant.exe"
Write-Output "Release archive: $zip"

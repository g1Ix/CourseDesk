param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Paths)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Wait-WinRT($Operation, [Type]$ResultType) {
    if ($ResultType.FullName -eq 'Windows.Foundation.IAsyncAction') {
        $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
            Where-Object { $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
            Select-Object -First 1
        $task = $method.Invoke($null, @($Operation))
        $task.GetAwaiter().GetResult()
        return
    }
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

$language = [Windows.Media.Ocr.OcrEngine, Windows, ContentType=WindowsRuntime]::AvailableRecognizerLanguages |
    Where-Object { $_.LanguageTag -like 'zh-Hans*' } | Select-Object -First 1
$pagesOut = [System.Collections.Generic.List[object]]::new()
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.IO;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class CourseContrast {
 public static byte[] Render(byte[] input) {
  using(var s=new MemoryStream(input)) using(var original=new Bitmap(s))
  using(var bitmap=new Bitmap(original.Width,original.Height,PixelFormat.Format32bppArgb)) {
   using(var g=Graphics.FromImage(bitmap)) g.DrawImageUnscaled(original,0,0);
   var locked=bitmap.LockBits(new Rectangle(0,0,bitmap.Width,bitmap.Height),ImageLockMode.ReadWrite,PixelFormat.Format32bppArgb);
   var bytes=new byte[Math.Abs(locked.Stride)*bitmap.Height]; Marshal.Copy(locked.Scan0,bytes,0,bytes.Length);
   for(int i=0;i<bytes.Length;i+=4) {byte c=(byte)(bytes[i]>=230&&bytes[i+1]>=230&&bytes[i+2]>=230?0:255);bytes[i]=bytes[i+1]=bytes[i+2]=c;bytes[i+3]=255;}
   Marshal.Copy(bytes,0,locked.Scan0,bytes.Length);bitmap.UnlockBits(locked);
   using(var output=new MemoryStream()) {bitmap.Save(output,ImageFormat.Png);return output.ToArray();}
  }
 }
}
'@
function New-ImageStream([byte[]]$Bytes) {
    $s = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows, ContentType=WindowsRuntime]::new()
    $w = [Windows.Storage.Streams.DataWriter, Windows, ContentType=WindowsRuntime]::new($s)
    $w.WriteBytes($Bytes)
    Wait-WinRT ($w.StoreAsync()) ([uint32]) | Out-Null
    $null=$w.DetachStream();$w.Dispose();$s.Seek(0) | Out-Null
    return $s
}
function Read-ContrastLines($Stream) {
    $Stream.Seek(0) | Out-Null
    $reader=[Windows.Storage.Streams.DataReader, Windows, ContentType=WindowsRuntime]::new($Stream)
    Wait-WinRT ($reader.LoadAsync([uint32]$Stream.Size)) ([uint32]) | Out-Null
    $bytes=New-Object byte[] ([int]$Stream.Size);$reader.ReadBytes($bytes);$null=$reader.DetachStream();$reader.Dispose()
    $contrast=New-ImageStream ([CourseContrast]::Render($bytes))
    try {
        $decoder=Wait-WinRT ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime]::CreateAsync($contrast)) ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime])
        $bitmap=Read-OcrBitmap $decoder
        $result=Wait-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult, Windows, ContentType=WindowsRuntime])
        & $makeLines $result
        $bitmap.Dispose()
    } finally {$contrast.Dispose()}
}
function Read-OcrBitmap($Decoder) {
    $maxDimension = [Windows.Media.Ocr.OcrEngine, Windows, ContentType=WindowsRuntime]::MaxImageDimension
    $scale = [Math]::Min(2.0, $maxDimension / [Math]::Max($Decoder.PixelWidth, $Decoder.PixelHeight))
    $transform = [Windows.Graphics.Imaging.BitmapTransform, Windows, ContentType=WindowsRuntime]::new()
    $transform.ScaledWidth = [uint32]($Decoder.PixelWidth * $scale)
    $transform.ScaledHeight = [uint32]($Decoder.PixelHeight * $scale)
    Wait-WinRT ($Decoder.GetSoftwareBitmapAsync(
        [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
        [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied,
        $transform,
        [Windows.Graphics.Imaging.ExifOrientationMode]::IgnoreExifOrientation,
        [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage
    )) ([Windows.Graphics.Imaging.SoftwareBitmap, Windows, ContentType=WindowsRuntime])
}
$makeLines = {
    param($Result)
    @($Result.Lines | ForEach-Object {
        $rects = @($_.Words | ForEach-Object { $_.BoundingRect })
        if ($rects.Count) {
            $left = ($rects | Measure-Object X -Minimum).Minimum
            $top = ($rects | Measure-Object Y -Minimum).Minimum
            $right = ($rects | ForEach-Object { $_.X + $_.Width } | Measure-Object -Maximum).Maximum
            $bottom = ($rects | ForEach-Object { $_.Y + $_.Height } | Measure-Object -Maximum).Maximum
            @{ text=$_.Text; x=[double]$left; y=[double]$top; width=[double]($right - $left); height=[double]($bottom - $top) }
        } else {
            @{ text=$_.Text; x=0.0; y=0.0; width=0.0; height=0.0 }
        }
    })
}
if ($language) {
    $engine = [Windows.Media.Ocr.OcrEngine, Windows, ContentType=WindowsRuntime]::TryCreateFromLanguage($language)
    foreach ($path in $Paths) {
        $path = [IO.Path]::GetFullPath($path)
        $extension = [IO.Path]::GetExtension($path).ToLowerInvariant()
        $inputStream = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows, ContentType=WindowsRuntime]::new()
        $writer = [Windows.Storage.Streams.DataWriter, Windows, ContentType=WindowsRuntime]::new($inputStream)
        $writer.WriteBytes([IO.File]::ReadAllBytes($path))
        Wait-WinRT ($writer.StoreAsync()) ([uint32]) | Out-Null
        $null = $writer.DetachStream(); $writer.Dispose(); $inputStream.Seek(0) | Out-Null
        if ($extension -eq '.pdf') {
            $doc = Wait-WinRT ([Windows.Data.Pdf.PdfDocument, Windows, ContentType=WindowsRuntime]::LoadFromStreamAsync($inputStream)) ([Windows.Data.Pdf.PdfDocument, Windows, ContentType=WindowsRuntime])
            for ($i = 0; $i -lt $doc.PageCount; $i++) {
                $page = $doc.GetPage([uint32]$i)
                $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows, ContentType=WindowsRuntime]::new()
                $renderOptions=[Windows.Data.Pdf.PdfPageRenderOptions, Windows, ContentType=WindowsRuntime]::new()
                $renderScale=[Math]::Min(3.0,2048.0/[Math]::Max($page.Size.Width,$page.Size.Height))
                $renderOptions.DestinationWidth=[uint32]($page.Size.Width*$renderScale)
                $renderOptions.DestinationHeight=[uint32]($page.Size.Height*$renderScale)
                Wait-WinRT ($page.RenderToStreamAsync($stream,$renderOptions)) ([Windows.Foundation.IAsyncAction, Windows, ContentType=WindowsRuntime]) | Out-Null
                $stream.Seek(0) | Out-Null
                $decoder = Wait-WinRT ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime])
                $bitmap = Read-OcrBitmap $decoder
                $ocr = Wait-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult, Windows, ContentType=WindowsRuntime])
                $pagesOut.Add(@{ file=$path; page=$i + 1; width=[double]$bitmap.PixelWidth; height=[double]$bitmap.PixelHeight; lines=& $makeLines $ocr; contrast_lines=@(Read-ContrastLines $stream) })
                $page.Dispose(); $stream.Dispose(); $bitmap.Dispose()
            }
        } else {
            $decoder = Wait-WinRT ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime]::CreateAsync($inputStream)) ([Windows.Graphics.Imaging.BitmapDecoder, Windows, ContentType=WindowsRuntime])
            $bitmap = Read-OcrBitmap $decoder
            $ocr = Wait-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult, Windows, ContentType=WindowsRuntime])
            $pagesOut.Add(@{ file=$path; page=1; width=[double]$bitmap.PixelWidth; height=[double]$bitmap.PixelHeight; lines=& $makeLines $ocr; contrast_lines=@(Read-ContrastLines $inputStream) })
            $bitmap.Dispose()
        }
        $inputStream.Dispose()
    }
} else {throw 'Windows 中文 OCR language 未安装。'}
@{ language=if ($language) { $language.LanguageTag } else { $null }; pages=@($pagesOut) } | ConvertTo-Json -Depth 8 -Compress

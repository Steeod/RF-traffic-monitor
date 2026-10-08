$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$output = Join-Path $projectRoot 'app\vendor\adsb\rtl-probe.exe'
& $compiler /nologo /target:exe /platform:x86 /optimize+ /r:System.Web.Extensions.dll "/out:$output" (Join-Path $PSScriptRoot 'RtlProbe.cs')
if ($LASTEXITCODE -ne 0) { throw 'RTL probe compilation failed.' }

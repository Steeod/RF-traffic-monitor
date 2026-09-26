$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
$appDir = if (Test-Path (Join-Path $projectDir 'app\VrsBridge.cs')) { Join-Path $projectDir 'app' } else { $projectDir }
$vrsDir = Join-Path $appDir 'vendor\vrs'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
& $compiler /nologo /target:exe /platform:x86 "/out:$vrsDir\VrsBridge.exe" "/r:$vrsDir\InterfaceFactory.dll" "/r:$vrsDir\VirtualRadar.Interface.dll" "/r:$vrsDir\VirtualRadar.Library.dll" "/r:$vrsDir\Newtonsoft.Json.dll" (Join-Path $appDir 'VrsBridge.cs')
if ($LASTEXITCODE -ne 0) { throw 'VRS bridge compilation failed' }

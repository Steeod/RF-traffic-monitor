$ErrorActionPreference='Stop'
$radarRoot=Split-Path $PSScriptRoot -Parent
$appRoot=if(Test-Path (Join-Path $radarRoot 'app\native\Cargo.toml')){Join-Path $radarRoot 'app'}else{$radarRoot}
$nativeSource=if(Test-Path (Join-Path $appRoot 'native\Cargo.toml')){Join-Path $appRoot 'native'}else{Join-Path $radarRoot 'sources\native'}
$output=Join-Path $appRoot 'vendor\native'
New-Item -ItemType Directory -Force $output | Out-Null
Copy-Item (Join-Path $nativeSource 'target\release\radar-decode.exe') $output
if(Test-Path (Join-Path $radarRoot 'downloads\rtl-v4\x64')){Copy-Item (Join-Path $radarRoot 'downloads\rtl-v4\x64\*.dll') $output}
$vsCandidates=@(
  'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
  'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat',
  'C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat',
  'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat'
)
$vs=$vsCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if(-not $vs){throw 'Visual Studio 2022 C++ Build Tools were not found.'}
$core=Join-Path $radarRoot '.build\opendroneid-core-c-master\libopendroneid'
$wrapper=Join-Path $nativeSource 'rid_decode.c'
$compat=Join-Path $nativeSource 'odid_compat.h'
Push-Location (Join-Path $radarRoot '.build')
try { & cmd.exe /c "`"$vs`" >nul && cl /nologo /LD /O2 /MT /FI`"$compat`" /I`"$core`" `"$wrapper`" `"$core\opendroneid.c`" /link /OUT:`"$output\rid_decode.dll`""; if($LASTEXITCODE -ne 0){throw 'OpenDroneID build failed'} } finally { Pop-Location }

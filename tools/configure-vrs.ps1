$ErrorActionPreference = 'Stop'
if ([Environment]::Is64BitProcess) {
  $powershell32 = Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
  if (-not (Test-Path -LiteralPath $powershell32)) { throw '32-bit Windows PowerShell is required to configure the x86 VRS libraries.' }
  & $powershell32 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
  exit $LASTEXITCODE
}
$projectDir = Split-Path $PSScriptRoot -Parent
$vrsDir = Join-Path $projectDir 'app\vendor\vrs'
$dataDir = Join-Path $projectDir 'app\data\vrs'
New-Item -ItemType Directory -Force $dataDir | Out-Null
[void][Reflection.Assembly]::LoadFrom((Join-Path $vrsDir 'InterfaceFactory.dll'))
[void][Reflection.Assembly]::LoadFrom((Join-Path $vrsDir 'VirtualRadar.Interface.dll'))
[void][Reflection.Assembly]::LoadFrom((Join-Path $vrsDir 'VirtualRadar.Library.dll'))
[VirtualRadar.Library.Implementations]::Register([InterfaceFactory.Factory]::Singleton)
$settings = New-Object VirtualRadar.Interface.Settings.Configuration
$settings.VersionCheckSettings.CheckAutomatically = $false
$settings.BaseStationSettings.LookupAircraftDetailsOnline = $false
$settings.BaseStationSettings.DownloadGlobalAirPressureReadings = $false
$settings.FlightRouteSettings.AutoUpdateEnabled = $false
$settings.WebServerSettings.EnableUPnp = $false
$settings.WebServerSettings.AutoStartUPnP = $false
$receiver = New-Object VirtualRadar.Interface.Settings.Receiver
$receiver.UniqueId = 1
$receiver.Name = 'RF Traffic Monitor RTL-SDR'
$receiver.Address = '127.0.0.1'
$receiver.Port = 30003
$settings.Receivers.Add($receiver)
$settings.GoogleMapSettings.ClosestAircraftReceiverId = 1
$settings.GoogleMapSettings.WebSiteReceiverId = 1
$serializer = New-Object System.Xml.Serialization.XmlSerializer($settings.GetType())
$writer = [IO.StreamWriter]::new((Join-Path $dataDir 'Configuration.xml'))
try { $serializer.Serialize($writer, $settings) } finally { $writer.Dispose() }

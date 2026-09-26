param([ValidateSet('Host','Bind')][string]$Stage,[string]$BusId='')
$ErrorActionPreference='Stop'
if ($Stage -eq 'Host') {
  $installer=Join-Path $PSScriptRoot '..\vendor\wsl-bundle\usbipd-win_5.3.0_x64.msi'
  if (-not (Test-Path -LiteralPath $installer)) { throw 'The bundled usbipd-win installer is missing.' }
  $p=Start-Process msiexec.exe -ArgumentList @('/i',('"'+(Resolve-Path $installer).Path+'"')) -Wait -PassThru
  if ($p.ExitCode -ne 0) { throw "The usbipd-win installer returned $($p.ExitCode)." }
  Write-Host 'Bundled usbipd-win 5.3.0 was installed. Microsoft WSL was not modified.'
} elseif ($Stage -eq 'Bind') {
  if ($BusId -notmatch '^\d+-\d+$') { throw 'Invalid USB BUSID.' }
  usbipd.exe bind --busid $BusId
  Write-Host 'The device is now shared with WSL2.'
}
Read-Host 'Press Enter to close'

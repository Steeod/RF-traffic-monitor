[CmdletBinding()]
param(
    [string]$Location,
    [Nullable[double]]$Latitude,
    [Nullable[double]]$Longitude,
    [string]$StationName,
    [ValidateRange(50,500)][int]$RadiusKm = 200,
    [ValidateSet('Ask','RTL','HackRF','WiFi')][string]$Receiver = 'Ask',
    [ValidateSet('Ask','None','Windows','WSL')][string]$WifiSupport = 'Ask',
    [ValidateSet('Ask','None','AWUS036H','AWUS036ACS','Other')][string]$WifiAdapter = 'Ask',
    [switch]$SkipToolchainInstall,
    [switch]$SkipSatellite,
    [switch]$SkipPackage
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

function Write-Step([string]$Text) {
    Write-Host "`n==> $Text" -ForegroundColor Cyan
}

function Invoke-External([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}

function Find-Python {
    $commands = @(
        @{ Program = 'py.exe'; Args = @('-3.12') },
        @{ Program = 'py.exe'; Args = @('-3') },
        @{ Program = 'python.exe'; Args = @() }
    )
    foreach ($candidate in $commands) {
        if (Get-Command $candidate.Program -ErrorAction SilentlyContinue) {
            $probeArguments = @($candidate.Args) + @('-c','import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)')
            & $candidate.Program @probeArguments 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

function Install-WingetPackage([string]$Id, [string[]]$Extra = @()) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "winget is required to install $Id automatically. Install App Installer or use -SkipToolchainInstall after installing it manually."
    }
    $arguments = @('install','--id',$Id,'--exact','--accept-package-agreements','--accept-source-agreements','--silent') + $Extra
    Invoke-External 'winget.exe' $arguments
}

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'RF Traffic Monitor setup requires 64-bit Windows 10 or 11.'
}

Write-Host 'RF Traffic Monitor - guided Windows setup' -ForegroundColor Green
Write-Host 'Downloads are verified with SHA-256 before they are used.'

if ($null -eq $Latitude -or $null -eq $Longitude) {
    if (-not $Location) { $Location = Read-Host 'Receiver city or area (for example Athens, Greece)' }
    if ($Location) {
        Write-Step "Looking up location: $Location"
        $encoded = [Uri]::EscapeDataString($Location)
        $headers = @{ 'User-Agent' = 'RFTrafficMonitor/0.10 setup' }
        try {
            $results = @(Invoke-RestMethod -Uri "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&accept-language=en&q=$encoded" -Headers $headers)
        } catch {
            Write-Warning "Location lookup failed: $($_.Exception.Message). Coordinates will be requested."
            $results = @()
        }
        if ($results.Count -gt 0) {
            for ($index=0; $index -lt $results.Count; $index++) {
                Write-Host "[$($index+1)] $($results[$index].display_name)"
            }
            $choice = Read-Host 'Select a number [1]'
            if (-not $choice) { $choice = '1' }
            $selected = $results[[int]$choice - 1]
            $Latitude = [double]::Parse($selected.lat,[Globalization.CultureInfo]::InvariantCulture)
            $Longitude = [double]::Parse($selected.lon,[Globalization.CultureInfo]::InvariantCulture)
            if (-not $StationName) { $StationName = $Location }
        }
    }
}
if ($null -eq $Latitude) { $Latitude = [double]::Parse((Read-Host 'Latitude (-85 to 85)'),[Globalization.CultureInfo]::InvariantCulture) }
if ($null -eq $Longitude) { $Longitude = [double]::Parse((Read-Host 'Longitude (-180 to 180)'),[Globalization.CultureInfo]::InvariantCulture) }
if ($Latitude -lt -85 -or $Latitude -gt 85 -or $Longitude -lt -180 -or $Longitude -gt 180) {
    throw 'Invalid receiver coordinates.'
}
if (-not $StationName) { $StationName = Read-Host 'Receiver station name' }
if (-not $StationName) { $StationName = 'My receiving station' }

if ($Receiver -eq 'Ask') {
    Write-Host "`nReceiver: [1] RTL-SDR, [2] HackRF One, [3] Wi-Fi Remote ID only"
    $receiverChoice = Read-Host 'Selection [1]'
    $Receiver = switch ($receiverChoice) { '2' {'HackRF'} '3' {'WiFi'} default {'RTL'} }
}

if ($WifiSupport -eq 'Ask') {
    Write-Host "`nWi-Fi Remote ID: [1] no, [2] Windows WLAN/Npcap, [3] WSL2 monitor mode"
    $wifiChoice = Read-Host 'Selection [1]'
    $WifiSupport = switch ($wifiChoice) { '2' {'Windows'} '3' {'WSL'} default {'None'} }
}
if ($WifiSupport -ne 'None' -and $WifiAdapter -eq 'Ask') {
    Write-Host 'Wi-Fi adapter: [1] AWUS036H, [2] AWUS036ACS, [3] another model'
    $adapterChoice = Read-Host 'Selection [3]'
    $WifiAdapter = switch ($adapterChoice) { '1' {'AWUS036H'} '2' {'AWUS036ACS'} default {'Other'} }
}
if ($WifiSupport -eq 'None') { $WifiAdapter = 'None' }
if ($Receiver -eq 'WiFi' -and $WifiSupport -eq 'None') {
    throw 'Wi-Fi-only mode requires Windows or WSL Wi-Fi support.'
}

$python = Find-Python
if (-not $python) {
    if ($SkipToolchainInstall) { throw 'Python 3.11+ is required.' }
    Write-Step 'Installing Python 3.12'
    Install-WingetPackage 'Python.Python.3.12'
    $python = Find-Python
    if (-not $python) {
        $installedPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
        if (Test-Path -LiteralPath $installedPython) { $python = @{ Program=$installedPython; Args=@() } }
    }
    if (-not $python) { throw 'Python installed but was not found. Open a new PowerShell window and rerun setup.ps1 with the same location.' }
}
function Invoke-Python([string[]]$Arguments) {
    Invoke-External $python.Program (@($python.Args) + $Arguments)
}

Write-Step 'Downloading and verifying runtimes, decoders, libraries, sources and drivers'
Invoke-Python @((Join-Path $projectRoot 'tools\bootstrap.py'),'dependencies')
Invoke-Python @((Join-Path $projectRoot 'tools\bootstrap.py'),'materialize')
Invoke-Python @((Join-Path $projectRoot 'tools\bootstrap.py'),'configure','--station-name',$StationName,
                '--latitude',$Latitude.ToString([Globalization.CultureInfo]::InvariantCulture),
                '--longitude',$Longitude.ToString([Globalization.CultureInfo]::InvariantCulture),
                '--receiver-type',$Receiver.ToLowerInvariant(),
                '--wifi-support',$WifiSupport.ToLowerInvariant(),
                '--wifi-adapter',$WifiAdapter.ToLowerInvariant())

if ($WifiSupport -eq 'Windows' -and $WifiAdapter -in @('AWUS036H','AWUS036ACS')) {
    $driverFolder = if ($WifiAdapter -eq 'AWUS036H') {'awus036h'} else {'awus036acs'}
    $driverInf = if ($WifiAdapter -eq 'AWUS036H') {'Netrtuw.inf'} else {'netrtwlanu.inf'}
    $infPath = Join-Path $projectRoot "app\vendor\drivers\alfa\$driverFolder\$driverInf"
    Write-Step "Installing the signed Windows driver for $WifiAdapter (UAC)"
    $driverProcess = Start-Process 'pnputil.exe' -Verb RunAs -Wait -PassThru -ArgumentList @('/add-driver',('"'+$infPath+'"'),'/install')
    if ($driverProcess.ExitCode -ne 0) { throw "pnputil returned $($driverProcess.ExitCode) for $WifiAdapter" }
}

Write-Step 'Building local land and place-name maps'
$latText = $Latitude.ToString([Globalization.CultureInfo]::InvariantCulture)
$lonText = $Longitude.ToString([Globalization.CultureInfo]::InvariantCulture)
Invoke-Python @((Join-Path $projectRoot 'tools\prepare-map.py'),$latText,$lonText,'--radius-km',$RadiusKm.ToString())
Invoke-Python @((Join-Path $projectRoot 'tools\prepare-places.py'),$latText,$lonText,'--radius-km',$RadiusKm.ToString())

if (-not $SkipSatellite) {
    Write-Step 'Installing Pillow and downloading the EOX offline satellite map'
    $mapPackages = Join-Path $projectRoot '.build\map-python'
    if (-not (Test-Path -LiteralPath (Join-Path $mapPackages 'PIL\__init__.py'))) {
        New-Item -ItemType Directory -Force -Path $mapPackages | Out-Null
        Invoke-Python @('-m','pip','install','--target',$mapPackages,'Pillow==11.3.0')
    }
    $env:PYTHONPATH = $mapPackages
    $runtimePillow = Join-Path $projectRoot 'app\runtime\PIL'
    if (Test-Path -LiteralPath $runtimePillow) { Remove-Item -LiteralPath $runtimePillow -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $mapPackages 'PIL') -Destination $runtimePillow -Recurse
    Invoke-Python @((Join-Path $projectRoot 'app\map_downloader.py'),$latText,$lonText,$RadiusKm.ToString())
}

if (-not (Get-Command cargo.exe -ErrorAction SilentlyContinue) -and -not (Test-Path "$env:USERPROFILE\.cargo\bin\cargo.exe")) {
    if ($SkipToolchainInstall) { throw 'Rust/cargo is required for the xng decoder build.' }
    Write-Step 'Installing the Rust toolchain'
    Install-WingetPackage 'Rustlang.Rustup'
}
$cargo = (Get-Command cargo.exe -ErrorAction SilentlyContinue).Source
if (-not $cargo) { $cargo = "$env:USERPROFILE\.cargo\bin\cargo.exe" }

$vcvars = @(
    'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat'
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $vcvars) {
    if ($SkipToolchainInstall) { throw 'Visual Studio 2022 C++ Build Tools are required.' }
    Write-Step 'Installing Visual Studio 2022 C++ Build Tools'
    Install-WingetPackage 'Microsoft.VisualStudio.2022.BuildTools' @('--override','--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
}

Write-Step 'Building the native xng and OpenDroneID decoders'
$env:CARGO_HOME = Join-Path $projectRoot '.build\cargo'
Invoke-External $cargo @('build','--release','--locked','--manifest-path',(Join-Path $projectRoot 'app\native\Cargo.toml'))
Invoke-External 'powershell.exe' @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $projectRoot 'tools\build-extra.ps1'))
Invoke-Python @((Join-Path $projectRoot 'tools\collect-native-licenses.py'))

Write-Step 'Building and configuring the offline Virtual Radar bridge'
Invoke-External 'powershell.exe' @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $projectRoot 'tools\build-bridge.ps1'))
Invoke-External 'powershell.exe' @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $projectRoot 'tools\configure-vrs.ps1'))

if ($WifiSupport -eq 'WSL') {
    Write-Step 'Downloading the WSL2, usbipd and driver source bundle'
    Invoke-Python @((Join-Path $projectRoot 'tools\download-wsl-bundle.py'))
    $bundleTarget = Join-Path $projectRoot 'app\vendor\wsl-bundle'
    New-Item -ItemType Directory -Force -Path $bundleTarget | Out-Null
    Copy-Item -Path (Join-Path $projectRoot 'downloads\wsl-bundle\*') -Destination $bundleTarget -Force
    $usbipdInstaller = Join-Path $bundleTarget 'usbipd-win_5.3.0_x64.msi'
    Write-Step 'Installing usbipd-win (UAC)'
    $usbipdProcess = Start-Process 'msiexec.exe' -Verb RunAs -Wait -PassThru -ArgumentList @('/i',('"'+$usbipdInstaller+'"'),'/passive','/norestart')
    if ($usbipdProcess.ExitCode -notin @(0,3010)) { throw "usbipd installer returned $($usbipdProcess.ExitCode)" }
    $wslReady = $false
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        & wsl.exe --status *> $null
        $wslReady = $LASTEXITCODE -eq 0
    }
    if (-not $wslReady) {
        Write-Host 'WSL2 is not installed. Run as administrator: wsl --install -d Ubuntu-22.04, restart, and rerun setup.ps1 with the same parameters.' -ForegroundColor Yellow
    } else {
        Write-Host 'Use the WSL guide in the application for USB binding and the device-specific Linux driver build.' -ForegroundColor Yellow
    }
}

Write-Step 'Testing the application'
Invoke-Python @('-m','unittest','discover','-s',(Join-Path $projectRoot 'tests'),'-v')

if (-not $SkipPackage) {
    Write-Step 'Creating the portable package'
    Invoke-Python @((Join-Path $projectRoot 'tools\package.py'))
}

Write-Host "`nRF Traffic Monitor is ready." -ForegroundColor Green
Write-Host "Station: $StationName ($latText, $lonText)"
Write-Host "Portable folder: $(Join-Path $projectRoot 'dist\RFTrafficMonitor')"
if (-not $SkipPackage) { Write-Host "ZIP: $(Join-Path $projectRoot 'dist\RFTrafficMonitor-0.10-win64.zip')" }
Write-Host 'For RTL-SDR/HackRF, open the application and select Install WinUSB. Verify the exact USB device visually in Zadig before installing.' -ForegroundColor Yellow
if ($WifiSupport -eq 'Windows') { Write-Host 'For raw Wi-Fi capture, install Npcap separately from its official site. Basic Windows WLAN scanning does not require it.' }

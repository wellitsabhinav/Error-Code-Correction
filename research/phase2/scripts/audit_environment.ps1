$ErrorActionPreference = 'Continue'
$PhaseRoot = Split-Path -Parent $PSScriptRoot
$OutRoot = Join-Path $PhaseRoot 'raw/environment'
New-Item -ItemType Directory -Path $OutRoot -Force | Out-Null
$drives = Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root, Used, Free
$volumes = @()
$volumeError = $null
try { $volumes = Get-Volume -ErrorAction Stop | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size, SizeRemaining }
catch { $volumeError = $_.Exception.Message }
$tools = Get-Command git, python, iverilog, vvp, yosys, sta, openroad, docker, make, g++ -ErrorAction SilentlyContinue | Select-Object Name, Source
$distros = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\*' -ErrorAction SilentlyContinue | Select-Object DistributionName, BasePath
$paths = @(
    'C:\Users\Abhinav\OneDrive\Desktop\ECC\Error-Code-Correction',
    'D:\GREENS_ARCHIVES',
    'G:\ECC Continued',
    'F:\green-ecc-iscas-sustainability-temp\wsl-relocated\Ubuntu-24.04\ext4.vhdx',
    'F:\AgenticAI\.local\wsl\ext4.vhdx',
    'F:\AgenticAI\.local\m9-icarus-linux\iverilog_12.0-2build2_amd64.deb'
)
$items = foreach ($p in $paths) {
    $item = Get-Item -LiteralPath $p -ErrorAction SilentlyContinue
    [PSCustomObject]@{ path = $p; exists = ($null -ne $item); length_bytes = if ($item -and !$item.PSIsContainer) { $item.Length } else { $null } }
}
$data = [ordered]@{ utc = [DateTime]::UtcNow.ToString('o'); drives = @($drives); volumes = @($volumes); volume_error = $volumeError; native_tools = @($tools); wsl_registrations = @($distros); locations = @($items) }
$data | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutRoot 'windows_inventory.json') -Encoding utf8
wsl --list --verbose 2>&1 | Out-File -LiteralPath (Join-Path $OutRoot 'wsl_list.txt') -Encoding utf8
$data | ConvertTo-Json -Depth 6

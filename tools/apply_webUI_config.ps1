param(
    [string]$WebUIConfigDir = "config_webUI",
    [string]$EnvPath = ".env",
    [switch]$RunApplyAgent
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "File not found: $Path"
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-Timestamp {
    return Get-Date -Format "yyyyMMdd-HHmmss"
}

function ConvertTo-Hashtable {
    param($Object)
    $table = @{}
    if ($null -eq $Object) {
        return $table
    }
    foreach ($property in $Object.PSObject.Properties) {
        $table[$property.Name] = [string]$property.Value
    }
    return $table
}

function Upsert-DotenvValues {
    param(
        [string]$Path,
        [hashtable]$Updates
    )
    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    }
    $seen = @{}
    $output = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $line.Contains("=")) {
            $output.Add($line)
            continue
        }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        if ($Updates.ContainsKey($key)) {
            $output.Add("$key=$($Updates[$key])")
            $seen[$key] = $true
        } else {
            $output.Add($line)
        }
    }
    $missing = @($Updates.Keys | Where-Object { -not $seen.ContainsKey($_) } | Sort-Object)
    if ($missing.Count -gt 0 -and $output.Count -gt 0 -and $output[$output.Count - 1].Trim()) {
        $output.Add("")
    }
    foreach ($key in $missing) {
        $output.Add("$key=$($Updates[$key])")
    }
    Set-Content -LiteralPath $Path -Value $output -Encoding UTF8
}

$repoRoot = Get-RepoRoot
Set-Location -LiteralPath $repoRoot

$configRoot = Resolve-Path -LiteralPath $WebUIConfigDir -ErrorAction Stop
$currentPath = Join-Path $configRoot "current.json"
$current = Read-JsonFile $currentPath

$snapshotRelative = [string]$current.active_snapshot
if (-not $snapshotRelative) {
    throw "config_webUI/current.json does not contain active_snapshot."
}
$snapshotPath = Join-Path $configRoot $snapshotRelative
$snapshot = Read-JsonFile $snapshotPath
$updates = ConvertTo-Hashtable $snapshot.owned_fields
if ($updates.Count -eq 0) {
    throw "The active WebUI snapshot has no owned_fields."
}

$backupDir = Join-Path $configRoot "backup"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$timestamp = Get-Timestamp

if (Test-Path -LiteralPath $EnvPath) {
    Copy-Item -LiteralPath $EnvPath -Destination (Join-Path $backupDir ".env.$timestamp.bak") -Force
} else {
    Copy-Item -LiteralPath ".env.example" -Destination $EnvPath -Force
}

Upsert-DotenvValues $EnvPath $updates

Move-Item -LiteralPath $currentPath -Destination (Join-Path $backupDir "current.$timestamp.json") -Force

if ($RunApplyAgent -or $updates.ContainsKey("ENABLED_AGENTS")) {
    & (Join-Path $PSScriptRoot "apply_agent.ps1") -EnvPath $EnvPath -AgentConfigDir "config/agent" -AgentEnvDir "."
}

Write-Host "Applied $($updates.Count) WebUI-owned values to $EnvPath."
Write-Host "Archived WebUI current.json under $backupDir."
Write-Host "Restart the Docker service if module switches or provider settings changed."

param(
    [string]$EnvPath = ".env",
    [string]$AgentConfigDir = "config/agent",
    [string]$AgentEnvDir = "."
)

$ErrorActionPreference = "Stop"

$ManagedMarker = "# Managed by tools/apply_agent.ps1"
$MatrixTools = @("matrix_send_text", "matrix_send_image", "matrix_send_audio")

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Read-DotenvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Dotenv file not found: $Path"
    }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        if ($parts[0].Trim() -eq $Key) {
            return (Unquote-EnvValue $parts[1].Trim())
        }
    }
    return ""
}

function Unquote-EnvValue {
    param([string]$Value)
    if ($Value.Length -ge 2) {
        $first = $Value.Substring(0, 1)
        $last = $Value.Substring($Value.Length - 1, 1)
        if (($first -eq "'" -and $last -eq "'") -or ($first -eq '"' -and $last -eq '"')) {
            return $Value.Substring(1, $Value.Length - 2)
        }
    }
    return $Value
}

function Get-EnabledAgents {
    param([string]$RawValue)
    $agents = [System.Collections.Generic.List[string]]::new()
    $seen = @{}
    foreach ($item in ($RawValue -split "[,;]")) {
        $name = $item.Trim()
        if (-not $name) {
            continue
        }
        if ($name -notmatch "^[A-Za-z0-9_-]+$") {
            throw "Invalid agent name '$name'. Use only letters, numbers, underscores, and hyphens."
        }
        if (-not $seen.ContainsKey($name)) {
            $agents.Add($name)
            $seen[$name] = $true
        }
    }
    return $agents
}

function Get-AgentEnvName {
    param(
        [string]$AgentName,
        [string]$Prefix,
        [string]$Suffix
    )
    $normalized = ($AgentName.ToCharArray() | ForEach-Object {
        if ([char]::IsLetterOrDigit($_)) { [string]$_ } else { "_" }
    }) -join ""
    return "$Prefix$($normalized.ToUpperInvariant())$Suffix"
}

function New-Token {
    $bytes = [byte[]]::new(32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Ensure-AgentConfig {
    param(
        [string]$AgentName,
        [string]$Path
    )
    if (Test-Path -LiteralPath $Path) {
        return $false
    }
    $gatewayTokenEnv = Get-AgentEnvName $AgentName "GATEWAY_TOKEN_" ""
    $matrixTokenEnv = Get-AgentEnvName $AgentName "" "_MATRIX_ACCESS_TOKEN"
    $toolsYaml = ($MatrixTools | ForEach-Object { "  - $_" }) -join "`n"
    $content = @"
$ManagedMarker
caller:
  role: role_play
  token_env: $gatewayTokenEnv
  shared_artifact_read: false

matrix:
  enabled: true
  account: $AgentName
  homeserver_env: MATRIX_HOMESERVER
  access_token_env: $matrixTokenEnv

high_risk_tools:
$toolsYaml
"@
    Set-Content -LiteralPath $Path -Value $content -Encoding UTF8
    return $true
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
    $missing = @($Updates.Keys | Where-Object { -not $seen.ContainsKey($_) })
    if ($missing.Count -gt 0 -and $output.Count -gt 0 -and $output[$output.Count - 1].Trim()) {
        $output.Add("")
    }
    foreach ($key in $missing) {
        $output.Add("$key=$($Updates[$key])")
    }
    Set-Content -LiteralPath $Path -Value $output -Encoding UTF8
}

function Ensure-AgentEnv {
    param(
        [string]$AgentName,
        [string]$Path,
        [string]$RootEnvPath
    )
    $created = -not (Test-Path -LiteralPath $Path)
    if ($created) {
        Set-Content -LiteralPath $Path -Value $ManagedMarker -Encoding UTF8
    }
    $gatewayTokenEnv = Get-AgentEnvName $AgentName "GATEWAY_TOKEN_" ""
    $matrixTokenEnv = Get-AgentEnvName $AgentName "" "_MATRIX_ACCESS_TOKEN"
    $existingGatewayToken = Read-DotenvValue $RootEnvPath $gatewayTokenEnv
    $existingMatrixToken = Read-DotenvValue $RootEnvPath $matrixTokenEnv
    if (-not $existingGatewayToken) {
        $existingGatewayToken = New-Token
    }
    $updates = @{
        $gatewayTokenEnv = $existingGatewayToken
        $matrixTokenEnv = $existingMatrixToken
    }
    if (Test-Path -LiteralPath $Path) {
        $existing = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        if ($existing -match "(?m)^\s*$([regex]::Escape($gatewayTokenEnv))\s*=") {
            $updates.Remove($gatewayTokenEnv)
        }
        if ($existing -match "(?m)^\s*$([regex]::Escape($matrixTokenEnv))\s*=") {
            $updates.Remove($matrixTokenEnv)
        }
    }
    if ($updates.Count -gt 0) {
        Upsert-DotenvValues $Path $updates
    }
    return $created
}

function Remove-ManagedFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $firstLine = (Get-Content -LiteralPath $Path -TotalCount 1 -Encoding UTF8)
    if ($firstLine -eq $ManagedMarker) {
        Remove-Item -LiteralPath $Path
        return $true
    }
    Write-Warning "Skipped unmanaged file: $Path"
    return $false
}

$repoRoot = Get-RepoRoot
Set-Location -LiteralPath $repoRoot

$enabledRaw = Read-DotenvValue $EnvPath "ENABLED_AGENTS"
$enabledAgents = Get-EnabledAgents $enabledRaw
$enabledSet = @{}
foreach ($agent in $enabledAgents) {
    $enabledSet[$agent] = $true
}

New-Item -ItemType Directory -Force -Path $AgentConfigDir | Out-Null
New-Item -ItemType Directory -Force -Path $AgentEnvDir | Out-Null

foreach ($agent in $enabledAgents) {
    $configPath = Join-Path $AgentConfigDir "config.agent.$agent.yaml"
    $envFilePath = Join-Path $AgentEnvDir ".env.agent.$agent"
    $createdConfig = Ensure-AgentConfig $agent $configPath
    $createdEnv = Ensure-AgentEnv $agent $envFilePath $EnvPath
    if ($createdConfig -or $createdEnv) {
        Write-Host "Applied agent '$agent' (created missing files)."
    } else {
        Write-Host "Applied agent '$agent'."
    }
}

Get-ChildItem -LiteralPath $AgentConfigDir -Filter "config.agent.*.yaml" -File | ForEach-Object {
    $name = $_.Name.Substring("config.agent.".Length)
    $name = $name.Substring(0, $name.Length - ".yaml".Length)
    if (-not $enabledSet.ContainsKey($name)) {
        if (Remove-ManagedFile $_.FullName) {
            Write-Host "Removed disabled agent config '$name'."
        }
    }
}

Get-ChildItem -LiteralPath $AgentEnvDir -Filter ".env.agent.*" -File | ForEach-Object {
    $name = $_.Name.Substring(".env.agent.".Length)
    if (-not $enabledSet.ContainsKey($name)) {
        if (Remove-ManagedFile $_.FullName) {
            Write-Host "Removed disabled agent env '$name'."
        }
    }
}

Write-Host "Enabled agents: $($enabledAgents -join ', ')"

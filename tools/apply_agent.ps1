param(
    [string]$ConfigPath = "config/config.yaml",
    [string]$AgentConfigDir = "config/agent"
)

$ErrorActionPreference = "Stop"

$ManagedMarker = "# Managed by tools/apply_agent.ps1"
$MatrixTools = @("matrix_send_text", "matrix_send_image", "matrix_send_audio")

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Read-TextFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8
}

function Get-EnabledAgents {
    param([string]$ConfigText)
    $agents = [System.Collections.Generic.List[string]]::new()
    $inAgents = $false
    $inEnabled = $false
    $enabledIndent = -1
    $inline = [regex]::Match($ConfigText, "(?m)^agents:\s*(?:\r?\n(?:[ ]{2,}.*\r?\n?)*)")
    if ($inline.Success) {
        $block = $inline.Value
        $enabledLine = [regex]::Match($block, "(?m)^[ ]{2}enabled:\s*(.*)$")
        if ($enabledLine.Success) {
            $raw = $enabledLine.Groups[1].Value.Trim()
            if ($raw.StartsWith("[") -and $raw.EndsWith("]")) {
                foreach ($item in $raw.Trim("[]").Split(",")) {
                    Add-AgentName $agents $item.Trim().Trim("'").Trim('"')
                }
                return $agents
            }
        }
    }
    foreach ($line in $ConfigText -split "\r?\n") {
        if ($line -match "^\S") {
            $inAgents = $line -match "^agents:\s*$"
            $inEnabled = $false
            continue
        }
        if (-not $inAgents) {
            continue
        }
        if ($line -match "^(\s*)enabled:\s*$") {
            $inEnabled = $true
            $enabledIndent = $Matches[1].Length
            continue
        }
        if ($inEnabled -and $line -match "^(\s*)-\s*(.+?)\s*$") {
            if ($Matches[1].Length -le $enabledIndent) {
                $inEnabled = $false
                continue
            }
            Add-AgentName $agents $Matches[2].Trim().Trim("'").Trim('"')
        } elseif ($line -match "^\s{2}\S") {
            $inEnabled = $false
        }
    }
    return $agents
}

function Add-AgentName {
    param(
        [System.Collections.Generic.List[string]]$Agents,
        [string]$Name
    )
    if (-not $Name) {
        return
    }
    if ($Name -notmatch "^[A-Za-z0-9_-]+$") {
        throw "Invalid agent name '$Name'. Use only letters, numbers, underscores, and hyphens."
    }
    if (-not $Agents.Contains($Name)) {
        $Agents.Add($Name)
    }
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
    $toolsYaml = ($MatrixTools | ForEach-Object { "  - $_" }) -join "`n"
    $gatewayToken = New-Token
    $content = @"
$ManagedMarker
caller:
  role: role_play
  token: $gatewayToken
  shared_artifact_read: false

matrix:
  enabled: true
  account: $AgentName
  access_token: ""

high_risk_tools:
$toolsYaml
"@
    Set-Content -LiteralPath $Path -Value $content -Encoding UTF8
    return $true
}

function Remove-ManagedFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $firstLine = (Get-Content -LiteralPath $Path -TotalCount 1 -Encoding UTF8)
    if ($firstLine -eq $ManagedMarker -or $firstLine -eq "# Managed by WebUI") {
        Remove-Item -LiteralPath $Path
        return $true
    }
    Write-Warning "Skipped unmanaged file: $Path"
    return $false
}

$repoRoot = Get-RepoRoot
Set-Location -LiteralPath $repoRoot

$enabledAgents = Get-EnabledAgents (Read-TextFile $ConfigPath)
$enabledSet = @{}
foreach ($agent in $enabledAgents) {
    $enabledSet[$agent] = $true
}

New-Item -ItemType Directory -Force -Path $AgentConfigDir | Out-Null

foreach ($agent in $enabledAgents) {
    $configPath = Join-Path $AgentConfigDir "config.agent.$agent.yaml"
    $createdConfig = Ensure-AgentConfig $agent $configPath
    if ($createdConfig) {
        Write-Host "Applied agent '$agent' (created missing config)."
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

Write-Host "Enabled agents: $($enabledAgents -join ', ')"

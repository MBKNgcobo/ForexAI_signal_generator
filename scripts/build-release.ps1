#Requires -Version 5.1
<#
  ForexAI - build the client distribution ZIP (maintainer only).

  Builds release/ForexAI-v1.0.0-Windows(.zip) from an allow-list so the
  client never receives .git, node_modules, venvs, caches, real .env,
  backups, training data, or dev notes. Refuses to run if a real secret
  is detectable in .env.example or if .env would be included.
#>
[CmdletBinding()]
param(
  [string]$Version = "v1.0.0",
  [string]$RepoRoot = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  if ($PSScriptRoot) { $RepoRoot = (Split-Path -Parent $PSScriptRoot) }
  else { $RepoRoot = (Get-Location).Path }
}

$ReleaseRoot = Join-Path -Path $RepoRoot -ChildPath "release"
$Stage = Join-Path -Path $ReleaseRoot -ChildPath "ForexAI-$Version-Windows"
$Zip = Join-Path -Path $ReleaseRoot -ChildPath "ForexAI-$Version-Windows.zip"

Write-Host ""
Write-Host "ForexAI - building client package $Version"
Write-Host ""

# --- Secret hygiene: .env.example must contain only placeholders ------------
$example = Get-Content (Join-Path -Path $RepoRoot -ChildPath ".env.example") -Raw
foreach ($v in @("POSTGRES_PASSWORD", "JWT_KEY", "TWELVE_DATA_API_KEY", "OPENROUTER_API_KEY")) {
  if ($example -match "(?m)^$v=(?!replace-me)(?!`$)(.+)$") {
    $val = $Matches[1].Trim()
    if ($val -ne "" -and $val -notlike "*replace-me*") {
      throw "Refusing to package: .env.example sets $v to a non-placeholder value."
    }
  }
}

# --- Fresh stage -------------------------------------------------------------
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path -Path $Stage -ChildPath "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path -Path $Stage -ChildPath "docs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path -Path $Stage -ChildPath "backups") | Out-Null
$backupsDir = Join-Path -Path $Stage -ChildPath "backups"
$gitkeep = Join-Path -Path $backupsDir -ChildPath ".gitkeep"
if (!(Test-Path -LiteralPath $gitkeep)) { New-Item -ItemType File -Path $gitkeep -Force | Out-Null }

function Copy-File([string]$rel) {
  $src = Join-Path -Path $RepoRoot -ChildPath $rel
  $dst = Join-Path -Path $Stage -ChildPath $rel
  $dir = Split-Path -Parent $dst
  if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Copy-Item -Force $src $dst
}

# --- Top-level client surface ------------------------------------------------
foreach ($f in @(
  "docker-compose.yml", ".env.example", "version.txt",
  "START_HERE.txt", "README_CLIENT.md",
  "start.bat", "stop.bat", "restart.bat", "status.bat",
  "logs.bat", "reset.bat", "collect-diagnostics.bat",
  "start.sh", "stop.sh", "status.sh", "logs.sh"
)) { Copy-File $f }

# --- Scripts (client .bat only; no .ps1 dev tools, no secrets) ----------------
foreach ($f in @(
  "scripts\start-forexai.bat", "scripts\stop-forexai.bat",
  "scripts\restart-forexai.bat", "scripts\status-forexai.bat",
  "scripts\logs-forexai.bat", "scripts\reset-forexai.bat",
  "scripts\backup-forexai.bat", "scripts\add-user-forexai.bat",
  "scripts\update-forexai.bat", "scripts\collect-diagnostics.bat"
)) { Copy-File $f }

# --- Docs --------------------------------------------------------------------
foreach ($f in @(
  "docs\INSTALLATION_GUIDE.md", "docs\TROUBLESHOOTING.md",
  "docs\BACKUP_AND_RESTORE.md", "docs\FAQ.md",
  "docs\ENVIRONMENT_VARIABLES.md", "docs\client-installation.md",
  "docs\user-guide.md"
)) { Copy-File $f }

# --- .NET API (source needed for compose build; exclude bin/obj/secrets) ------
$apiDirs = @("ForexAI.Api", "ForexAI.Application", "ForexAI.Domain", "ForexAI.Infrastructure")
foreach ($d in $apiDirs) {
  Get-ChildItem (Join-Path -Path $RepoRoot -ChildPath "ForexAI\$d") -Recurse -File |
    Where-Object { $_.FullName -notmatch "\\(bin|obj)\\" -and $_.Name -notmatch "\.(user|suo)$" } |
    ForEach-Object {
      $rel = "ForexAI\" + $_.FullName.Substring((Join-Path -Path $RepoRoot -ChildPath "ForexAI\").Length)
      Copy-File $rel
    }
}
Copy-File "ForexAI\ForexAI.sln"
Copy-File "ForexAI\Dockerfile"
Copy-File "ForexAI\.dockerignore"

# --- Python AI service (app + manifest + fetcher; models via release fetch) ---
Get-ChildItem (Join-Path -Path $RepoRoot -ChildPath "forexai-ai\app") -Recurse -File |
  Where-Object { $_.Name -notmatch "\.pyc$" } |
  ForEach-Object {
    $rel = "forexai-ai\" + $_.FullName.Substring((Join-Path -Path $RepoRoot -ChildPath "forexai-ai\").Length)
    Copy-File $rel
  }
foreach ($f in @(
  "forexai-ai\requirements.txt", "forexai-ai\Dockerfile",
  "forexai-ai\.dockerignore", "forexai-ai\.env.example",
  "forexai-ai\models\ARTIFACTS.sha256", "forexai-ai\models\calibration.json",
  "forexai-ai\scripts\fetch_model_artifacts.py"
)) { Copy-File $f }

# --- Dashboard (source for npm build; no node_modules/dist) -------------------
Get-ChildItem (Join-Path -Path $RepoRoot -ChildPath "forexai-dashboard") -Recurse -File |
  Where-Object {
    $_.FullName -notmatch "\\(node_modules|dist|\.vs)\\" -and
    $_.Name -notmatch "\.log$"
  } |
  ForEach-Object {
    $rel = "forexai-dashboard\" + $_.FullName.Substring((Join-Path -Path $RepoRoot -ChildPath "forexai-dashboard\").Length)
    Copy-File $rel
  }

# --- Refuse to ship secrets / junk -------------------------------------------
$bad = Get-ChildItem $Stage -Recurse -Force -Include @(".env", "*.log", "*.joblib", "*.sql") |
  Where-Object { $_.Name -ne ".env.example" }
if ($bad) { throw ("Refusing to package, forbidden files staged: " + (($bad | ForEach-Object { $_.FullName }) -join ", ")) }
foreach ($d in @(".git", ".github", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".vs")) {
  if (Test-Path (Join-Path $Stage $d)) { throw "Refusing to package: staged $d" }
}

# --- Zip ----------------------------------------------------------------------
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path -Path $Stage -ChildPath "*") -DestinationPath $Zip -CompressionLevel Optimal
$hash = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path -Leaf $Zip)" | Set-Content "$Zip.sha256"

Write-Host ""
Write-Host "[OK] Staged: $Stage"
Write-Host "[OK] ZIP:    $Zip"
Write-Host "[OK] SHA256: $hash"
Write-Host ""



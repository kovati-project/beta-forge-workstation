# AI Workstation — Sync and Deploy
# Copies project files to the workstation, then runs deployment over SSH.
#
# Usage (from repo root in PowerShell):
#   .\sync-and-deploy.ps1                        # sync only
#   .\sync-and-deploy.ps1 -Deploy                # sync + deploy all phases
#   .\sync-and-deploy.ps1 -Deploy -From 08       # sync + deploy from phase 08
#   .\sync-and-deploy.ps1 -Deploy -Phase 13      # sync + deploy phase 13 only
#   .\sync-and-deploy.ps1 -Deploy -Validate      # sync + deploy with validation
#   .\sync-and-deploy.ps1 -SyncOnly -DryRun      # preview sync, no transfer

param(
    [switch]$Deploy,
    [switch]$SyncOnly,
    [switch]$Validate,
    [switch]$DryRun,
    [string]$From    = "",
    [string]$To      = "",
    [string]$Phase   = ""
)

$ErrorActionPreference = "Stop"

$Host_      = "kasemo@10.10.10.2"
$RemoteDir  = "~/ai-workstation"
$RepoRoot   = $PSScriptRoot   # directory containing this script

# ── Sync ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Sync to workstation ===" -ForegroundColor Blue
Write-Host "Source:      $RepoRoot"
Write-Host "Destination: ${Host_}:${RemoteDir}"
if ($DryRun) { Write-Host "Mode:        DRY RUN" -ForegroundColor Yellow }
Write-Host ""

# Build rsync command
$rsyncArgs = @(
    "-avz",
    "--exclude=.git/",
    "--exclude=*.pyc",
    "--exclude=__pycache__/",
    "--exclude=.env",
    "--exclude=*.env",
    "--exclude=plan/",
    "--exclude=distro/",
    "--exclude=node_modules/",
    "--exclude=.pytest_cache/",
    "--exclude=*.egg-info/"
)

if ($DryRun) { $rsyncArgs += "--dry-run" }

$rsyncArgs += @("${RepoRoot}/", "${Host_}:${RemoteDir}/")

# Prefer rsync, fall back to scp
$rsyncCmd = Get-Command rsync -ErrorAction SilentlyContinue
$scpCmd   = Get-Command scp   -ErrorAction SilentlyContinue
$rsyncBin = if ($rsyncCmd) { $rsyncCmd.Source } else { $null }
$scpBin   = if ($scpCmd)   { $scpCmd.Source   } else { $null }

if ($rsyncBin) {
    Write-Host "Using rsync..."
    & $rsyncBin @rsyncArgs
    if ($LASTEXITCODE -ne 0) { throw "rsync failed (exit $LASTEXITCODE)" }
} elseif ($scpBin) {
    if ($DryRun) {
        Write-Host "[dry-run] Would run: scp -r docker scripts configs loadout-manager ${Host_}:${RemoteDir}/"
    } else {
        Write-Host "rsync not found — using scp..."
        & $scpBin -r docker scripts configs loadout-manager "${Host_}:${RemoteDir}/"
        if ($LASTEXITCODE -ne 0) { throw "scp failed (exit $LASTEXITCODE)" }
    }
} else {
    throw "Neither rsync nor scp found. Install Git for Windows (includes both) or OpenSSH."
}

if (-not $DryRun) {
    # Make scripts executable on workstation
    Write-Host ""
    Write-Host "Setting permissions..."
    ssh $Host_ "find ${RemoteDir}/scripts -name '*.sh' -o -name '*.py' | xargs dos2unix -q 2>/dev/null; chmod +x ${RemoteDir}/scripts/*.sh ${RemoteDir}/scripts/*.py 2>/dev/null; echo '  + chmod +x / dos2unix scripts/*'"
}

Write-Host ""
Write-Host "Sync complete." -ForegroundColor Green

# ── Deploy (optional) ─────────────────────────────────────────────────────────
if (-not $Deploy -and -not $SyncOnly) {
    Write-Host ""
    Write-Host "Files synced. To deploy:"
    Write-Host "  .\sync-and-deploy.ps1 -Deploy"
    Write-Host "  .\sync-and-deploy.ps1 -Deploy -From 03"
    Write-Host "  ssh $Host_ 'cd ~/ai-workstation && bash scripts/deploy-all.sh'"
    Write-Host ""
    exit 0
}

if ($SyncOnly -or $DryRun) { exit 0 }

# Build deploy-all.sh arguments
$deployArgs = ""
if ($Phase  -ne "") { $deployArgs += " --phase $Phase" }
else {
    if ($From -ne "") { $deployArgs += " --from $From" }
    if ($To   -ne "") { $deployArgs += " --to $To" }
}
if ($Validate) { $deployArgs += " --validate" }

$remoteCmd = "cd ~/ai-workstation && bash scripts/deploy-all.sh$deployArgs"

Write-Host ""
Write-Host "=== Remote deploy ===" -ForegroundColor Blue
Write-Host "Running on workstation: $remoteCmd"
Write-Host ""

ssh -t $Host_ $remoteCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Deployment finished with errors. Check output above." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== All done ===" -ForegroundColor Green

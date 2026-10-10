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

# Deploy stamp: records which commit was synced so scripts/healthcheck.sh can show
# it and warn when the host is behind. Lives under scripts/ because both rsync
# (whole tree) and the scp fallback (docker scripts configs loadout-manager) copy it,
# and no entry in the exclude list below matches it. It is written just before the
# sync and removed locally afterwards so it never shows up in `git status`.
$StampRel   = "scripts/.deployed-commit"
$StampPath  = Join-Path $RepoRoot "scripts\.deployed-commit"

function New-DeployStampText {
    param([string]$Root, [string]$ExcludeRel)

    # Native git stderr must not become a terminating error under -Stop.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $full   = "unknown"
        $short  = "unknown"
        $branch = "unknown"
        $dirty  = "unknown"

        $gitCmd = Get-Command git -ErrorAction SilentlyContinue
        if ($gitCmd) {
            $out = & git -C $Root rev-parse HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $full = ("$out").Trim() }

            $out = & git -C $Root rev-parse --short HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $short = ("$out").Trim() }

            $out = & git -C $Root rev-parse --abbrev-ref HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                $branch = ("$out").Trim()
                if ($branch -eq "HEAD") { $branch = "(detached)" }
            }

            # Uncommitted = modified, staged or untracked files (all of which rsync
            # would ship). The stamp file itself is excluded so a leftover stamp
            # cannot make the tree look dirty.
            $status = & git -C $Root status --porcelain -- . ":(exclude)$ExcludeRel" 2>$null
            if ($LASTEXITCODE -eq 0) {
                if ($status) { $dirty = "true" } else { $dirty = "false" }
            }
        }

        $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        $lines = @(
            "short=$short",
            "full=$full",
            "branch=$branch",
            "timestamp=$stamp",
            "dirty=$dirty"
        )
        return (($lines -join "`n") + "`n")
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
}

# ── Sync ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Sync to workstation ===" -ForegroundColor Blue
Write-Host "Source:      $RepoRoot"
Write-Host "Destination: ${Host_}:${RemoteDir}"
if ($DryRun) { Write-Host "Mode:        DRY RUN" -ForegroundColor Yellow }
Write-Host ""

# Write the deploy stamp (LF line endings, UTF-8 without BOM so bash can parse it).
# Written even for -DryRun so the rsync preview lists it; removed again in `finally`.
$stampText = New-DeployStampText -Root $RepoRoot -ExcludeRel $StampRel
[System.IO.File]::WriteAllText($StampPath, $stampText, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Deploy stamp ($StampRel):"
foreach ($stampLine in ($stampText -split "`n")) {
    if ($stampLine -ne "") { Write-Host "  $stampLine" }
}
if ($stampText -match "dirty=true") {
    Write-Host "  WARNING: uncommitted changes are being deployed" -ForegroundColor Yellow
}
Write-Host ""

try {

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

}
finally {
    # Keep the working tree clean: the stamp only needs to exist during the transfer.
    if (Test-Path -LiteralPath $StampPath) {
        Remove-Item -LiteralPath $StampPath -Force -ErrorAction SilentlyContinue
    }
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

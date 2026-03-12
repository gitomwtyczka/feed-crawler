<#
.SYNOPSIS
    Remote VPS execution helper — avoids PowerShell SSH quoting issues.
.DESCRIPTION
    Copies a script to VPS via SCP, executes it via SSH, then cleans up.
    Solves the recurring CRLF + quote escaping problems.
.EXAMPLE
    .\scripts\vps-run.ps1 scripts\migrate.sh
    .\scripts\vps-run.ps1 scripts\deploy.sh
    .\scripts\vps-run.ps1 some_script.py -Runtime python3
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath,
    
    [string]$Runtime = "bash",
    [string]$VpsHost = "ubuntu@147.224.162.100",
    [string]$SshKey = "$env:USERPROFILE\.ssh\oracle-crimson.key",
    [switch]$Sudo
)

$ErrorActionPreference = "Stop"

# Resolve paths
$localFile = Resolve-Path $ScriptPath
$remoteName = "vps_task_$(Get-Date -Format 'yyyyMMdd_HHmmss')_$(Split-Path $ScriptPath -Leaf)"
$remotePath = "/tmp/$remoteName"

Write-Host "[VPS-RUN] Remote Execute" -ForegroundColor Cyan
Write-Host "  Script: $localFile"
Write-Host "  Runtime: $Runtime"
Write-Host "  Host: $VpsHost"

# Step 1: Fix CRLF -> LF before upload
$content = [System.IO.File]::ReadAllText($localFile)
$lfContent = $content -replace "`r`n", "`n"
$tempFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tempFile, $lfContent, [System.Text.UTF8Encoding]::new($false))

# Step 2: SCP upload
Write-Host "[UPLOAD] Uploading to $remotePath..." -ForegroundColor Yellow
scp -i $SshKey $tempFile "${VpsHost}:${remotePath}" 2>&1
if ($LASTEXITCODE -ne 0) { throw "SCP failed" }

# Step 3: SSH execute
$sudoPrefix = if ($Sudo) { "sudo " } else { "" }
Write-Host "[EXEC] Executing on VPS..." -ForegroundColor Green
ssh -i $SshKey $VpsHost "${sudoPrefix}${Runtime} ${remotePath}; rm -f ${remotePath}"
$exitCode = $LASTEXITCODE

# Cleanup
Remove-Item $tempFile -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {
    Write-Host "[FAIL] Script exited with code $exitCode" -ForegroundColor Red
    exit $exitCode
}

Write-Host "[OK] Done!" -ForegroundColor Green

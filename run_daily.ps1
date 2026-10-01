# DailyScout Morning Briefing PowerShell Automation Script
# Runs daily to gather news, synthesize reports, and dispatch emails.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[$Timestamp] Starting DailyScout Autonomous Agent..." -ForegroundColor Cyan

# Ensure reports directory exists
if (-not (Test-Path "reports")) {
    New-Item -ItemType Directory -Path "reports" | Out-Null
}

# Execute Scout
try {
    python scout.py --send-email *>> reports\runner.log
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[$Timestamp] DailyScout completed successfully." -ForegroundColor Green
    } else {
        Write-Host "[$Timestamp] DailyScout failed with exit code $LASTEXITCODE." -ForegroundColor Red
    }
} catch {
    Write-Host "[$Timestamp] Exception occurred: $_" -ForegroundColor Red
}

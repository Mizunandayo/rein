<#
.SYNOPSIS
  Blocks any commit that stages the private blueprint.
.DESCRIPTION
  Second line of defence behind .gitignore. A `git add -f` or a rename that
  slips past the ignore patterns would otherwise put the full private
  specification into permanent public history.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$staged = git diff --cached --name-only --diff-filter=ACMR
if (-not $staged) { exit 0 }

$offenders = $staged | Where-Object { (Split-Path $_ -Leaf) -match '(?i)_blueprint[^\\/]*\.md$' }

if ($offenders) {
    Write-Host ''
    Write-Host '  COMMIT BLOCKED — private specification staged' -ForegroundColor Red
    Write-Host ''
    $offenders | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    Write-Host ''
    Write-Host '  The blueprint is private (spec §20) and must never enter git'
    Write-Host '  history. Unstage it:'
    Write-Host ''
    $offenders | ForEach-Object { Write-Host "    git restore --staged `"$_`"" -ForegroundColor Cyan }
    Write-Host ''
    exit 1
}
exit 0

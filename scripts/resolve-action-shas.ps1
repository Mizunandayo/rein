<#
.SYNOPSIS
  Resolve every third-party GitHub Action reference used in this repo's
  workflows to an immutable commit SHA.
.DESCRIPTION
  This list must be kept in sync with every `uses:` line across
  .github/workflows/*.yml. If you add a new action to a workflow, add its
  tag here too -- a moving tag left unresolved defeats the whole point of
  pinning (see FRICTION.md F-004: this list originally missed
  gitleaks/gitleaks-action, which is why that check exists below).
#>
$actions = @(
  'actions/checkout@v7.0.1',
  'astral-sh/setup-uv@v10.2.0',
  'github/codeql-action@v4.38.2',
  'gitleaks/gitleaks-action@v3.0.0'
)
foreach ($a in $actions) {
  $repo, $ref = $a -split '@'
  $sha = gh api "repos/$repo/commits/$ref" --jq '.sha' 2>$null
  if ($sha) { "{0}@{1}  # {2}" -f $repo, $sha, $ref }
  else      { "COULD NOT RESOLVE $a" }
}

# ── Self-check: does every `uses:` action actually appear in $actions? ──
# This is what would have caught the gitleaks-action gap automatically.
$knownRepos = $actions | ForEach-Object { ($_ -split '@')[0] }
$workflowFiles = Get-ChildItem -Path (Join-Path $PSScriptRoot '..\.github\workflows') -Filter '*.yml' -ErrorAction SilentlyContinue

$usedRepos = foreach ($f in $workflowFiles) {
  Select-String -Path $f -Pattern 'uses:\s*([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)' |
    ForEach-Object { $_.Matches[0].Groups[1].Value }
}
$usedRepos = $usedRepos | Sort-Object -Unique

$missing = $usedRepos | Where-Object { $_ -notin $knownRepos }
if ($missing) {
  Write-Host ''
  Write-Host "WARNING: these actions are used in a workflow but missing from `$actions` above:" -ForegroundColor Red
  $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
  Write-Host 'Add them to the $actions list at the top of this script and re-run.' -ForegroundColor Red
}

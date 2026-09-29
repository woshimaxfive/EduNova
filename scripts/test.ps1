$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location $repoRoot

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string] $FilePath,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CommandArguments
  )

  & $FilePath @CommandArguments
  $exitCode = $LASTEXITCODE
  if ($null -ne $exitCode -and $exitCode -ne 0) {
    throw "Command failed with exit code ${exitCode}: $FilePath $($CommandArguments -join ' ')"
  }
}

Write-Host "== EduNova verification =="

Write-Host "== Encoding check =="
& "$repoRoot\scripts\verify_encoding.ps1"
& "$repoRoot\scripts\test_local_search_setup.ps1"
& "$repoRoot\scripts\test_local_speech_setup.ps1"

if (Test-Path -LiteralPath "$repoRoot\backend") {
  Write-Host "== Backend checks =="
  if (Test-Path -LiteralPath "$repoRoot\.venv\Scripts\python.exe") {
    $python = "$repoRoot\.venv\Scripts\python.exe"
  }
  else {
    $python = "py"
  }

  if (Test-Path -LiteralPath "$repoRoot\backend\tests") {
    Invoke-CheckedCommand $python -m pytest "$repoRoot\backend\tests"
    Write-Host "== Offline AI quality evaluation =="
    Invoke-CheckedCommand $python -m backend.evals.run --mode offline --output "$repoRoot\output\ai-eval\offline-latest.json"
    Write-Host "== Release readiness evidence =="
    Invoke-CheckedCommand $python -m backend.evals.release_readiness --output "$repoRoot\output\release-readiness\latest.json"
  }
  else {
    Write-Host "backend tests not found; skipped"
  }

  Write-Host "== OpenAPI contract drift check =="
  Invoke-CheckedCommand $python "$repoRoot\scripts\check_openapi.py"

  if (Test-Path -LiteralPath "$repoRoot\backend") {
    Invoke-CheckedCommand $python -m ruff check "$repoRoot\backend"
  }

  if (Test-Path -LiteralPath "$repoRoot\alembic.ini") {
    Invoke-CheckedCommand $python -m alembic heads
  }
}
else {
  Write-Host "backend directory not found; skipped"
}

if (Test-Path -LiteralPath "$repoRoot\frontend\package.json") {
  Write-Host "== Frontend checks =="
  Push-Location "$repoRoot\frontend"
  try {
    Invoke-CheckedCommand "pnpm" lint
    Invoke-CheckedCommand "pnpm" test
    Invoke-CheckedCommand "pnpm" build
  }
  finally {
    Pop-Location
  }
}
else {
  Write-Host "frontend package not found; skipped"
}

if (Test-Path -LiteralPath "$repoRoot\desktop\package.json") {
  Write-Host "== Desktop permission and packaging checks =="
  Invoke-CheckedCommand "node" --test "$repoRoot/desktop/test/*.test.cjs"
}

if (Test-Path -LiteralPath "$repoRoot\docker-compose.yml") {
  Write-Host "== Docker Compose config =="
  Invoke-CheckedCommand "docker" compose config --quiet
}
else {
  Write-Host "docker-compose.yml not found; skipped"
}

Write-Host "verification complete"

$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
$projectName = "edunova-e2e"
$composeArgs = @(
  "compose",
  "-p", $projectName,
  "-f", "$repoRoot\docker-compose.yml",
  "-f", "$repoRoot\docker-compose.e2e.yml"
)
$baseUrl = if ($env:E2E_BASE_URL) { $env:E2E_BASE_URL } else { "http://127.0.0.1:18080" }

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string] $FilePath,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CommandArguments
  )

  & $FilePath @CommandArguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($CommandArguments -join ' ')"
  }
}

Write-Host "== Reset isolated E2E project =="
& docker @composeArgs down -v --remove-orphans

try {
  Write-Host "== Start isolated E2E project =="
  Invoke-CheckedCommand -FilePath "docker" -CommandArguments ($composeArgs + @("up", "--build", "-d", "--wait", "--wait-timeout", "180"))

  Write-Host "== Verify E2E health =="
  $health = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/health" -TimeoutSec 10
  if ($health.StatusCode -ne 200) {
    throw "E2E health check returned $($health.StatusCode)."
  }

  Write-Host "== Verify PostgreSQL/pgvector cosine ranking =="
  Invoke-CheckedCommand -FilePath "docker" -CommandArguments ($composeArgs + @("exec", "-T", "backend", "python", "-m", "backend.integration.pgvector_rag_check"))

  Write-Host "== Verify isolated code execution policy =="
  Invoke-CheckedCommand -FilePath "docker" -CommandArguments ($composeArgs + @("exec", "-T", "backend", "python", "-m", "backend.integration.code_verifier_check"))

  Write-Host "== Run learning closure Playwright E2E =="
  Push-Location "$repoRoot\frontend"
  try {
    $env:E2E_BASE_URL = $baseUrl
    Invoke-CheckedCommand -FilePath "pnpm" -CommandArguments @("test:e2e")
  }
  finally {
    Pop-Location
  }
}
finally {
  Write-Host "== Remove isolated E2E containers and volumes =="
  & docker @composeArgs down -v --remove-orphans
}

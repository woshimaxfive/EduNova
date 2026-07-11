$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
$python = if (Test-Path -LiteralPath "$repoRoot\.venv\Scripts\python.exe") {
  "$repoRoot\.venv\Scripts\python.exe"
}
else {
  "py"
}
$mode = if ($env:EDUNOVA_EVAL_ALLOW_NETWORK -eq "1") { "live" } else { "offline" }
$output = "$repoRoot\output\ai-eval\$mode-latest.json"

Set-Location $repoRoot
& $python -m backend.evals.run --mode $mode --output $output
if ($LASTEXITCODE -ne 0) {
  throw "AI quality evaluation failed with exit code $LASTEXITCODE."
}

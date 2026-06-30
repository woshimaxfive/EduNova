$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location $repoRoot

$textFilePattern = '(^|/)(Dockerfile|\.dockerignore|\.editorconfig|\.gitattributes|\.gitignore)$|\.(py|ts|tsx|js|jsx|json|md|txt|yml|yaml|toml|env|css|html|ps1|psm1|psd1|ini|cfg|conf|example|sql|sh|bash|dockerfile)$'
$trackedAndUntracked = git -c core.quotePath=false ls-files --cached --others --exclude-standard

$utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)
$failed = $false

foreach ($relativePath in $trackedAndUntracked) {
  if ([string]::IsNullOrWhiteSpace($relativePath)) {
    continue
  }

  if ($relativePath -notmatch $textFilePattern) {
    continue
  }

  if ($relativePath -match '(^|/)(node_modules|\.venv|venv|dist|build|storage|uploads|logs|\.worktrees)/') {
    continue
  }

  $path = Join-Path $repoRoot $relativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    continue
  }

  $bytes = [System.IO.File]::ReadAllBytes($path)

  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    Write-Error "UTF-8 BOM found: $relativePath"
    $failed = $true
    continue
  }

  if ($bytes.Length -ge 2 -and (($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) -or ($bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF))) {
    Write-Error "UTF-16 BOM found: $relativePath"
    $failed = $true
    continue
  }

  if ($bytes.Length -ge 4 -and (($bytes[0] -eq 0x00 -and $bytes[1] -eq 0x00 -and $bytes[2] -eq 0xFE -and $bytes[3] -eq 0xFF) -or ($bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE -and $bytes[2] -eq 0x00 -and $bytes[3] -eq 0x00))) {
    Write-Error "UTF-32 BOM found: $relativePath"
    $failed = $true
    continue
  }

  if ($bytes -contains 0x00) {
    Write-Error "NUL byte found, possible UTF-16/UTF-32 or binary content: $relativePath"
    $failed = $true
    continue
  }

  try {
    $text = $utf8Strict.GetString($bytes)
  }
  catch {
    Write-Error "Invalid UTF-8 or possible legacy encoding found: $relativePath"
    $failed = $true
    continue
  }

  if ($text -match '\\u[0-9a-fA-F]{4}') {
    Write-Error "Unicode escape found: $relativePath"
    $failed = $true
  }
}

if ($failed) {
  exit 1
}

Write-Host "encoding check passed"

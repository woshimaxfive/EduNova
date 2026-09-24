param([string] $Path = ".env")
$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Path).Path
$text = [IO.File]::ReadAllText($resolved, [Text.Encoding]::UTF8)
# Remove retired paid-search credentials without printing or backing up secrets.
# Main-model, speech and unrelated settings remain untouched.
$updated = [regex]::Replace($text, '(?m)^[ \t]*(?:export[ \t]+)?WEB_SEARCH_(?:PROVIDER|ENDPOINT|API_KEY)[ \t]*=[^\r\n]*(\r?\n|$)', '')
if ($updated -ne $text) {
  [IO.File]::WriteAllText($resolved, $updated, [Text.UTF8Encoding]::new($false))
}
Write-Host 'Local search enabled. Retired search settings removed; other credentials retained.'

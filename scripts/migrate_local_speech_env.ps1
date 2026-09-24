param([string] $Path = ".env")
$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Path).Path
$text = [IO.File]::ReadAllText($resolved, [Text.Encoding]::UTF8)
$updated = [regex]::Replace($text, '(?m)^[ \t]*(?:export[ \t]+)?SYSTEM_SPEECH_[A-Z_]+[ \t]*=[^\r\n]*(\r?\n|$)', '')
if ($updated -ne $text) {
  [IO.File]::WriteAllText($resolved, $updated, [Text.UTF8Encoding]::new($false))
}
Write-Host 'Retired speech credentials removed. Main-model credentials retained.'

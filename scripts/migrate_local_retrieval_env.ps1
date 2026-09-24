param([string] $Path = ".env")
$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Path).Path
$text = [IO.File]::ReadAllText($resolved, [Text.Encoding]::UTF8)
$values = @{}
foreach ($line in ($text -split "\r?\n")) {
  if ($line -match '^([A-Z_]+)=(.*)$') { $values[$matches[1]] = $matches[2] }
}
# Preserve an explicitly shared Xfyun speech connection before removing retrieval keys.
if ($values['SYSTEM_EMBEDDING_PROVIDER'] -eq 'xfyun_embedding') {
  foreach ($suffix in @('APP_ID', 'API_KEY', 'API_SECRET')) {
    $speechName = "SYSTEM_SPEECH_$suffix"
    if (-not $values[$speechName] -and $values["SYSTEM_EMBEDDING_$suffix"]) {
      $value = $values["SYSTEM_EMBEDDING_$suffix"]
      if ($text -match "(?m)^$speechName=") {
        $text = [regex]::Replace($text, "(?m)^$speechName=[^\r\n]*", [System.Text.RegularExpressions.MatchEvaluator]{ param($m) "$speechName=$value" })
      } else { $text += "`n$speechName=$value`n" }
    }
  }
}
$text = [regex]::Replace($text, '(?m)^SYSTEM_(EMBEDDING|RERANK)_[A-Z_]+=[^\r\n]*(\r?\n|$)', '')
$text = $text.TrimEnd() + "`nSYSTEM_EMBEDDING_PROVIDER=fastembed_local`n"
[IO.File]::WriteAllText($resolved, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'Local retrieval enabled. External retrieval settings removed; main-model settings retained.'

param([string] $Path = ".env")
$ErrorActionPreference = "Stop"
$resolved = (Resolve-Path -LiteralPath $Path).Path
$text = [IO.File]::ReadAllText($resolved, [Text.Encoding]::UTF8)
$text = [regex]::Replace($text, '(?m)^SYSTEM_(EMBEDDING|RERANK)_[A-Z_]+=[^\r\n]*(\r?\n|$)', '')
$text = $text.TrimEnd() + "`nSYSTEM_EMBEDDING_PROVIDER=fastembed_local`n"
[IO.File]::WriteAllText($resolved, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'Local retrieval enabled. External retrieval settings removed; main-model settings retained.'

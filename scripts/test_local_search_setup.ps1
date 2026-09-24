$ErrorActionPreference = "Stop"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("edunova-search-env-" + [guid]::NewGuid().ToString('N') + ".env")
try {
  $retained = "# 合成启动配置`r`nSYSTEM_MODEL_API_KEY=synthetic-main`r`nSYSTEM_SPEECH_API_KEY=synthetic-speech`r`nWEB_SEARCH_MAX_RESULTS=3`r`n"
  $legacy = "WEB_SEARCH_PROVIDER=tavily`r`nWEB_SEARCH_ENDPOINT=https://api.example.test/search`r`nWEB_SEARCH_API_KEY=synthetic-search`r`n export WEB_SEARCH_API_KEY = 'duplicate-synthetic-search'`r`n"
  [IO.File]::WriteAllText($fixture, $retained + $legacy, [Text.UTF8Encoding]::new($false))
  & "$PSScriptRoot\migrate_local_search_env.ps1" -Path $fixture
  if ([IO.File]::ReadAllText($fixture, [Text.Encoding]::UTF8) -cne $retained) {
    throw 'Migration did not preserve unrelated settings exactly.'
  }
  $hash = (Get-FileHash -LiteralPath $fixture).Hash
  & "$PSScriptRoot\migrate_local_search_env.ps1" -Path $fixture
  if ((Get-FileHash -LiteralPath $fixture).Hash -ne $hash) { throw 'Migration is not idempotent.' }
  $bytes = [IO.File]::ReadAllBytes($fixture)
  if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) {
    throw 'Unexpected UTF-8 BOM.'
  }
  Write-Host 'Search environment migration: preservation, retired key removal, idempotence and encoding passed.'
}
finally {
  if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture }
}

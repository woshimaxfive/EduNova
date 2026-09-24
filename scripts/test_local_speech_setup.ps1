$ErrorActionPreference = "Stop"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("edunova-speech-env-" + [guid]::NewGuid().ToString('N') + ".env")
try {
  $retained = "# 合成配置`r`nSYSTEM_MODEL_API_KEY=synthetic-main`r`nPOSTGRES_DB=synthetic`r`n"
  $legacy = "SYSTEM_SPEECH_APP_ID=old`r`nSYSTEM_SPEECH_API_KEY=old`r`n export SYSTEM_SPEECH_API_SECRET = 'old'`r`n"
  [IO.File]::WriteAllText($fixture, $retained + $legacy, [Text.UTF8Encoding]::new($false))
  & "$PSScriptRoot\migrate_local_speech_env.ps1" -Path $fixture
  if ([IO.File]::ReadAllText($fixture, [Text.Encoding]::UTF8) -cne $retained) {
    throw 'Speech migration did not preserve unrelated settings exactly.'
  }
  $hash = (Get-FileHash -LiteralPath $fixture).Hash
  & "$PSScriptRoot\migrate_local_speech_env.ps1" -Path $fixture
  if ((Get-FileHash -LiteralPath $fixture).Hash -ne $hash) { throw 'Speech migration is not idempotent.' }
  Write-Host 'Speech migration: main model preserved, legacy credentials removed, idempotence passed.'
}
finally {
  if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture }
}

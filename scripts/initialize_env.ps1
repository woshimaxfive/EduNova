param(
  [string] $Path = ".env"
)

$ErrorActionPreference = "Stop"

function New-RandomBase64Url {
  param(
    [Parameter(Mandatory = $true)]
    [int] $ByteCount,

    [switch] $KeepPadding
  )

  $bytes = New-Object byte[] $ByteCount
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $generator.GetBytes($bytes)
  }
  finally {
    $generator.Dispose()
  }

  $value = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
  if (-not $KeepPadding) {
    $value = $value.TrimEnd("=")
  }
  return $value
}

$resolvedPath = (Resolve-Path -LiteralPath $Path).Path
$text = [System.IO.File]::ReadAllText($resolvedPath, [System.Text.Encoding]::UTF8)
$postgresPassword = New-RandomBase64Url -ByteCount 32
$jwtSecret = New-RandomBase64Url -ByteCount 48
$fernetKey = New-RandomBase64Url -ByteCount 32 -KeepPadding

$updated = $text.Replace("change-this-local-database-password", $postgresPassword)
$updated = $updated.Replace("change-this-local-development-secret", $jwtSecret)
$updated = $updated.Replace("replace-with-fernet-key", $fernetKey)

if ($updated -notmatch '(?m)^POSTGRES_PASSWORD=') {
  $newLine = if ($updated.Contains("`r`n")) { "`r`n" } else { "`n" }
  if (-not $updated.EndsWith("`n")) {
    $updated += $newLine
  }
  $updated += "POSTGRES_PASSWORD=$postgresPassword$newLine"
}

if ($updated -ne $text) {
  [System.IO.File]::WriteAllText(
    $resolvedPath,
    $updated,
    (New-Object System.Text.UTF8Encoding($false))
  )
  Write-Host "Local PostgreSQL, JWT, and configuration encryption secrets were initialized."
}
else {
  Write-Host "Local security values are already initialized."
}

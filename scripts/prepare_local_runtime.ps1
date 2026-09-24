$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
  # Reuse the serving image; no host Python installation or extra downloader image.
  docker compose build backend
  if ($LASTEXITCODE -ne 0) { throw "Local runtime build failed." }
  $modelDir = Join-Path $repoRoot "storage/models/bge-small-zh-v1.5"
  New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
  $composeConfig = docker compose config --format json | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) { throw "Compose configuration failed." }
  $imageName = "$($composeConfig.name)-backend"
  docker run --rm --user 0 --entrypoint python `
    --mount "type=bind,source=$modelDir,target=/models" `
    --mount "type=bind,source=$repoRoot/scripts/prepare_local_embedding.py,target=/app/prepare_local_embedding.py,readonly" `
    $imageName /app/prepare_local_embedding.py --model-dir /models
  if ($LASTEXITCODE -ne 0) { throw "Local model preparation failed; services were not switched." }
  docker run --rm --network none --entrypoint python `
    --env LOCAL_EMBEDDING_MODEL_DIR=/models --env HF_HUB_OFFLINE=1 `
    --mount "type=bind,source=$modelDir,target=/models,readonly" `
    $imageName -m backend.integration.local_embedding_check
  if ($LASTEXITCODE -ne 0) { throw "Offline inference failed; services were not switched." }
}
finally { Pop-Location }

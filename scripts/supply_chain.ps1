$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & .\.venv\Scripts\python.exe -m pip_audit -r backend\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip-audit failed" }
    & .\.venv\Scripts\python.exe -m pip_audit -r backend\requirements-ai.txt
    if ($LASTEXITCODE -ne 0) { throw "AI dependency pip-audit failed" }

    Push-Location frontend
    try {
        pnpm audit --audit-level high
        if ($LASTEXITCODE -ne 0) { throw "pnpm audit failed" }
    } finally {
        Pop-Location
    }

    Push-Location evals\promptfoo
    try {
        pnpm audit --audit-level high --prod
        if ($LASTEXITCODE -ne 0) { throw "Promptfoo dependency audit failed" }
    } finally {
        Pop-Location
    }

    & .\.venv\Scripts\python.exe scripts\generate_dependency_licenses.py
    if ($LASTEXITCODE -ne 0) { throw "license inventory failed" }

    # Scan only versioned and pending source files. Traversing Windows bind-mounted
    # node_modules makes a repository scan both slow and nondeterministic.
    $scanRoot = Join-Path ([System.IO.Path]::GetTempPath()) "edunova-trivy-$PID"
    New-Item -ItemType Directory -Path $scanRoot | Out-Null
    try {
        $files = & git -c core.quotepath=false ls-files -co --exclude-standard
        foreach ($file in $files) {
            if ($file -eq ".env") { continue }
            if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
            $destination = Join-Path $scanRoot $file
            $parent = Split-Path -Parent $destination
            if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -LiteralPath $file -Destination $destination
        }

        docker run --rm `
            -v "${scanRoot}:/workspace:ro" `
            -v edunova_trivy_cache:/root/.cache/trivy `
            aquasec/trivy:0.69.3 fs `
            --skip-version-check `
            --scanners secret,misconfig `
            --severity HIGH,CRITICAL `
            --exit-code 1 `
            /workspace
        if ($LASTEXITCODE -ne 0) { throw "Trivy secret or misconfiguration scan failed" }

        docker run --rm `
            -v "${scanRoot}:/workspace:ro" `
            -v edunova_trivy_cache:/root/.cache/trivy `
            aquasec/trivy:0.69.3 fs `
            --skip-version-check `
            --db-repository public.ecr.aws/aquasecurity/trivy-db:2 `
            --timeout 40m `
            --scanners vuln `
            --severity HIGH,CRITICAL `
            --exit-code 1 `
            /workspace
        if ($LASTEXITCODE -ne 0) { throw "Trivy vulnerability scan failed" }
    } finally {
        if (Test-Path -LiteralPath $scanRoot) {
            Remove-Item -LiteralPath $scanRoot -Recurse -Force
        }
    }
} finally {
    Pop-Location
}

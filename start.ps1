param(
    [int]$Port = 8765,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskPython = Join-Path $taskRoot ".venv\Scripts\python.exe"
$taskPreviousEncoding = $env:PYTHONIOENCODING
$env:PYTHONIOENCODING = "utf-8"

Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath $taskPython)) {
        $taskLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $taskLauncher) {
            throw "Python 3.10+ is required. Install it from https://www.python.org/downloads/."
        }
        & $taskLauncher.Source -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the Python virtual environment."
        }
    }

    $taskImportPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $taskPython -c "import shellloop, typer, yaml" 2>$null
        $taskImportExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $taskImportPreference
    }
    if ($taskImportExitCode -ne 0) {
        & $taskPython -m pip install -e ".[dev]"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install Shellloop dependencies."
        }
    }

    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop is required. Shellloop will not run Agent commands on this computer."
    }

    Write-Host "Building the isolated Shellloop sandbox image..."
    & docker build -t shellloop-sandbox:0.4 -f Dockerfile.sandbox .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build the Docker sandbox image."
    }

    Write-Host "Starting Shellloop Studio at http://127.0.0.1:$Port"
    Write-Host "API keys are entered in the local browser and are never saved to disk."
    $taskArguments = @("-m", "shellloop", "studio", "--port", $Port)
    if ($NoOpen) {
        $taskArguments += "--no-open"
    }
    & $taskPython @taskArguments
}
finally {
    Pop-Location
    if ($null -eq $taskPreviousEncoding) {
        Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONIOENCODING = $taskPreviousEncoding
    }
}

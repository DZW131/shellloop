param(
    [ValidateSet("menu", "offline", "cloud")]
    [string]$Mode = "menu",
    [string]$Task,
    [string]$Model,
    [string]$Output,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskPython = Join-Path $taskRoot ".venv\Scripts\python.exe"
$taskPreviousEncoding = $env:PYTHONIOENCODING
$taskClearApiKey = $false
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

    if ($Mode -eq "menu") {
        Write-Host ""
        Write-Host "Shellloop Student Launcher"
        Write-Host "1. Offline demo (no API key)"
        Write-Host "2. Ollama Cloud (personal API key required)"
        $taskChoice = Read-Host "Choose 1 or 2"
        switch ($taskChoice) {
            "1" { $Mode = "offline" }
            "2" { $Mode = "cloud" }
            default { throw "Enter 1 or 2." }
        }
    }

    if ([string]::IsNullOrWhiteSpace($Task)) {
        $Task = Read-Host "Task"
    }
    if ([string]::IsNullOrWhiteSpace($Task)) {
        throw "Task must not be empty."
    }

    if ($Mode -eq "cloud") {
        if ([string]::IsNullOrWhiteSpace($Model)) {
            $Model = Read-Host "Ollama model (Enter for gpt-oss:120b-cloud)"
            if ([string]::IsNullOrWhiteSpace($Model)) {
                $Model = "gpt-oss:120b-cloud"
            }
        }
        if ([string]::IsNullOrWhiteSpace($env:OLLAMA_API_KEY)) {
            $taskSecureKey = Read-Host "Ollama API Key (used only for this run)" -AsSecureString
            $taskPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecureKey)
            try {
                $env:OLLAMA_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPointer)
            }
            finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPointer)
            }
            $taskClearApiKey = $true
        }
    }

    if (-not $Output) {
        $Output = "artifacts/$Mode-$(Get-Date -Format 'yyyyMMdd-HHmmss').traj.json"
    }
    if (-not $Yes) {
        Write-Warning "Shellloop will execute model-generated shell commands in this project directory."
        if ((Read-Host "Run in an isolated teaching environment? Enter y to continue") -ne "y") {
            return
        }
    }

    $taskArguments = @("-m", "shellloop", "--task", $Task, "--output", $Output, "--yolo")
    if ($Mode -eq "cloud") {
        $taskArguments += @("--provider", "ollama-cloud", "--model", $Model)
    }
    & $taskPython @taskArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Shellloop failed with exit code $LASTEXITCODE."
    }
    & $taskPython -m shellloop inspect $Output
    if ($LASTEXITCODE -ne 0) {
        throw "Trajectory inspection failed with exit code $LASTEXITCODE."
    }
    Write-Host "Trajectory: $Output"
}
finally {
    Pop-Location
    if ($taskClearApiKey) {
        Remove-Item Env:OLLAMA_API_KEY -ErrorAction SilentlyContinue
    }
    if ($null -eq $taskPreviousEncoding) {
        Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONIOENCODING = $taskPreviousEncoding
    }
}

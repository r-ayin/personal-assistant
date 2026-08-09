param([string]$Port = $env:PA_ESP_PORT)
$ErrorActionPreference = "Stop"
$log = Join-Path $PSScriptRoot "build-log.txt"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line
}

# Clean MSys pollution inherited from bash
$env:MSYSTEM = ""
$env:TERM = ""
$env:SHELL = ""

$env:IDF_PATH = if ($env:IDF_PATH) { $env:IDF_PATH } else { "E:\x-tool\espidf" }
$env:IDF_TOOLS_PATH = if ($env:IDF_TOOLS_PATH) { $env:IDF_TOOLS_PATH } else { "E:\x-tool\Espressif" }
$env:IDF_PYTHON_ENV_PATH = if ($env:IDF_PYTHON_ENV_PATH) { $env:IDF_PYTHON_ENV_PATH } else { "$env:IDF_TOOLS_PATH\python_env\idf5.5_py3.12_env" }
$venv = "$env:IDF_PYTHON_ENV_PATH\Scripts\python.exe"

# Add required tools to PATH
$tools = "E:\x-tool\Espressif\tools"
$env:PATH = "$tools\ninja\1.12.1;$tools\cmake\3.30.2\bin;$tools\xtensa-esp-elf\esp-14.2.0_20260121\xtensa-esp-elf\bin;$env:PATH"
$env:PATH = "$tools\riscv32-esp-elf\14.2.0_20260121\riscv32-esp-elf\bin;$env:PATH"

Set-Location (Join-Path $PSScriptRoot "xiaozhi-esp32")

# Clean stale build
if ((Test-Path build) -and -not (Test-Path build/sdkconfig)) {
    Write-Log "Removing stale build dir..."
    Remove-Item -Recurse -Force build
}

# Configure
if (-not (Test-Path build/sdkconfig)) {
    Write-Log "=== Step 1: set-target esp32s3 ==="
    & $venv "$env:IDF_PATH\tools\idf.py" set-target esp32s3 2>&1 | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) { Write-Log "CONFIG FAILED"; exit 1 }
}

# Build
Write-Log "=== Step 2: build ==="
$buildOutput = & $venv "$env:IDF_PATH\tools\idf.py" build 2>&1
$buildOutput | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "BUILD FAILED"; exit 1 }

# Find binary
$bin = Get-ChildItem -Path build -Recurse -Name "xiaozhi.bin" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($bin) {
    Write-Log "=== BUILD SUCCESS: build/$bin ==="
} else {
    Write-Log "BUILD OK but xiaozhi.bin not found (check build dir)"
}

# Flash
Write-Log "=== Step 3: flash ==="
$port = if ($Port) { $Port } else { "COM4" }
$flashResult = python -m esptool --chip esp32s3 --port $port write-flash 0x20000 "build/$bin" 2>&1
$flashResult | ForEach-Object { Write-Log $_ }
if ($LASTEXITCODE -ne 0) { Write-Log "FLASH FAILED"; exit 1 }
Write-Log "=== DONE: firmware flashed ==="

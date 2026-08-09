# Clear MSys/MinGW env vars that confuse ESP-IDF
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue
Remove-Item Env:MSYSTEM_CHOST -ErrorAction SilentlyContinue
Remove-Item Env:MSYSTEM_CARCH -ErrorAction SilentlyContinue
Remove-Item Env:MSYSTEM_PREFIX -ErrorAction SilentlyContinue
Remove-Item Env:MINGW_CHOST -ErrorAction SilentlyContinue
Remove-Item Env:MINGW_PREFIX -ErrorAction SilentlyContinue
Remove-Item Env:SHELL -ErrorAction SilentlyContinue
Remove-Item Env:TERM -ErrorAction SilentlyContinue

# 禁用 cmd.exe AutoRun。当前用户注册表 AutoRun="cd /d E:\x-tool"，
# CMake/Ninja 的 cmd.exe /C 链接步骤会切错 cwd，导致找不到 TryCompile .obj。
# /D 仅影响当前构建进程，不修改全局注册表。
$env:COMSPEC = "$env:SystemRoot\System32\cmd.exe /D"

$env:IDF_PATH = "E:\x-tool\espidf"
$env:IDF_TOOLS_PATH = "E:\x-tool\Espressif"
$env:IDF_PYTHON_ENV_PATH = "E:\x-tool\Espressif\python_env\idf5.5_py3.12_env"
$romElf = Get-ChildItem "$env:IDF_TOOLS_PATH\tools\esp-rom-elfs" -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if ($romElf) { $env:ESP_ROM_ELF_DIR = $romElf.FullName }
$venv = "$env:IDF_PYTHON_ENV_PATH\Scripts\python.exe"

# Add ESP-IDF toolchain to PATH
$tools = "E:\x-tool\Espressif\tools"
$env:PATH = "$tools\ninja\1.12.1;$tools\cmake\3.30.2\bin;$tools\xtensa-esp-elf\esp-14.2.0_20260121\xtensa-esp-elf\bin;$env:PATH"
$env:PATH = "$tools\riscv32-esp-elf\esp-14.2.0_20260121\riscv32-esp-elf\bin;$env:PATH"
$env:PATH = "$tools\idf-git\2.44.0\cmd;$env:PATH"

Set-Location "E:\x-tool\personal-assistant\scripts\xiaozhi-esp32"

# sdkconfig 默认值链：sdkconfig.local（本地机密，不入库）存在时追加覆盖
$defaults = "sdkconfig.defaults;sdkconfig.defaults.esp32s3"
if (Test-Path sdkconfig.local) { $defaults += ";sdkconfig.local" }
$env:SDKCONFIG_DEFAULTS = $defaults
Write-Host "SDKCONFIG_DEFAULTS=$env:SDKCONFIG_DEFAULTS"

# Clean stale build directory if needed。build.ninja 是 CMake 配置完成标记；
# sdkconfig 位于项目根目录，不在 build/，不能用 build/sdkconfig 判断。
if ((Test-Path build) -and -not (Test-Path build/build.ninja)) {
    Write-Host "Removing stale build directory..."
    Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
}

# First config if needed
if (-not (Test-Path build/build.ninja)) {
    Write-Host "=== First config: set-target esp32s3 ==="
    $result = & $venv "$env:IDF_PATH\tools\idf.py" set-target esp32s3 2>&1
    $result | Select-Object -Last 10
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CONFIG FAILED (exit=$LASTEXITCODE)"
        exit 1
    }
}

# Build
Write-Host "=== Building firmware ==="
$result = & $venv "$env:IDF_PATH\tools\idf.py" build 2>&1
$result | Select-Object -Last 20
if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD FAILED (exit=$LASTEXITCODE)"
    exit 1
}

Write-Host "=== BUILD SUCCESS ==="
$bin = Get-ChildItem -Path build -Recurse -Name "xiaozhi.bin" -ErrorAction SilentlyContinue
if ($bin) { Write-Host "Firmware: build/$bin" } else { Write-Host "WARNING: xiaozhi.bin not found in build/" }

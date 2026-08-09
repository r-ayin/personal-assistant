$env:IDF_PATH = "E:\x-tool\espidf"
$env:IDF_TOOLS_PATH = "E:\x-tool\Espressif"
$venv = "E:\x-tool\Espressif\python_env\idf5.5_py3.12_env\Scripts\python.exe"

Set-Location "E:\x-tool\personal-assistant\scripts\xiaozhi-esp32"

Write-Host "=== QEMU Test ==="
& $venv "$env:IDF_PATH\tools\idf.py" qemu

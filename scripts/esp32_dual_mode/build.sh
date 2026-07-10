#!/usr/bin/env bash
# build.sh — 一键编译双模式固件
# 用法: bash build.sh [port]
#   port: COM口，默认 COM4
#
# 前置条件:
#   1. ESP-IDF v5.5 已安装（`git clone -b v5.5 https://github.com/espressif/esp-idf.git`）
#   2. ESP-IDF 环境已导出（`source esp-idf/export.sh` 或 Windows: `install.ps1 && export.ps1`）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${1:-COM4}"

echo "========================================"
echo "  ESP32-S3 双模式固件编译"
echo "  项目: $PROJECT_DIR"
echo "  端口: $PORT"
echo "========================================"

cd "$PROJECT_DIR"

# Step 1: 设置目标芯片
echo ""
echo "[1/5] 设置目标芯片 ESP32-S3..."
idf.py set-target esp32s3

# Step 2: 配置
echo ""
echo "[2/5] Menuconfig 配置（检查关键参数）..."
echo "  请确认以下设置无误:"
echo "  - Serial flasher config → Flash size: 16MB"
echo "  - Component config → ESP32S3-Specific → Support for PSRAM: enable"
echo "  - Component config → ESP32S3-Specific → PSRAM mode: Octal SPI 80MHz"
echo "  - Background Audio Collection → PC IP: 你的电脑局域网IP"
echo "  - Background Audio Collection → PC port: 8000"
echo ""
echo "  按 Enter 继续打开 menuconfig..."
read -r
idf.py menuconfig

# Step 3: 解决依赖
echo ""
echo "[3/5] 解决组件依赖..."
idf.py reconfigure

# Step 4: 编译
echo ""
echo "[4/5] 编译固件..."
idf.py build

# Step 5: 烧录
echo ""
echo "[5/5] 烧录到 ESP32-S3 (${PORT})..."
idf.py -p "$PORT" flash

echo ""
echo "========================================"
echo "  ✅ 编译烧录完成！"
echo "  启动监视器: idf.py -p $PORT monitor"
echo "  或: python -m serial.tools.miniterm $PORT 115200"
echo "========================================"

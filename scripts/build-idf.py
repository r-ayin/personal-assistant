#!/usr/bin/env python3
"""Run ESP-IDF build with aggressively clean environment (no MSys/MinGW/Git pollution).

路径参数化（v0.11 净化）：环境变量 IDF_PATH / IDF_TOOLS_PATH 优先，
未设置时回退到脚本相对位置（本仓库 scripts/xiaozhi-esp32）。不硬编码用户名/盘符。
"""
import glob
import subprocess, os, sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IDF_PATH = os.environ.get("IDF_PATH", "")
if not IDF_PATH:
    for cand in (os.path.join(_SCRIPT_DIR, "espidf"),
                 os.path.join(os.path.dirname(_SCRIPT_DIR), "espidf")):
        if os.path.isfile(os.path.join(cand, "tools", "idf.py")):
            IDF_PATH = cand
            break
IDF_TOOLS_PATH = os.environ.get("IDF_TOOLS_PATH", "")
if not IDF_TOOLS_PATH:
    for cand in (os.path.join(_SCRIPT_DIR, "Espressif"),
                 os.path.join(os.path.dirname(_SCRIPT_DIR), "Espressif")):
        if os.path.isdir(cand):
            IDF_TOOLS_PATH = cand
            break
PROJECT_DIR = os.path.join(_SCRIPT_DIR, "xiaozhi-esp32")  # <repo>/scripts/xiaozhi-esp32
VENV_PY = os.path.join(IDF_TOOLS_PATH, "python_env", "idf5.5_py3.12_env", "Scripts", "python.exe")
VENV_PYTHON = VENV_PY if os.path.isfile(VENV_PY) else sys.executable
IDF_PY = os.path.join(IDF_PATH, "tools", "idf.py")
ROM_ELF_ROOT = os.path.join(IDF_TOOLS_PATH, "tools", "esp-rom-elfs")
ROM_ELF_VERSIONS = sorted(
    (os.path.join(ROM_ELF_ROOT, name) for name in os.listdir(ROM_ELF_ROOT)),
    reverse=True,
) if os.path.isdir(ROM_ELF_ROOT) else []
ROM_ELF_DIR = ROM_ELF_VERSIONS[0] if ROM_ELF_VERSIONS else ""


def _find_tool(subpath: str) -> str:
    """按 tools/<name> 目录动态查找工具路径（版本号由本机安装决定）。"""
    base = os.path.join(IDF_TOOLS_PATH, "tools", subpath)
    if os.path.isdir(base):
        return base
    for match in sorted(glob.glob(base + "-*"), reverse=True):
        if os.path.isdir(match):
            return match
    return ""


def _tool_bin(name: str, exe: str) -> str:
    """递归查找包含目标可执行文件的目录（工具版本目录布局各异：
    ninja 直接放版本目录，cmake 放 bin/，dfu-util 再嵌套一层 win64）。"""
    root = _find_tool(name)
    if not root:
        return ""
    for dirpath, dirnames, filenames in os.walk(root):
        if exe in filenames:
            return dirpath
    return ""

# Build a CLEAN environment — strip ALL MSys/MinGW/Cygwin/Git pollution
env = {}
skip_prefixes = ("MSYS", "MINGW", "MSYSTEM", "CYGWIN", "GIT_")
skip_keys = ("SHELL", "TERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION",
             "EXEPATH", "ORIGINAL_PATH", "PROMPT", "OLDPWD",
             "HOSTNAME", "HOME", "DISPLAY", "COLORTERM",
             "PKG_CONFIG_PATH", "ACLOCAL_PATH", "MANPATH",
             "INFOPATH", "XDG_", "DBUS_", "WSL_", "CONDA_")

for k, v in os.environ.items():
    should_skip = False
    for prefix in skip_prefixes:
        if k.startswith(prefix):
            should_skip = True
            break
    if k in skip_keys:
        should_skip = True
    if not should_skip:
        env[k] = v

# Clean PATH: only keep Windows system paths and ESP-IDF tools
clean_path_parts = []
for part in env.get("PATH", "").split(os.pathsep):
    part_lower = part.lower()
    # Skip MSys/MinGW/Cygwin/Git paths
    if any(x in part_lower for x in ("mingw", "msys", "cygwin", "\\git\\", "/git/")):
        continue
    if part == "" or part == ".":
        continue
    clean_path_parts.append(part)

# Add ESP-IDF toolchain paths (at front)，版本目录动态发现
idf_tool_paths = [
    _tool_bin("ninja", "ninja.exe"),
    _tool_bin("cmake", "cmake.exe"),
    _tool_bin("ccache", "ccache.exe"),
    _tool_bin("dfu-util", "dfu-util.exe"),
    _tool_bin("openocd-esp32", "openocd.exe"),
    _tool_bin("xtensa-esp-elf", "xtensa-esp32-elf-gcc.exe"),
    _tool_bin("riscv32-esp-elf", "riscv32-esp-elf-gcc.exe"),
    _tool_bin("esp32ulp-elf", "esp32ulp-elf-elf-gcc.exe"),
    ROM_ELF_DIR,
    # Python venv
    os.path.dirname(VENV_PYTHON),
]
# Add Windows system paths
sys_paths = [
    r"C:\Windows\System32",
    r"C:\Windows",
    r"C:\Windows\System32\Wbem",
    r"C:\Windows\System32\WindowsPowerShell\v1.0",
    r"C:\Windows\System32\OpenSSH",
]
clean_path_parts = [p for p in idf_tool_paths if os.path.isdir(p)] + sys_paths + clean_path_parts
env["PATH"] = os.pathsep.join(clean_path_parts)

# 禁用 cmd.exe AutoRun。当前用户注册表 AutoRun="cd /d E:\\x-tool"，
# CMake/Ninja 的 cmd.exe /C 链接步骤会因此切错 cwd，找不到刚生成的 .obj。
# /D 只对本构建进程生效，不修改用户的全局注册表配置。
env["COMSPEC"] = r"C:\Windows\System32\cmd.exe /D"

# ESP-IDF required vars
env["IDF_PATH"] = IDF_PATH
env["IDF_TOOLS_PATH"] = IDF_TOOLS_PATH
env["IDF_PYTHON_ENV_PATH"] = os.path.join(IDF_TOOLS_PATH, "python_env", "idf5.5_py3.12_env")
env["ESP_IDF_VERSION"] = "5.5.4"
if ROM_ELF_DIR:
    env["ESP_ROM_ELF_DIR"] = ROM_ELF_DIR

# sdkconfig 默认值链：sdkconfig.local（本地机密，不入库）存在时追加覆盖
_defaults = "sdkconfig.defaults;sdkconfig.defaults.esp32s3"
if os.path.exists(os.path.join(PROJECT_DIR, "sdkconfig.local")):
    _defaults += ";sdkconfig.local"
env["SDKCONFIG_DEFAULTS"] = _defaults

os.chdir(PROJECT_DIR)

def run(cmd, desc, timeout=600):
    print(f"\n=== {desc} ===", flush=True)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    if result.stdout:
        lines = result.stdout.strip().split("\n")
        for line in lines[-25:]:
            print(line)
    if result.stderr:
        for line in result.stderr.strip().split("\n")[-10:]:
            if line.strip():
                print(f"  [stderr] {line}")
    if result.returncode != 0:
        print(f"\nFAILED ({desc}): exit={result.returncode}")
        sys.exit(1)
    return result

# Step 1: configure。build.ninja 是 CMake 已完成配置的可靠标记；
# sdkconfig 位于项目根目录，不在 build/，旧检查会导致每次都重复 set-target。
build_ninja = os.path.join(PROJECT_DIR, "build", "build.ninja")
if not os.path.exists(build_ninja):
    run([VENV_PYTHON, IDF_PY, "set-target", "esp32s3"], "set-target")

# Step 2: build
run([VENV_PYTHON, IDF_PY, "build"], "build", timeout=600)

# Step 3: find binary
for root, dirs, files in os.walk(os.path.join(PROJECT_DIR, "build")):
    for f in files:
        if f.endswith(".bin"):
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            print(f"\n=== BINARY: {path} ({size} bytes) ===")

print("\n=== BUILD SUCCESS ===")

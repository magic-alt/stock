#!/bin/bash
# 生产环境启动脚本 (Linux/Mac)
#
# 用法:
#   ./start_production.sh
#   ./start_production.sh --mode paper
#   ./start_production.sh --config config.yaml

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查虚拟环境
if [ -f "venv/bin/activate" ]; then
    echo "[信息] 激活虚拟环境..."
    source venv/bin/activate
fi

# 检查依赖
if ! python3 -c "import pandas, numpy, backtrader" &> /dev/null; then
    echo "[警告] 缺少依赖包，正在安装..."
    pip install -r requirements.txt
fi

# 初始化目录
python3 -c "from src.core.defaults import ensure_directories; ensure_directories()" 2>/dev/null || true

# 运行启动脚本
echo "[信息] 启动生产环境..."
python3 scripts/start_production.py "$@"

exit $?

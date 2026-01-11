@echo off
REM 生产环境启动脚本 (Windows)
REM 
REM 用法:
REM   start_production.bat
REM   start_production.bat --mode paper
REM   start_production.bat --config config.yaml

setlocal enabledelayedexpansion

REM 设置项目根目录
set PROJECT_ROOT=%~dp0..
cd /d "%PROJECT_ROOT%"

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python环境，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [信息] 激活虚拟环境...
    call venv\Scripts\activate.bat
)

REM 检查依赖
python -c "import pandas, numpy, backtrader" >nul 2>&1
if errorlevel 1 (
    echo [警告] 缺少依赖包，正在安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

REM 初始化目录
python -c "from src.core.defaults import ensure_directories; ensure_directories()" 2>nul

REM 运行启动脚本
echo [信息] 启动生产环境...
python scripts\start_production.py %*

if errorlevel 1 (
    echo [错误] 启动失败
    pause
    exit /b 1
)

endlocal

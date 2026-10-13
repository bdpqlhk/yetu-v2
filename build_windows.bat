@echo off
rem 野兔 v2 Windows 打包脚本: 产物 dist\yetu-v2.exe (单文件)
rem 用法: 双击或在 cmd / PowerShell 里执行  build_windows.bat
rem 前置: 已安装 Python 3.8+ (勾选 Add to PATH)
setlocal
cd /d "%~dp0"

echo ^>^> 解释器:
python -c "import sys; print(sys.executable, sys.version.split()[0])" || goto :fail

rem 依赖: PyQt6 与 PyInstaller 必须装在"同一个 python"下
python -c "import PyQt6" 2>nul || (
  echo ^>^> 安装 PyQt6 ...
  python -m pip install PyQt6 || goto :fail
)
python -c "import PyInstaller" 2>nul || (
  echo ^>^> 安装 PyInstaller ...
  python -m pip install pyinstaller || goto :fail
)

echo ^>^> 打包 yetu-v2.exe ...
python -m PyInstaller yetu-v2.spec --noconfirm --clean || goto :fail

echo ^>^> 冒烟验证打包产物 ...
"dist\yetu-v2.exe" --smoke || goto :fail

echo.
echo [OK] 完成: dist\yetu-v2.exe
exit /b 0

:fail
echo [FAIL] 打包或验证失败, 请检查上方日志
echo        若 pip 安装慢, 可用清华镜像:
echo        python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
exit /b 1

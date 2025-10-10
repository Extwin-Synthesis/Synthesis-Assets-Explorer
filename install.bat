@echo off

:: 设置代码页为 UTF-8，支持中文显示
chcp 65001 >nul

set OMNIVERSE_PYTHON=

:: 启用延迟变量扩展
setlocal enabledelayedexpansion

echo.
echo ========================================
echo     正在运行 Omniverse 扩展安装脚本
echo ========================================
echo.
echo 尝试使用 Omniverse 自带的 Python 环境
echo.

:: 跳转到 install.bat 所在目录
cd /d "%~dp0"

set "CURRENT_DIR=%CD%"

:: 向上查找最多 10 层，寻找 Omniverse 根目录（包含 python.bat 和 apps\）
for /L %%i in (1,1,10) do (
    echo 正在检查目录: !CURRENT_DIR!

    if exist "!CURRENT_DIR!\python.bat" (
        if exist "!CURRENT_DIR!\apps\" (
            set "OMNIVERSE_PYTHON=!CURRENT_DIR!\python.bat"
            echo 找到 Omniverse 自带的 Python 环境:
            echo !OMNIVERSE_PYTHON!
            goto :run_install
        )
    )

    :: 向上一级目录
    for %%d in ("!CURRENT_DIR!\.") do set "CURRENT_DIR=%%~dpd"

    :: 清理末尾反斜杠
    if "!CURRENT_DIR:~-1!"=="\" set "CURRENT_DIR=!CURRENT_DIR:~0,-1!"

    :: 如果已经到根目录（如 C:\），停止查找
    for %%g in ("!CURRENT_DIR!") do if "%%~dpg"=="%%~pg" goto not_found
)

:not_found
endlocal
echo.
echo 错误：未找到 Omniverse 自带的 python.bat
echo 请确保此扩展(即包含install.bat/install.sh的文件夹)位于 Isaac Sim 或 Omniverse 的根目录。
echo 安装已终止。
goto pause

:run_install
echo.
echo ========================================
echo     正在执行 install.py
echo ========================================
echo 调试：将使用 Python 路径: "!OMNIVERSE_PYTHON!"

:: 真正执行
call "!OMNIVERSE_PYTHON!" "install.py" %*

:: 拷贝安装脚本的父级目录下的所有内容到与父级目录同级的extsUser目录下
set "FULL_PATH=%CD%"
set "FOLDER_NAME=%FULL_PATH%"

:: 去掉末尾的反斜杠（如果有）
if "%FOLDER_NAME:~-1%"=="\" set "FOLDER_NAME=%FOLDER_NAME:~0,-1%"

:: 提取最后一个反斜杠后的完整名称（包括 . 和 _）
for %%I in ("%FOLDER_NAME%") do set "EXT_NAME=%%~nxI"

echo 当前扩展名: !EXT_NAME!

:: 构建 extsUser 路径（与当前扩展目录同级）
set "EXTS_USER_DIR=!CURRENT_DIR!\extsUser"
set "DEST_DIR=!EXTS_USER_DIR!\!EXT_NAME!"

:: 创建 extsUser 目录（如果不存在）
if not exist "!EXTS_USER_DIR!" mkdir "!EXTS_USER_DIR!"

:: 删除旧版本（仅同名）
if exist "!DEST_DIR!" (
    echo.
    echo 正在删除旧版本: !EXT_NAME!
    rd /s /q "!DEST_DIR!"
    if exist "!DEST_DIR!" (
        echo 警告：无法删除旧版本，请检查是否被占用。
    ) else (
        echo 删除完成。
    )
)

:: 拷贝当前扩展目录到 extsUser
echo.
echo 正在安装新版本到: !DEST_DIR!
xcopy /e /i /y "%CD%" "!DEST_DIR!" >nul
if exist "!DEST_DIR!" (
    echo 安装成功：扩展已复制到 extsUser。
) else (
    echo 错误：拷贝失败！
)
endlocal

if %errorlevel% equ 0 (
    echo.
    echo 安装完成！
) else (
    echo.
    echo 安装失败，错误码: %errorlevel%
    echo 请检查上述错误信息。
)


:pause
echo.
echo ----------------------------------------
echo     按任意键退出...
echo ----------------------------------------
pause >nul
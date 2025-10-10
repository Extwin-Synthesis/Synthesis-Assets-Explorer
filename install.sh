#!/bin/bash

# 设置 UTF-8 编码（支持中文）
export LANG="zh_CN.UTF-8"

# 初始化变量
OMNIVERSE_PYTHON=""
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$CURRENT_DIR"

echo ""
echo "========================================"
echo "    正在运行 Omniverse 扩展安装脚本"
echo "========================================"
echo ""
echo "尝试使用 Omniverse 自带的 Python 环境"
echo ""

# 向上查找最多 10 层，寻找根目录（包含 python 和 apps/）
for ((i=1; i<=10; i++)); do
    echo "正在检查目录: $ROOT_DIR"

    if [[ -f "$ROOT_DIR/python" && -d "$ROOT_DIR/apps" ]]; then
        OMNIVERSE_PYTHON="$ROOT_DIR/python"
        echo "找到 Omniverse 自带的 Python 环境:"
        echo "$OMNIVERSE_PYTHON"
        break
    fi

    # 向上一级
    NEW_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
    if [[ "$NEW_ROOT" == "$ROOT_DIR" ]]; then
        # 已到达根目录（如 / 或 /home）
        break
    fi
    ROOT_DIR="$NEW_ROOT"
done

# 检查是否找到
if [[ -z "$OMNIVERSE_PYTHON" ]]; then
    echo ""
    echo "错误：未找到 Omniverse 自带的 python"
    echo "请确保此扩展（即包含 install.sh/install.bat 的文件夹）位于 Isaac Sim 或 Omniverse 的根目录。"
    echo "安装已终止。"
    read -n1 -r -s -p "按任意键退出..."
    exit 1
fi

echo ""
echo "========================================"
echo "    正在执行 install.py"
echo "========================================"
echo "调试：将使用 Python 路径: $OMNIVERSE_PYTHON"

# 执行 install.py（传递所有参数）
"$OMNIVERSE_PYTHON" "install.py" "$@"

# 获取当前扩展文件夹名（完整名称，包含 . 和 _）
EXT_NAME="$(basename "$CURRENT_DIR")"

echo "当前扩展名: $EXT_NAME"

# 构建 extsUser 路径
EXTS_USER_DIR="$ROOT_DIR/extsUser"
DEST_DIR="$EXTS_USER_DIR/$EXT_NAME"

# 创建 extsUser 目录（如果不存在）
mkdir -p "$EXTS_USER_DIR"

# 删除旧版本（仅同名）
if [[ -d "$DEST_DIR" ]]; then
    echo ""
    echo "正在删除旧版本: $EXT_NAME"
    rm -rf "$DEST_DIR"
    if [[ -d "$DEST_DIR" ]]; then
        echo "警告：无法删除旧版本，请检查权限或是否被占用。"
    else
        echo "删除完成。"
    fi
fi

# 拷贝当前扩展目录到 extsUser
echo ""
echo "正在安装新版本到: $DEST_DIR"
cp -r "$CURRENT_DIR" "$DEST_DIR"

# 验证拷贝结果
if [[ -d "$DEST_DIR" ]]; then
    echo "安装成功：扩展已复制到 extsUser。"
else
    echo "错误：拷贝失败！"
fi

# 检查 install.py 的执行结果
if [[ $? -eq 0 ]]; then
    echo ""
    echo "安装完成！"
else
    echo ""
    echo "安装失败，错误码: $?"
    echo "请检查上述错误信息。"
fi

echo ""
echo "----------------------------------------"
echo "    按回车键退出..."
echo "----------------------------------------"
read
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Omniverse 扩展一键安装脚本（优化版）

功能：
1. 检测操作系统
2. 安装 requirements.txt 依赖
3. 在 .kit 文件 [dependencies] 段末尾添加新依赖（智能去重，忽略版本）
4. 自动备份原文件
5. 支持自定义 .kit 文件路径
"""

import os
import sys
import subprocess
import platform
import re
import shutil
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Omniverse 扩展安装脚本")
    parser.add_argument("--kit", help="指定 .kit 配置文件路径")
    parser.add_argument("--ext", help="要添加的扩展名，如 extwin.synthesis_explorer")
    parser.add_argument(
        "--requirements", default="requirements.txt", help="依赖文件路径"
    )
    return parser.parse_args()


def find_omniverse_root(start_path):
    current = start_path
    for _ in range(10):
        apps_dir = os.path.join(current, "apps")
        if os.path.isdir(apps_dir):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise FileNotFoundError("无法找到 Omniverse 根目录（未发现 'apps' 目录）")


def detect_platform():
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "macos"
    else:
        raise OSError(f"不支持的操作系统: {system}")


def install_dependencies():
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"未找到 '{REQUIREMENTS_FILE}'，跳过用户依赖安装。")
        return

    print("正在安装用户依赖...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE]
        )
        print("用户依赖安装成功！")
    except subprocess.CalledProcessError as e:
        print(f"用户依赖安装失败！错误: {e}")
        sys.exit(1)


def modify_kit_file():
    print(f"正在修改 .kit 文件: {KIT_FILE}")

    try:
        with open(KIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 创建备份
        backup_path = KIT_FILE + ".backup"
        if not os.path.exists(backup_path):
            shutil.copy(KIT_FILE, backup_path)
            print(f"已创建备份: {backup_path}")

        dependencies_start = -1
        insert_index = -1  # 实际插入位置（最后一个有效行之后）
        in_dependencies = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped == "[dependencies]":
                dependencies_start = i
                in_dependencies = True
                insert_index = i + 1  # 默认插入到段开始后
                continue

            if in_dependencies:
                # 遇到下一个段，结束 dependencies 段
                if (
                    stripped.startswith("[")
                    and stripped.endswith("]")
                    and stripped != "[dependencies]"
                ):
                    break

                # 跳过注释和空行
                if stripped and not stripped.startswith("#"):
                    # 检查是否已包含该扩展（忽略引号和版本）
                    if re.search(rf'["\']?{re.escape(NEW_DEPENDENCY_KEY)}["\']?', line):
                        print(
                            f"[dependencies] 中已存在 {NEW_DEPENDENCY_KEY}，无需添加。"
                        )
                        return

                # 更新插入位置为当前行之后（保证插入到最后一个非空/非注释行之后）
                if stripped:
                    insert_index = i + 1

        if dependencies_start == -1:
            print(f"错误: 未找到 [dependencies] 段")
            sys.exit(1)

        # 插入新依赖
        new_line = f'"{NEW_DEPENDENCY_KEY}" = {{}}\n'
        lines.insert(insert_index, new_line)

        with open(KIT_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"已在 [dependencies] 添加: {NEW_DEPENDENCY_KEY}")
        print(f"文件已更新: {KIT_FILE}")

    except Exception as e:
        print(f"修改文件失败: {e}")
        sys.exit(1)


# ------------------ 配置 ------------------
args = parse_args()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS_FILE = os.path.join(SCRIPT_DIR, args.requirements)

# .kit 文件路径（优先使用参数，否则自动查找）
KIT_FILE = args.kit
if not KIT_FILE:
    try:
        OMNIVERSE_ROOT = find_omniverse_root(SCRIPT_DIR)
        # 尝试多个常见 .kit 文件
        possible_kits = [
            "apps/isaacsim.exp.full.streaming.kit",
        ]
        for rel_path in possible_kits:
            candidate = os.path.join(OMNIVERSE_ROOT, rel_path)
            if os.path.isfile(candidate):
                KIT_FILE = candidate
                print(f"自动发现 .kit 文件: {KIT_FILE}")
                break
        if not KIT_FILE:
            raise FileNotFoundError("未找到任何可用的 .kit 文件")
    except Exception as e:
        print(f"自动查找 .kit 文件失败: {e}")
        sys.exit(1)
else:
    KIT_FILE = os.path.abspath(KIT_FILE)
    if not os.path.isfile(KIT_FILE):
        print(f"错误: 指定的 .kit 文件不存在: {KIT_FILE}")
        sys.exit(1)

# 扩展名
NEW_DEPENDENCY_KEY = args.ext or "extwin.synthesis_explorer"

# ------------------------------------------


def main():
    print("开始 Omniverse 扩展安装...")
    platform_name = detect_platform()
    print(f"平台: {platform_name}")
    print(f"脚本路径: {SCRIPT_DIR}")

    install_dependencies()
    modify_kit_file()

    print("\n安装完成！请启动 Omniverse 应用。")


if __name__ == "__main__":
    main()

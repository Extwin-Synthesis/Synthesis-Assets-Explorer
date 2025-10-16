#!/usr/bin/env python3
# Isaac Sim Extension Installer
# Cross-platform: Windows, Linux, macOS

import sys
import shutil
import subprocess
import platform
from pathlib import Path


def find_isaac_sim_root():
    """Find Isaac Sim root directory (must contain 'apps' and 'python.bat' or 'python.sh')"""
    current_dir = Path(__file__).parent.resolve()

    # Traverse upward from current directory
    for parent in [current_dir] + list(current_dir.parents):
        python_exe = None
        if (parent / "python.bat").exists():
            python_exe = parent / "python.bat"
        elif (parent / "python.sh").exists():
            python_exe = parent / "python.sh"

        if python_exe and (parent / "apps").exists():
            return parent, python_exe

    raise RuntimeError(
        "Failed to locate Isaac Sim root directory.\n"
        "Please ensure this script is located in the extension directory.\n"
        "The Isaac Sim root directory must contain the 'apps' folder and 'python.bat' or 'python.sh'."
    )


def install_dependencies(requirements_file):
    """Install dependencies using Isaac Sim's built-in Python"""
    if not requirements_file.exists():
        print("No requirements.txt found. Skipping dependency installation.")
        return

    print(f"Installing Python dependencies from: {requirements_file}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        )
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        raise


def modify_kit_file(kit_path):
    """Modify .kit file (TOML format) and preserve original formatting"""
    try:
        import tomlkit
    except ImportError:
        print("tomlkit not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tomlkit"])
        import tomlkit

    if not kit_path.exists():
        print(f"Config file not found, skipping: {kit_path}")
        return

    print(f"Modifying: {kit_path.name}")

    try:
        with open(kit_path, "r", encoding="utf-8") as f:
            content = f.read()
            doc = tomlkit.parse(content)

        modified = False

        # 1. [dependencies]
        if "dependencies" not in doc:
            doc["dependencies"] = tomlkit.table()
            print("  Created [dependencies]")

        deps = doc["dependencies"]
        ext_name = "extwin.synthesis_explorer"
        if ext_name not in deps:
            deps[ext_name] = tomlkit.inline_table()
            print(f"  Added dependency: {ext_name}")
            modified = True
        else:
            print(f"  Dependency already exists: {ext_name}")

        # # 2. [settings.app.exts.folders] '++'
        # try:
        #     node = doc
        #     for key in ["settings", "app", "exts", "folders"]:
        #         if key not in node:
        #             node[key] = tomlkit.table()
        #         node = node[key]

        #     if "++" not in node:
        #         node["++"] = tomlkit.array()
        #         node["++"].append("${app}/../extwin")
        #         print("  Created '++' and added '${app}/../extwin'")
        #         modified = True
        #     elif "${app}/../extwin" not in node["++"]:
        #         node["++"].append("${app}/../extwin")
        #         print("  Added to '++': ${app}/../extwin")
        #         modified = True
        #     else:
        #         print("  '${app}/../extwin' already in '++'")
        # except Exception as e:
        #     print(f"Warning: Failed to update exts.folders: {e}")

        # 3. Save with backup
        if modified:
            backup = kit_path.with_suffix(kit_path.suffix + ".bak")
            if not backup.exists():
                shutil.copy2(kit_path, backup)
                print(f"  Backup saved: {backup.name}")
            with open(kit_path, "w", encoding="utf-8") as f:
                f.write(tomlkit.dumps(doc))
            print(f"  Updated: {kit_path.name}")
        else:
            print(f"  No changes needed: {kit_path.name}")

    except Exception as e:
        print(f"Error modifying {kit_path}: {e}")
        raise


def copy_extension(extension_dir, isaac_root):
    """Copy extension to extsUser/<extension_name>, ignoring hidden files"""
    extwin_dir = isaac_root / "extsUser"
    target_dir = extwin_dir / extension_dir.name

    # Remove existing version
    if target_dir.exists():
        print(f"Removing existing extension: {target_dir}")
        shutil.rmtree(target_dir)

    extwin_dir.mkdir(exist_ok=True)

    def ignore_hidden(directory, filenames):
        # Ignore files and directories starting with '.'
        return [f for f in filenames if f.startswith(".")]

    print(f"Copying extension to: {target_dir}")
    shutil.copytree(extension_dir, target_dir, ignore=ignore_hidden)
    print("Extension copied successfully.")


def main():
    print("=" * 60)
    print("       Isaac Sim Extension Installer")
    print("       Supports: Windows, Linux, macOS")
    print("=" * 60)

    try:
        # 1. Find Isaac Sim root
        isaac_root, _ = find_isaac_sim_root()
        print(f"Isaac Sim root directory: {isaac_root}")

        # 2. Get extension directory
        extension_dir = Path(__file__).parent.resolve()
        print(f"Extension directory: {extension_dir}")

        # 3. Install dependencies
        req_file = extension_dir / "requirements.txt"
        install_dependencies(req_file)

        # 4. Modify .kit files
        apps_dir = isaac_root / "apps"
        kit_files = list(apps_dir.glob("isaacsim.exp.base.kit"))
        if not kit_files:
            print(f"No .kit files found in: {apps_dir}")
        else:
            for kit_file in kit_files:
                modify_kit_file(kit_file)

        # 5. Copy extension
        copy_extension(extension_dir, isaac_root)

        # 6. Check xclip on Linux
        if platform.system() == "Linux":
            if shutil.which("xclip") is None:
                print("\n" + "="*60)
                print("WARNING: 'xclip' utility not found")
                print("="*60)
                print("The 'xclip' tool is required for full clipboard functionality in Isaac Sim,")
                print("such as copying text from the UI or external applications.")
                print("\nWithout it, clipboard operations may not work correctly.")
                print("\nPlease install 'xclip' using your distribution's package manager:")
                print("  • Ubuntu/Debian: sudo apt update && sudo apt install xclip")
                print("  • CentOS/RHEL/Fedora: sudo yum install xclip   OR   sudo dnf install xclip")
                print("  • openSUSE: sudo zypper install xclip")
                print("  • Arch Linux: sudo pacman -S xclip")
                print("\nTip: After installation, verify with: 'xclip -version'")
                print("="*60 + "\n")

        print("\nInstallation completed successfully!")
        print("\nPlease open the extension window, search for the extwin.synthesis_explorer extension, and enable it.")
        print("\nBackup files have been created for modified .kit files (.kit.bak)")

    except Exception as e:
        print(f"\nInstallation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

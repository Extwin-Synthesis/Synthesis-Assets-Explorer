#!/bin/bash
# Isaac Sim Extension Installer (Linux/macOS)
# Uses built-in python.sh

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to script directory
cd "$SCRIPT_DIR" || exit 1

# Locate python.sh in parent directory
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -f "$ROOT_DIR/python.sh" ]; then
    PYTHON_EXE="$ROOT_DIR/python.sh"
else
    echo "Error: python.sh not found. Ensure this extension is in  Isaac Sim root directory."
    exit 1
fi

# Check for install.py
if [ ! -f "install.py" ]; then
    echo "Error: install.py not found."
    exit 1
fi

echo "Using $PYTHON_EXE to install extension..."
"$PYTHON_EXE" "install.py"

if [ $? -ne 0 ]; then
    echo "Installation failed."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Installation completed."
read -p "Press Enter to exit..."
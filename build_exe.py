import subprocess
import sys
from pathlib import Path

def run_command(command):
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def main():
    print("Starting build process for BSN Redactor executable...")

    # 1. Install dependencies
    print("Installing dependencies...")
    run_command([sys.executable, "-m", "pip", "install", "pyinstaller", "pyqt6", "pymupdf"])

    # 2. Build the executable
    # --onefile: Bundle everything into a single executable
    # --noconsole: Hide the console window when the app starts (since it's a GUI)
    # --name: The name of the resulting executable
    # --windowed: Necessary for macOS to create a proper .app bundle
    print("Building executable with PyInstaller...")
    build_command = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--noconsole",
        "--name", "BSN_Redactor",
        "gui.py"
    ]
    run_command(build_command)

    print("\n" + "="*30)
    print("BUILD SUCCESSFUL!")
    print("="*30)
    print("The executable is located in the 'dist' folder: dist/BSN_Redactor")
    print("You can send this file to the user.")
    print("="*30)

if __name__ == "__main__":
    main()

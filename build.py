"""Compila PyGate come .exe con Nuitka.

Uso:
    python build.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "app")
ENTRY = os.path.join(ROOT, "pygate.py")
OUTPUT = os.path.join(ROOT, "dist")


def main():
    try:
        subprocess.run([sys.executable, "-m", "nuitka", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Nuitka non installato. pip install nuitka")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT}",
        "--output-filename=pygate.exe",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        "--remove-output",
        f"--include-data-dir={os.path.join(APP, 'locale')}=locale",
        f"--include-data-dir={os.path.join(APP, 'shared')}=shared",
        f"--include-data-files={os.path.join(ROOT, 'pygate.png')}=pygate.png",
        f"--windows-icon-from-ico={os.path.join(ROOT, 'pygate.ico')}",
        ENTRY,
    ]

    print("Building PyGate...\n")
    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode == 0:
        exe = os.path.join(OUTPUT, "pygate.exe")
        if os.path.exists(exe):
            size = os.path.getsize(exe) / (1024 * 1024)
            print(f"\n[OK] pygate.exe ({size:.1f} MB) -> {exe}")
    else:
        print("\n[ERRORE] Build fallita")
        sys.exit(1)


if __name__ == "__main__":
    main()

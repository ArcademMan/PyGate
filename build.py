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

    # Aggiungi app/ al PYTHONPATH cosi' Nuitka trova i package
    env = os.environ.copy()
    env["PYTHONPATH"] = APP + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        f"--output-dir={OUTPUT}",
        "--output-filename=pygate.exe",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        "--remove-output",
        # Includi i package Python da app/
        "--include-package=shared",
        "--include-package=shared.widgets",
        "--include-package=core",
        "--include-package=gui",
        "--include-package=cli",
        # Dati extra (locale, icona)
        f"--include-data-dir={os.path.join(APP, 'locale')}=locale",
        f"--include-data-dir={os.path.join(APP, 'shared', 'locale')}=shared/locale",
        f"--include-data-files={os.path.join(ROOT, 'pygate.png')}=pygate.png",
        f"--windows-icon-from-ico={os.path.join(ROOT, 'pygate.ico')}",
        ENTRY,
    ]

    print("Building PyGate...\n")
    result = subprocess.run(cmd, cwd=ROOT, env=env)

    if result.returncode != 0:
        print("\n[ERRORE] Build fallita")
        sys.exit(1)

    exe_dir = os.path.join(OUTPUT, "pygate.dist")
    exe = os.path.join(exe_dir, "pygate.exe")
    if not os.path.exists(exe):
        print("\n[ERRORE] pygate.exe non trovato")
        sys.exit(1)

    size = os.path.getsize(exe) / (1024 * 1024)
    print(f"\n[OK] pygate.exe ({size:.1f} MB)")

    # Zip per la release
    import shutil
    zip_path = os.path.join(OUTPUT, "PyGate-win64")
    if os.path.exists(zip_path + ".zip"):
        os.remove(zip_path + ".zip")
    shutil.make_archive(zip_path, "zip", OUTPUT, "pygate.dist")
    zip_size = os.path.getsize(zip_path + ".zip") / (1024 * 1024)
    print(f"[OK] PyGate-win64.zip ({zip_size:.1f} MB) -> {zip_path}.zip")


if __name__ == "__main__":
    main()

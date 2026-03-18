"""PyGate — Runner principale."""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.join(_ROOT, "app")

# Aggiungi la cartella app/ al path
if os.path.isdir(_APP):
    sys.path.insert(0, _APP)

from shared.i18n import register_locale_dir

# Registra locale: cerca in app/locale (dev) o locale/ (compilato)
for candidate in [os.path.join(_APP, "locale"), os.path.join(_ROOT, "locale")]:
    if os.path.isdir(candidate):
        register_locale_dir("pygate", candidate)
        break


def main():
    from gui.app import launch
    launch()


if __name__ == "__main__":
    main()

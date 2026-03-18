"""PyGate — Runner principale."""

import os
import sys

# Aggiungi la cartella app/ al path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from shared.i18n import register_locale_dir

register_locale_dir("pygate", os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "locale"))


def main():
    from gui.app import launch
    launch()


if __name__ == "__main__":
    main()

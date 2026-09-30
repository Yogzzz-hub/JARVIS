"""Bundled UI fonts (SIL Open Font License, see jarvis/ui/qml/fonts): Orbitron for titles, Rajdhani for text."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("jarvis.ui.fonts")
FONT_DIR = Path(__file__).parent / "qml" / "fonts"
DISPLAY = "Orbitron"
TEXT = "Rajdhani"


def load_fonts(app=None) -> list[str]:
    """Register the fonts and make Rajdhani the default, so every page shares one typeface (Tamil and emoji fall
    back to the system fonts automatically). Returns the families loaded."""
    from PySide6.QtGui import QFont, QFontDatabase
    families: list[str] = []
    for f in sorted(FONT_DIR.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid < 0:
            logger.debug("Could not load font %s", f.name)
            continue
        families += QFontDatabase.applicationFontFamilies(fid)
    if app is not None and TEXT in families:
        font = QFont(TEXT)
        font.setPixelSize(15)
        font.setHintingPreference(QFont.PreferNoHinting)
        app.setFont(font)
    return sorted(set(families))

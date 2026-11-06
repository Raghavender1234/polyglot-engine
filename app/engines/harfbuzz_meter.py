from pathlib import Path
from typing import Dict, Tuple
import uharfbuzz as hb
from fontTools.ttLib import TTFont

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

class HarfBuzzMeter:
    def __init__(self, fonts_dir: Path = FONTS_DIR):
        self.fonts_dir = fonts_dir
        self._font_cache: Dict[str, Tuple[hb.Font, int]] = {}
        self._preload_fonts()

    def _preload_fonts(self):
        font_files = {
            "inter": self.fonts_dir / "Inter-Regular.ttf",
            "arabic": self.fonts_dir / "NotoSansArabic-Regular.ttf",
            "urdu": self.fonts_dir / "NotoNastaliqUrdu-Regular.ttf",
            "jp": self.fonts_dir / "NotoSansJP-Regular.ttf",
        }
        for key, path in font_files.items():
            if path.exists():
                blob = hb.Blob.from_file_path(str(path))
                face = hb.Face(blob)
                font = hb.Font(face)
                upem = face.upem
                self._font_cache[key] = (font, upem)

    def resolve_font_key(self, locale: str) -> str:
        loc = locale.lower().replace("_", "-")
        if loc.startswith("ur"):
            return "urdu"
        elif loc.startswith("ar") or loc.startswith("fa") or loc.startswith("ps"):
            return "arabic"
        elif loc.startswith("ja"):
            return "jp"
        return "inter"

    def measure_text(self, text: str, locale: str, font_size_px: float = 14.0, font_weight: int = 400) -> Tuple[float, str]:
        """
        Measures exact advance width in pixels using HarfBuzz C-engine.
        Returns (measured_width_px, font_name_used).
        """
        font_key = self.resolve_font_key(locale)
        if font_key not in self._font_cache:
            self._preload_fonts()

        if font_key in self._font_cache:
            font, upem = self._font_cache[font_key]
        else:
            # Fallback to whatever is available
            font, upem = next(iter(self._font_cache.values()))

        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()

        # Explicit direction override if needed
        loc = locale.lower()
        if loc.startswith(("ur", "ar", "he", "fa")):
            buf.direction = "rtl"
        else:
            buf.direction = "ltr"

        hb.shape(font, buf)
        total_advance = sum(pos.x_advance for pos in buf.glyph_positions)
        pixel_width = (total_advance / upem) * font_size_px

        # If font_weight >= 600 and we are using a variable or regular font,
        # bold glyphs add ~5-8% width unless bold file is separately shaped.
        if font_weight >= 600 and font_key == "inter":
            pixel_width *= 1.05

        return round(pixel_width, 2), font_key

harfbuzz_engine = HarfBuzzMeter()

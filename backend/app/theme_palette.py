from __future__ import annotations

from reportlab.lib import colors


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.replace("#", "")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(red: float, green: float, blue: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, round(red))),
        max(0, min(255, round(green))),
        max(0, min(255, round(blue))),
    )


def mix_hex(base_hex: str, mix_hex_color: str, amount: float) -> str:
    base_red, base_green, base_blue = _hex_to_rgb(base_hex)
    mix_red, mix_green, mix_blue = _hex_to_rgb(mix_hex_color)
    ratio = max(0.0, min(1.0, amount))

    return _rgb_to_hex(
        base_red + ((mix_red - base_red) * ratio),
        base_green + ((mix_green - base_green) * ratio),
        base_blue + ((mix_blue - base_blue) * ratio),
    )


def build_theme_palette(theme_color: str) -> dict[str, colors.Color]:
    accent = theme_color.lower()
    return {
        "accent": colors.HexColor(accent),
        "accent_deep": colors.HexColor(mix_hex(accent, "#000000", 0.18)),
        "accent_ink": colors.HexColor(mix_hex(accent, "#000000", 0.30)),
        "accent_soft": colors.HexColor(mix_hex(accent, "#ffffff", 0.88)),
        "accent_surface": colors.HexColor(mix_hex(accent, "#ffffff", 0.94)),
        "accent_surface_strong": colors.HexColor(mix_hex(accent, "#ffffff", 0.90)),
        "accent_line": colors.HexColor(mix_hex(accent, "#ffffff", 0.76)),
        "accent_border": colors.HexColor(mix_hex(accent, "#ffffff", 0.82)),
    }

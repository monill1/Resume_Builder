function hexToRgb(hexColor) {
  const value = String(hexColor || "").replace("#", "");
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function rgbToHex({ r, g, b }) {
  const toHex = (channel) => Math.max(0, Math.min(255, Math.round(channel))).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function mixHex(baseHex, mixHexColor, amount) {
  const base = hexToRgb(baseHex);
  const mix = hexToRgb(mixHexColor);
  const ratio = Math.max(0, Math.min(1, amount));

  return rgbToHex({
    r: base.r + (mix.r - base.r) * ratio,
    g: base.g + (mix.g - base.g) * ratio,
    b: base.b + (mix.b - base.b) * ratio,
  });
}

export function buildThemePalette(themeColor) {
  const accent = String(themeColor || "#1c5fdb").toLowerCase();

  return {
    accent,
    accentDeep: mixHex(accent, "#000000", 0.18),
    accentInk: mixHex(accent, "#000000", 0.3),
    accentSoft: mixHex(accent, "#ffffff", 0.88),
    accentSurface: mixHex(accent, "#ffffff", 0.94),
    accentSurfaceStrong: mixHex(accent, "#ffffff", 0.9),
    accentLine: mixHex(accent, "#ffffff", 0.76),
    accentBorder: mixHex(accent, "#ffffff", 0.82),
  };
}

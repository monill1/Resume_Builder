from __future__ import annotations

import re
from html import escape


BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def strip_rich_text(text: str | None) -> str:
    return BOLD_PATTERN.sub(lambda match: match.group(1), text or "")


def resolve_bold_font_name(font_name: str | None) -> str:
    base_name = (font_name or "").strip()
    if not base_name:
        return "Helvetica-Bold"
    if base_name.endswith("-Bold"):
        return base_name
    if base_name.endswith("-Italic"):
        return f"{base_name[:-7]}-BoldItalic"
    if base_name.endswith("-Oblique"):
        return f"{base_name[:-8]}-BoldOblique"
    if base_name == "Times-Roman":
        return "Times-Bold"
    return f"{base_name}-Bold"


def to_reportlab_markup(text: str | None, *, bold_font_name: str | None = None) -> str:
    source = text or ""
    parts: list[str] = []
    last_index = 0
    resolved_bold_font = escape(resolve_bold_font_name(bold_font_name))

    for match in BOLD_PATTERN.finditer(source):
        start, end = match.span()
        if start > last_index:
            parts.append(escape(source[last_index:start]))

        inner_text = escape(match.group(1))
        parts.append(f"<font name='{resolved_bold_font}'>{inner_text}</font>" if inner_text.strip() else escape(match.group(0)))
        last_index = end

    if last_index < len(source):
        parts.append(escape(source[last_index:]))

    markup = "".join(parts) if parts else escape(source)
    return markup.replace("\n", "<br/>")

from __future__ import annotations

from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    FrameBreak,
    Flowable,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from PIL import Image

from .models import ResumePayload
from .rich_text import to_reportlab_markup
from .theme_palette import build_theme_palette


ROOT_DIR = Path(__file__).resolve().parents[2]
ICON_ASSET_PATHS = {
    "phone": ROOT_DIR / "contact-logo-clean.png",
    "mail": ROOT_DIR / "email-logo-clean.png",
    "linkedin": ROOT_DIR / "linkedin-logo-clean.png",
    "github": ROOT_DIR / "github-logo-clean.png",
    "location": ROOT_DIR / "location-logo-clean.png",
}

TEXT = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
LIGHT_RULE = colors.HexColor("#E2E8F0")
DEFAULT_SECTION_ORDER = ["summary", "skills", "experience", "projects", "education", "certifications"]


def _hex(color: colors.Color) -> str:
    return f"#{color.hexval()[2:]}"


def _normalized_section_order(section_order: list[str] | None) -> list[str]:
    safe_order = section_order or []
    unique_known = [key for index, key in enumerate(safe_order) if key in DEFAULT_SECTION_ORDER and safe_order.index(key) == index]
    missing = [key for key in DEFAULT_SECTION_ORDER if key not in unique_known]
    return [*unique_known, *missing]


def _safe_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]


def _normalize_inline_paragraph_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@lru_cache(maxsize=16)
def _icon_image(kind: str) -> ImageReader | None:
    asset_path = ICON_ASSET_PATHS.get(kind)
    if not asset_path or not asset_path.exists():
        return None
    image = Image.open(asset_path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        image = image.crop(bbox)
    return ImageReader(image)


class ContactLineFlowable(Flowable):
    def __init__(self, resume: ResumePayload, width: float, accent: colors.Color, align: str = "left") -> None:
        super().__init__()
        self.resume = resume
        self.max_width = width
        self.accent = accent
        self.align = align
        self.font_name = "Helvetica"
        self.font_size = 9.0
        self.icon_size = 10.2
        self.gap = 4.2
        self.separator = "|"
        self.separator_padding = 6.0
        self.height = 14
        self._segments: list[dict] = []

    def _build_segments(self) -> list[dict]:
        basics = self.resume.basics
        segments = [
            {"kind": "phone", "label": basics.phone, "url": f"tel:{basics.phone.replace(' ', '')}", "color": TEXT},
            {"kind": "mail", "label": basics.email, "url": f"mailto:{basics.email}", "color": TEXT},
            {"kind": "location", "label": basics.location, "url": None, "color": TEXT},
        ]
        if basics.linkedin:
            segments.append({"kind": "linkedin", "label": "LinkedIn", "url": str(basics.linkedin), "color": self.accent})
        if basics.github:
            segments.append({"kind": "github", "label": "GitHub", "url": str(basics.github), "color": self.accent})
        if basics.website:
            segments.append({"kind": "website", "label": "Portfolio", "url": str(basics.website), "color": self.accent})
        return segments

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self._segments = self._build_segments()
        self.width = min(avail_width, self.max_width)
        self.height = 14
        return self.width, self.height

    def _segment_width(self, segment: dict) -> float:
        label_width = pdfmetrics.stringWidth(segment["label"], self.font_name, self.font_size)
        icon_width = self.icon_size + self.gap
        return icon_width + label_width

    def _separator_width(self) -> float:
        return pdfmetrics.stringWidth(self.separator, self.font_name, self.font_size) + (self.separator_padding * 2)

    def _draw_phone(self, x: float, y: float) -> None:
        icon = _icon_image("phone")
        if icon is not None:
            self.canv.drawImage(icon, x - 0.05, y - 1.35, width=10.4, height=10.4, mask="auto")

    def _draw_mail(self, x: float, y: float) -> None:
        icon = _icon_image("mail")
        if icon is not None:
            self.canv.drawImage(
                icon,
                x + 0.05,
                y - 1.32,
                width=10.0,
                height=10.0,
                mask="auto",
                preserveAspectRatio=True,
                anchor="c",
            )

    def _draw_location(self, x: float, y: float) -> None:
        icon = _icon_image("location")
        if icon is not None:
            self.canv.drawImage(icon, x + 0.2, y - 1.08, width=9.2, height=9.2, mask="auto")

    def _draw_linkedin(self, x: float, y: float) -> None:
        icon = _icon_image("linkedin")
        if icon is not None:
            self.canv.drawImage(icon, x + 0.2, y - 0.52, width=8.75, height=8.75, mask="auto")

    def _draw_github(self, x: float, y: float) -> None:
        icon = _icon_image("github")
        if icon is not None:
            self.canv.drawImage(icon, x + 0.02, y - 1.02, width=10.1, height=10.1, mask="auto")

    def _draw_website(self, x: float, y: float) -> None:
        canv = self.canv
        canv.setStrokeColor(self.accent)
        canv.setLineWidth(0.95)
        canv.circle(x + 5.0, y + 5.0, 4.0, fill=0, stroke=1)
        canv.line(x + 1.7, y + 5.0, x + 8.3, y + 5.0)
        canv.line(x + 5.0, y + 1.7, x + 5.0, y + 8.3)

    def _draw_icon(self, kind: str, x: float, y: float) -> None:
        if kind == "phone":
            self._draw_phone(x, y)
        elif kind == "mail":
            self._draw_mail(x, y)
        elif kind == "location":
            self._draw_location(x, y)
        elif kind == "linkedin":
            self._draw_linkedin(x, y)
        elif kind == "github":
            self._draw_github(x, y)
        elif kind == "website":
            self._draw_website(x, y)

    def draw(self) -> None:
        canv = self.canv
        total_width = 0.0
        widths = []
        for segment in self._segments:
            width = self._segment_width(segment)
            widths.append(width)
            total_width += width
        separator_width = self._separator_width()
        total_width += separator_width * max(0, len(self._segments) - 1)

        x = 0 if self.align == "left" else max(0, (self.width - total_width) / 2)
        y = 1.55

        for index, segment in enumerate(self._segments):
            if index > 0:
                canv.setFillColor(colors.HexColor("#7F8DB2"))
                canv.setFont(self.font_name, self.font_size)
                canv.drawString(x + self.separator_padding, y + 0.15, self.separator)
                x += separator_width

            icon_x = x
            self._draw_icon(segment["kind"], icon_x, y)
            text_x = icon_x + self.icon_size + self.gap
            canv.setFillColor(segment["color"])
            canv.setFont(self.font_name, self.font_size)
            canv.drawString(text_x, y, segment["label"])

            if segment["url"]:
                label_width = pdfmetrics.stringWidth(segment["label"], self.font_name, self.font_size)
                canv.linkURL(segment["url"], (icon_x, y - 1, text_x + label_width, y + 10), relative=1)

            x += widths[index]


class ContactStackFlowable(Flowable):
    def __init__(self, resume: ResumePayload, width: float, accent: colors.Color) -> None:
        super().__init__()
        self.resume = resume
        self.max_width = width
        self.accent = accent
        self.font_name = "Helvetica"
        self.font_size = 8.45
        self.icon_size = 9.4
        self.gap = 5.0
        self.row_gap = 3.6
        self.row_height = 12.4
        self._segments: list[dict] = []

    def _build_segments(self) -> list[dict]:
        basics = self.resume.basics
        segments = [
            {"kind": "phone", "label": basics.phone, "url": f"tel:{basics.phone.replace(' ', '')}", "color": TEXT},
            {"kind": "mail", "label": basics.email, "url": f"mailto:{basics.email}", "color": TEXT},
            {"kind": "location", "label": basics.location, "url": None, "color": TEXT},
        ]
        if basics.linkedin:
            segments.append({"kind": "linkedin", "label": "LinkedIn", "url": str(basics.linkedin), "color": self.accent})
        if basics.github:
            segments.append({"kind": "github", "label": "GitHub", "url": str(basics.github), "color": self.accent})
        if basics.website:
            segments.append({"kind": "website", "label": "Portfolio", "url": str(basics.website), "color": self.accent})
        return segments

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self._segments = self._build_segments()
        self.width = min(avail_width, self.max_width)
        if not self._segments:
            self.height = 0
        else:
            self.height = (len(self._segments) * self.row_height) + ((len(self._segments) - 1) * self.row_gap)
        return self.width, self.height

    def draw(self) -> None:
        canv = self.canv
        y = self.height - self.row_height + 1.2

        for segment in self._segments:
            icon_x = 0
            if segment["kind"] == "phone":
                icon = _icon_image("phone")
                if icon is not None:
                    canv.drawImage(icon, icon_x, y + 0.3, width=9.4, height=9.4, mask="auto")
            elif segment["kind"] == "mail":
                icon = _icon_image("mail")
                if icon is not None:
                    canv.drawImage(icon, icon_x, y + 0.25, width=9.1, height=9.1, mask="auto")
            elif segment["kind"] == "location":
                icon = _icon_image("location")
                if icon is not None:
                    canv.drawImage(icon, icon_x + 0.15, y + 0.5, width=8.6, height=8.6, mask="auto")
            elif segment["kind"] == "linkedin":
                icon = _icon_image("linkedin")
                if icon is not None:
                    canv.drawImage(icon, icon_x + 0.2, y + 0.85, width=8.0, height=8.0, mask="auto")
            elif segment["kind"] == "github":
                icon = _icon_image("github")
                if icon is not None:
                    canv.drawImage(icon, icon_x, y + 0.5, width=9.0, height=9.0, mask="auto")
            elif segment["kind"] == "website":
                canv.setStrokeColor(self.accent)
                canv.setLineWidth(0.85)
                canv.circle(icon_x + 4.3, y + 4.8, 3.2, fill=0, stroke=1)
                canv.line(icon_x + 1.8, y + 4.8, icon_x + 6.8, y + 4.8)
                canv.line(icon_x + 4.3, y + 2.3, icon_x + 4.3, y + 7.3)

            text_x = self.icon_size + self.gap
            canv.setFillColor(segment["color"])
            canv.setFont(self.font_name, self.font_size)
            canv.drawString(text_x, y + 1.1, segment["label"])

            if segment["url"]:
                label_width = pdfmetrics.stringWidth(segment["label"], self.font_name, self.font_size)
                canv.linkURL(segment["url"], (text_x, y - 0.2, text_x + label_width, y + 10.2), relative=1)

            y -= self.row_height + self.row_gap


class ProjectTitleFlowable(Flowable):
    def __init__(self, item, width: float, accent: colors.Color) -> None:
        super().__init__()
        self.item = item
        self.max_width = width
        self.accent = accent
        self.font_name = "Helvetica-Bold"
        self.font_size = 9.0
        self.icon_size = 10.0
        self.gap = 6.0
        self.height = 12.0

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = min(avail_width, self.max_width)
        return self.width, self.height

    def _fit_title(self, max_width: float) -> str:
        title = self.item.name.strip()
        if not title or max_width <= 0:
            return ""

        if pdfmetrics.stringWidth(title, self.font_name, self.font_size) <= max_width:
            return title

        suffix = "..."
        if pdfmetrics.stringWidth(suffix, self.font_name, self.font_size) > max_width:
            return ""

        trimmed = title
        while trimmed and pdfmetrics.stringWidth(f"{trimmed}{suffix}", self.font_name, self.font_size) > max_width:
            trimmed = trimmed[:-1].rstrip()
        return f"{trimmed}{suffix}" if trimmed else suffix

    def draw(self) -> None:
        canv = self.canv
        baseline_y = 1.7
        reserved_icon_width = self.icon_size + self.gap if self.item.link else 0
        title = self._fit_title(self.width - reserved_icon_width)
        title_width = pdfmetrics.stringWidth(title, self.font_name, self.font_size)

        canv.saveState()
        clip_path = canv.beginPath()
        clip_path.rect(0, 0, self.width, self.height)
        canv.clipPath(clip_path, stroke=0, fill=0)

        canv.setFillColor(TEXT)
        canv.setFont(self.font_name, self.font_size)
        canv.drawString(0, baseline_y, title)

        if self.item.link and self.width > self.icon_size:
            icon = _icon_image("github")
            if icon is not None:
                icon_x = min(self.width - self.icon_size, title_width + self.gap)
                canv.drawImage(icon, icon_x, baseline_y - 1.05, width=10.0, height=10.0, mask="auto")
                canv.linkURL(str(self.item.link), (icon_x, baseline_y - 1, icon_x + self.icon_size, baseline_y + 10), relative=1)

        canv.restoreState()


def _contact_parts(resume: ResumePayload, accent: colors.Color) -> str:
    basics = resume.basics
    parts = [
        escape(basics.phone),
        escape(basics.email),
        escape(basics.location),
    ]
    if basics.linkedin:
        parts.append(f"<font color='{_hex(accent)}'><link href='{escape(str(basics.linkedin))}'>LinkedIn</link></font>")
    if basics.github:
        parts.append(f"<font color='{_hex(accent)}'><link href='{escape(str(basics.github))}'>GitHub</link></font>")
    if basics.website:
        parts.append(f"<font color='{_hex(accent)}'><link href='{escape(str(basics.website))}'>Portfolio</link></font>")
    return "  |  ".join(parts)


def _contact_stack(resume: ResumePayload, accent: colors.Color, styles, key: str) -> list:
    items = [
        escape(resume.basics.phone),
        escape(resume.basics.email),
        escape(resume.basics.location),
    ]
    if resume.basics.linkedin:
        items.append(f"<font color='{_hex(accent)}'><link href='{escape(str(resume.basics.linkedin))}'>LinkedIn</link></font>")
    if resume.basics.github:
        items.append(f"<font color='{_hex(accent)}'><link href='{escape(str(resume.basics.github))}'>GitHub</link></font>")
    if resume.basics.website:
        items.append(f"<font color='{_hex(accent)}'><link href='{escape(str(resume.basics.website))}'>Portfolio</link></font>")
    return [Paragraph(item, styles[key]) for item in items]


def _sidebar_skill_rows(resume: ResumePayload, styles) -> list:
    rows = []
    for item in resume.skills:
        skill_items = _safe_items(item.items)
        if not item.name.strip() and not skill_items:
            continue
        rows.append(
            Paragraph(
                f"<font name='Helvetica-Bold'>{escape(item.name)}:</font> {escape(', '.join(skill_items))}",
                styles["SidebarBody"],
            )
        )
    return rows


def _sidebar_certification_block(item, width: float, styles) -> list:
    head = Table(
        [[Paragraph(escape(item.title), styles["SidebarBodyBold"]), Paragraph(escape(item.year), styles["SidebarMetaRight"])]],
        colWidths=[width * 0.72, width * 0.28],
    )
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    blocks = [head]
    if item.issuer.strip():
        blocks.append(Paragraph(escape(item.issuer), styles["SidebarMeta"]))
    blocks.append(Spacer(1, 4))
    return blocks


def _section_title_text(section_key: str, resume: ResumePayload, config: dict) -> str:
    title_overrides = config.get("section_title_overrides", {})
    if section_key in title_overrides:
        return title_overrides[section_key]
    if section_key == "summary":
        return "Summary"
    if section_key == "skills":
        return "Skills"
    if section_key == "experience":
        return "Experience"
    if section_key == "projects":
        return "Projects"
    if section_key == "education":
        return "Education"
    if section_key == "certifications":
        return "Certification" if len(resume.certifications) == 1 else "Certifications"
    return section_key.replace("_", " ").title()


def _build_sidebar_story(resume: ResumePayload, sidebar_width: float, styles, config: dict) -> list:
    story = []
    if config.get("sidebar_kicker_text"):
        story.extend([Paragraph(escape(config["sidebar_kicker_text"]), styles["SidebarKicker"]), Spacer(1, config.get("sidebar_kicker_gap_after", 8))])

    story.extend([Paragraph(escape(resume.basics.full_name), styles["SidebarName"]), Spacer(1, 4)])
    if resume.basics.headline.strip():
        story.extend([Paragraph(escape(resume.basics.headline), styles["SidebarHeadline"]), Spacer(1, config.get("sidebar_headline_gap_after", 10))])
    else:
        story.append(Spacer(1, config.get("sidebar_name_gap_after", 10)))

    if config.get("sidebar_show_divider"):
        story.extend(
            [
                HRFlowable(width="100%", thickness=config.get("sidebar_divider_thickness", 0.75), color=config.get("sidebar_divider_color", LIGHT_RULE)),
                Spacer(1, config.get("sidebar_divider_gap_after", 10)),
            ]
        )

    sidebar_config = {
        **config,
        "section_variant": config.get("sidebar_section_variant", "stacked"),
        "section_title_style": config.get("sidebar_section_title_style", "SidebarTitle"),
        "uppercase_sections": config.get("sidebar_uppercase_sections", config.get("uppercase_sections", False)),
        "section_gap_after_header": config.get("sidebar_section_gap_after_header", config.get("section_gap_after_header", 4)),
        "section_gap_after": config.get("sidebar_section_gap_after", config.get("section_gap_after", 5)),
    }

    contact_items = [ContactStackFlowable(resume, sidebar_width, config["accent"])] if config.get("sidebar_contact_icons") else _contact_stack(
        resume, config["accent"], styles, "SidebarContact"
    )
    if config.get("sidebar_contact_title"):
        _append_section(story, config["sidebar_contact_title"], contact_items, sidebar_width, styles, sidebar_config)
    else:
        story.extend(contact_items)
        story.append(Spacer(1, 12))

    sidebar_keys = [key for key in _normalized_section_order(getattr(resume, "section_order", None)) if key in config.get("sidebar_keys", [])]
    for section_key in sidebar_keys:
        if section_key == "skills" and resume.skills:
            _append_section(story, _section_title_text(section_key, resume, sidebar_config), _sidebar_skill_rows(resume, styles), sidebar_width, styles, sidebar_config)
        elif section_key == "certifications" and resume.certifications:
            _append_section(
                story,
                _section_title_text(section_key, resume, sidebar_config),
                [_sidebar_certification_block(item, sidebar_width, styles) for item in resume.certifications],
                sidebar_width,
                styles,
                sidebar_config,
            )
    return story


def _build_styles(config: dict):
    styles = getSampleStyleSheet()
    accent = config["accent"]
    styles.add(
        ParagraphStyle(
            name="Name",
            fontName=config.get("name_font", "Helvetica-Bold"),
            fontSize=config.get("name_size", 24),
            leading=config.get("name_leading", 26),
            alignment=config.get("header_align", TA_LEFT),
            textColor=TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Headline",
            fontName=config.get("headline_font", "Helvetica"),
            fontSize=config.get("headline_size", 11),
            leading=config.get("headline_leading", 14),
            alignment=config.get("header_align", TA_LEFT),
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Contact",
            fontName="Helvetica",
            fontSize=config.get("contact_size", 9.2),
            leading=config.get("contact_leading", 12),
            alignment=config.get("header_align", TA_LEFT),
            textColor=config.get("contact_text", TEXT),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            fontName="Helvetica-Bold",
            fontSize=config.get("section_size", 10.4),
            leading=config.get("section_size", 10.4),
            alignment=TA_LEFT,
            textColor=config.get("section_text", accent),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=config.get("body_size", 9.2),
            leading=config.get("body_leading", 12.6),
            alignment=TA_LEFT,
            textColor=TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeBullet",
            parent=styles["Body"],
            leftIndent=config.get("bullet_indent", 12),
            bulletIndent=2,
            spaceAfter=config.get("bullet_space_after", 1.6),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItemRole",
            fontName="Helvetica-Bold",
            fontSize=config.get("item_role_size", 9.6),
            leading=config.get("item_role_leading", 12),
            textColor=TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItemCompany",
            fontName="Helvetica",
            fontSize=config.get("item_company_size", 9.1),
            leading=config.get("item_company_leading", 11.8),
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItemCompanyLink",
            parent=styles["ItemCompany"],
            textColor=accent,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItemMeta",
            fontName="Helvetica",
            fontSize=config.get("item_meta_size", 8.8),
            leading=config.get("item_meta_leading", 11),
            textColor=MUTED,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ItemMetaRight",
            parent=styles["ItemMeta"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarKicker",
            fontName="Helvetica-Bold",
            fontSize=config.get("sidebar_kicker_size", 9.0),
            leading=config.get("sidebar_kicker_leading", 10.4),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_title_color", accent),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarName",
            fontName=config.get("sidebar_name_font", config.get("name_font", "Helvetica-Bold")),
            fontSize=config.get("sidebar_name_size", 19),
            leading=config.get("sidebar_name_leading", 21),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_text", TEXT),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarHeadline",
            fontName="Helvetica",
            fontSize=config.get("sidebar_headline_size", 9.4),
            leading=config.get("sidebar_headline_leading", 12),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_muted", MUTED),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarContact",
            fontName="Helvetica",
            fontSize=config.get("sidebar_contact_size", 8.5),
            leading=config.get("sidebar_contact_leading", 11),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_text", TEXT),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarBody",
            fontName="Helvetica",
            fontSize=config.get("sidebar_body_size", 8.35),
            leading=config.get("sidebar_body_leading", 10.2),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_text", TEXT),
            spaceAfter=config.get("sidebar_skill_space_after", 0),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarBodyBold",
            parent=styles["SidebarBody"],
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarMeta",
            fontName="Helvetica",
            fontSize=config.get("sidebar_meta_size", 7.8),
            leading=config.get("sidebar_meta_leading", 9.1),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_muted", MUTED),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarMetaRight",
            parent=styles["SidebarMeta"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarTitle",
            fontName="Helvetica-Bold",
            fontSize=config.get("sidebar_title_size", 10.2),
            leading=config.get("sidebar_title_leading", 11.8),
            alignment=TA_LEFT,
            textColor=config.get("sidebar_title_color", accent),
        )
    )
    return styles


def _section_header(title: str, width: float, styles, config: dict):
    title_style = styles[config.get("section_title_style", "SectionTitle")]

    if config.get("section_variant") == "pill":
        table = Table([[Paragraph(escape(title.upper()), title_style)]], colWidths=[width])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), config.get("pill_bg", colors.HexColor("#EFF6FF"))),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    if config.get("section_variant") == "stacked":
        label = escape(title.upper() if config.get("uppercase_sections") else title)
        if title in config.get("section_titles_without_rule", []):
            table = Table([[Paragraph(label, title_style)]], colWidths=[width])
            table.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            return table

        table = Table(
            [
                [Paragraph(label, title_style)],
                [""],
                [HRFlowable(width="100%", thickness=0.75, color=config.get("rule_color", LIGHT_RULE))],
            ],
            colWidths=[width],
            rowHeights=[None, config.get("stacked_rule_gap", 2), None],
        )
        table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return table

    label = escape(title.upper() if config.get("uppercase_sections") else title)
    table = Table(
        [[Paragraph(label, title_style), HRFlowable(width="100%", thickness=0.75, color=config.get("rule_color", LIGHT_RULE))]],
        colWidths=[config.get("section_label_width", 1.35) * inch, width - (config.get("section_label_width", 1.35) * inch)],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _bullet_rows(items: list[str], styles) -> list:
    return [
        Paragraph(
            to_reportlab_markup(item, bold_font_name=styles["ResumeBullet"].fontName),
            styles["ResumeBullet"],
            bulletText="\u2022",
        )
        for item in _safe_items(items)
    ]


def _skill_rows(resume: ResumePayload, styles) -> list:
    rows = []
    for item in resume.skills:
        skill_items = _safe_items(item.items)
        if not item.name.strip() and not skill_items:
            continue
        rows.append(
            Paragraph(
                f"<font name='Helvetica-Bold'>{escape(item.name)}:</font> {escape(', '.join(skill_items))}",
                styles["ResumeBullet"],
                bulletText="\u2022",
            )
        )
    return rows


def _experience_block(item, width: float, styles, config: dict | None = None) -> list:
    config = config or {}
    left = [Paragraph(escape(item.role), styles["ItemRole"])]
    if item.company_link:
        left.append(
            Paragraph(
                f"<link href='{escape(str(item.company_link))}'>{escape(item.company)}</link>",
                styles["ItemCompanyLink"],
            )
        )
    else:
        left.append(Paragraph(escape(item.company), styles["ItemCompany"]))

    right_parts = [part for part in [item.location, f"{item.start_date} - {'Current' if item.current or not item.end_date else item.end_date}"] if part]
    meta_ratio = config.get("experience_meta_ratio", 0.34)
    table = Table(
        [[left, Paragraph(escape(" | ".join(right_parts)), styles[config.get("experience_meta_style", "ItemMeta")])]],
        colWidths=[width * (1 - meta_ratio), width * meta_ratio],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    highlight_rows = _bullet_rows(item.achievements, styles)
    intro_blocks = [table, Spacer(1, 2)]
    if highlight_rows:
        lead = KeepTogether([*intro_blocks, highlight_rows[0]])
        return [lead, *highlight_rows[1:], Spacer(1, config.get("entry_space_after", 5))]
    return [KeepTogether(intro_blocks), Spacer(1, config.get("entry_space_after", 5))]


def _project_block(
    item,
    width: float,
    styles,
    accent: colors.Color,
    icon_link: bool = False,
    trailing_space: float = 5,
    keep_first_bullet_with_intro: bool = True,
) -> list:
    title_cell = ProjectTitleFlowable(item, width * 0.72, accent) if icon_link else Paragraph(escape(item.name), styles["ItemRole"])
    table = Table(
        [[title_cell, Paragraph(escape(item.year.strip()), styles["ItemMeta"])]],
        colWidths=[width * 0.72, width * 0.28],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    intro_blocks = [table]
    if item.tech_stack.strip():
        intro_blocks.extend([Paragraph(escape(item.tech_stack.strip()), styles["ItemCompany"]), Spacer(1, 2)])
    else:
        intro_blocks.append(Spacer(1, 2))
    if item.link and not icon_link:
        intro_blocks.extend(
            [
                Paragraph(f"<link href='{escape(str(item.link))}'>Project Link</link>", styles["ItemCompanyLink"]),
                Spacer(1, 2),
            ]
        )

    highlight_rows = _bullet_rows(item.highlights, styles)
    if highlight_rows:
        if keep_first_bullet_with_intro:
            lead = KeepTogether([*intro_blocks, highlight_rows[0]])
            return [lead, *highlight_rows[1:], Spacer(1, trailing_space)]
        return [KeepTogether(intro_blocks), *highlight_rows, Spacer(1, trailing_space)]
    return [KeepTogether(intro_blocks), Spacer(1, trailing_space)]


def _education_block(item, width: float, styles) -> KeepTogether:
    meta = [part for part in [item.location, item.score] if part]
    table = Table(
        [[Paragraph(escape(item.institution), styles["ItemRole"]), Paragraph(escape(item.duration), styles["ItemMeta"])]],
        colWidths=[width * 0.72, width * 0.28],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    blocks = [table, Paragraph(escape(item.degree), styles["ItemCompany"])]
    if meta:
        blocks.append(Paragraph(escape(" | ".join(meta)), styles["ItemMeta"]))
    blocks.append(Spacer(1, 5))
    return KeepTogether(blocks)


def _certification_block(item, width: float, styles) -> KeepTogether:
    table = Table(
        [[Paragraph(escape(item.title), styles["ItemRole"]), Paragraph(escape(item.year), styles["ItemMeta"])]],
        colWidths=[width * 0.76, width * 0.24],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    blocks = [table]
    if item.issuer.strip():
        blocks.append(Paragraph(escape(item.issuer), styles["ItemCompany"]))
    blocks.append(Spacer(1, 5))
    return KeepTogether(blocks)


def _anchor_blocks(item) -> list:
    if isinstance(item, (list, tuple)):
        return list(item)
    if isinstance(item, KeepTogether):
        return list(getattr(item, "_content", [item]))
    return [item]


def _append_section(story: list, title: str, items: list, width: float, styles, config: dict) -> None:
    if not items:
        return
    section_min_space_map = config.get("section_min_space_map", {})
    min_space = section_min_space_map.get(title)
    if min_space:
        story.append(CondPageBreak(min_space))
    header_gap = Spacer(1, config.get("section_gap_after_header", 4))
    section_tail = Spacer(1, config.get("section_gap_after", 5))
    header = _section_header(title, width, styles, config)
    anchor_map = config.get("section_first_anchor_flowables", {})
    if title in anchor_map:
        first_item, remaining_items = items[0], items[1:]
        first_blocks = _anchor_blocks(first_item)
        first_anchor_count = max(1, anchor_map[title])
        anchor_blocks = first_blocks[:first_anchor_count]
        overflow_blocks = first_blocks[first_anchor_count:]
        story.append(KeepTogether([header, header_gap, *anchor_blocks]))
        for block in overflow_blocks:
            story.append(block)
    else:
        story.extend([header, header_gap])
        remaining_items = items

    for item in remaining_items:
        if isinstance(item, (list, tuple)):
            story.extend(item)
        else:
            story.append(item)
    story.append(section_tail)


def _build_ordered_story(story: list, resume: ResumePayload, width: float, styles, config: dict, section_keys: list[str]) -> None:
    for section_key in section_keys:
        if section_key == "summary" and resume.basics.summary.strip():
            _append_section(
                story,
                _section_title_text(section_key, resume, config),
                [Paragraph(to_reportlab_markup(_normalize_inline_paragraph_text(resume.basics.summary), bold_font_name=styles["Body"].fontName), styles["Body"])],
                width,
                styles,
                config,
            )
        elif section_key == "skills" and resume.skills:
            _append_section(story, _section_title_text(section_key, resume, config), _skill_rows(resume, styles), width, styles, config)
        elif section_key == "experience" and resume.experience:
            _append_section(
                story,
                _section_title_text(section_key, resume, config),
                [_experience_block(item, width, styles, config) for item in resume.experience],
                width,
                styles,
                config,
            )
        elif section_key == "projects" and resume.projects:
            project_blocks = [
                flowable
                for item in resume.projects
                for flowable in _project_block(
                    item,
                    width,
                    styles,
                    config["accent"],
                    icon_link=config.get("project_link_icon", False),
                    trailing_space=config.get("entry_space_after", 5),
                    keep_first_bullet_with_intro=config.get("project_keep_first_bullet_with_intro", True),
                )
            ]
            if config.get("keep_projects_together"):
                project_blocks = [KeepTogether(project_blocks)]
            _append_section(
                story,
                _section_title_text(section_key, resume, config),
                project_blocks,
                width,
                styles,
                config,
            )
        elif section_key == "education" and resume.education:
            _append_section(
                story,
                _section_title_text(section_key, resume, config),
                [_education_block(item, width, styles) for item in resume.education],
                width,
                styles,
                config,
            )
        elif section_key == "certifications" and resume.certifications:
            _append_section(
                story,
                _section_title_text(section_key, resume, config),
                [_certification_block(item, width, styles) for item in resume.certifications],
                width,
                styles,
                config,
            )


def _build_single_column_pdf(resume: ResumePayload, config: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=config.get("left_margin", 0.62) * inch,
        rightMargin=config.get("right_margin", 0.62) * inch,
        topMargin=config.get("top_margin", 0.42) * inch,
        bottomMargin=config.get("bottom_margin", 0.32) * inch,
        title=f"{resume.basics.full_name} Resume",
        author=resume.basics.full_name,
    )
    styles = _build_styles(config)
    story = []

    if config.get("top_band"):
        band = Table([[""]], colWidths=[doc.width], rowHeights=[config.get("top_band_height", 12)])
        band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), config["accent"])]))
        story.extend([band, Spacer(1, config.get("band_gap_after", 6))])

    story.append(Paragraph(escape(resume.basics.full_name), styles["Name"]))
    if resume.basics.headline.strip():
        story.extend([Spacer(1, 3), Paragraph(escape(resume.basics.headline), styles["Headline"])])
    story.append(Spacer(1, 4))
    if config.get("icon_contact_line"):
        story.append(ContactLineFlowable(resume, doc.width, config["accent"], align=config.get("contact_align", "left")))
    else:
        story.append(Paragraph(_contact_parts(resume, config["accent"]), styles["Contact"]))
    story.append(Spacer(1, config.get("header_gap_after", 10)))

    section_keys = _normalized_section_order(getattr(resume, "section_order", None))
    _build_ordered_story(story, resume, doc.width, styles, config, section_keys)

    doc.build(story)
    return buffer.getvalue()


def _build_sidebar_pdf(resume: ResumePayload, config: dict) -> bytes:
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=config.get("left_margin", 0.54) * inch,
        rightMargin=config.get("right_margin", 0.54) * inch,
        topMargin=config.get("top_margin", 0.4) * inch,
        bottomMargin=config.get("bottom_margin", 0.32) * inch,
        title=f"{resume.basics.full_name} Resume",
        author=resume.basics.full_name,
    )
    styles = _build_styles(config)
    sidebar_width = config.get("sidebar_width", 2.0) * inch
    column_gap = config.get("column_gap", 0.26) * inch
    first_main = Frame(
        doc.leftMargin + sidebar_width + column_gap,
        doc.bottomMargin,
        doc.width - sidebar_width - column_gap,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="main",
    )
    later_frame = Frame(
        doc.leftMargin + sidebar_width + column_gap,
        doc.bottomMargin,
        doc.width - sidebar_width - column_gap,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="later",
    )

    def draw_sidebar_panel(canvas, _doc):
        if config.get("sidebar_bg"):
            sidebar_bleed = config.get("sidebar_bleed", 12)
            canvas.saveState()
            canvas.setFillColor(config["sidebar_bg"])
            canvas.rect(
                _doc.leftMargin - sidebar_bleed,
                _doc.bottomMargin - sidebar_bleed,
                sidebar_width + sidebar_bleed,
                _doc.height + (sidebar_bleed * 2),
                fill=1,
                stroke=0,
            )
            canvas.restoreState()

    def draw_first_page(canvas, _doc):
        draw_sidebar_panel(canvas, _doc)

        sidebar_frame = Frame(
            _doc.leftMargin,
            _doc.bottomMargin,
            sidebar_width,
            _doc.height,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="sidebar-repeat",
        )
        sidebar_story = _build_sidebar_story(resume, sidebar_width, styles, config)
        sidebar_frame.addFromList(sidebar_story, canvas)

    def draw_later_page(canvas, _doc):
        draw_sidebar_panel(canvas, _doc)

    doc.addPageTemplates(
        [
            PageTemplate(id="first", frames=[first_main], onPage=draw_first_page),
            PageTemplate(id="later", frames=[later_frame], onPage=draw_later_page),
        ]
    )

    main_story = [NextPageTemplate("later"), Spacer(1, 2)]

    main_keys = [key for key in _normalized_section_order(getattr(resume, "section_order", None)) if key not in config.get("sidebar_keys", [])]
    _build_ordered_story(main_story, resume, doc.width - sidebar_width - column_gap, styles, config, main_keys)

    doc.build(main_story)
    return buffer.getvalue()


def _profile_banner_initials(full_name: str) -> str:
    parts = [part for part in re.split(r"\s+", full_name.strip()) if part]
    initials = "".join(part[0].upper() for part in parts[:2])
    return initials or "CV"


def _profile_banner_sidebar_education_block(item, styles) -> list:
    blocks = []
    if item.degree.strip():
        blocks.append(Paragraph(escape(item.degree), styles["SidebarBodyBold"]))
    if item.institution.strip():
        blocks.append(Paragraph(escape(item.institution), styles["SidebarBody"]))
    for line in [item.location or "", item.duration or "", item.score or ""]:
        if str(line).strip():
            blocks.append(Paragraph(escape(str(line).strip()), styles["SidebarMeta"]))
    blocks.append(Spacer(1, 6))
    return blocks


def _profile_banner_sidebar_skill_rows(resume: ResumePayload, styles) -> list:
    rows = []
    for item in resume.skills:
        skill_items = _safe_items(item.items) or ([item.name.strip()] if item.name.strip() else [])
        for skill in skill_items:
            rows.append(Paragraph(escape(skill), styles["SidebarBullet"], bulletText="\u2022"))
    return rows


def _build_profile_banner_sidebar_story(resume: ResumePayload, sidebar_width: float, styles, config: dict) -> list:
    story = []
    sidebar_config = {
        **config,
        "section_variant": "stacked",
        "section_title_style": "SidebarTitle",
        "uppercase_sections": True,
        "section_gap_after_header": 7,
        "section_gap_after": 12,
        "section_titles_without_rule": ["Personal Information", "Education", "Key Skills"],
    }
    _append_section(
        story,
        "Personal Information",
        [ContactStackFlowable(resume, sidebar_width, config["accent"])],
        sidebar_width,
        styles,
        sidebar_config,
    )

    if resume.education:
        _append_section(
            story,
            "Education",
            [_profile_banner_sidebar_education_block(item, styles) for item in resume.education],
            sidebar_width,
            styles,
            sidebar_config,
        )

    if resume.skills:
        _append_section(story, "Key Skills", _profile_banner_sidebar_skill_rows(resume, styles), sidebar_width, styles, sidebar_config)

    return story


def _draw_profile_banner_header(canvas, doc, resume: ResumePayload, styles, config: dict) -> None:
    page_width, page_height = letter
    banner_height = config.get("banner_height", 2.05) * inch
    banner_y = page_height - banner_height
    accent = config["accent"]

    canvas.saveState()
    canvas.setFillColor(accent)
    canvas.rect(0, banner_y, page_width, banner_height, fill=1, stroke=0)

    avatar_radius = config.get("avatar_radius", 0.68) * inch
    avatar_x = doc.leftMargin + avatar_radius + 0.02 * inch
    avatar_y = banner_y + (banner_height / 2)
    canvas.setFillColor(config.get("avatar_bg", colors.white))
    canvas.setStrokeColor(colors.white)
    canvas.setLineWidth(5)
    canvas.circle(avatar_x, avatar_y, avatar_radius, fill=1, stroke=1)
    canvas.setFillColor(config.get("avatar_text", accent))
    canvas.setFont("Helvetica-Bold", 25)
    canvas.drawCentredString(avatar_x, avatar_y - 8, _profile_banner_initials(resume.basics.full_name))
    canvas.restoreState()

    text_x = avatar_x + avatar_radius + 0.4 * inch
    text_width = page_width - text_x - doc.rightMargin
    text_frame = Frame(
        text_x,
        banner_y + 0.25 * inch,
        text_width,
        banner_height - 0.5 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="profile-banner-header",
    )
    header_story = [Paragraph(escape(resume.basics.full_name), styles["BannerName"])]
    if resume.basics.headline.strip():
        header_story.extend([Spacer(1, 7), Paragraph(escape(resume.basics.headline), styles["BannerHeadline"])])
    if resume.basics.summary.strip():
        header_story.extend(
            [
                Spacer(1, 8),
                Paragraph(
                    to_reportlab_markup(_normalize_inline_paragraph_text(resume.basics.summary), bold_font_name=styles["BannerSummary"].fontName),
                    styles["BannerSummary"],
                ),
            ]
        )
    text_frame.addFromList(header_story, canvas)


def _build_profile_banner_pdf(resume: ResumePayload, config: dict) -> bytes:
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=config.get("left_margin", 0.34) * inch,
        rightMargin=config.get("right_margin", 0.34) * inch,
        topMargin=config.get("top_margin", 0.0) * inch,
        bottomMargin=config.get("bottom_margin", 0.28) * inch,
        title=f"{resume.basics.full_name} Resume",
        author=resume.basics.full_name,
    )
    styles = _build_styles(config)
    styles.add(
        ParagraphStyle(
            name="BannerName",
            fontName="Helvetica-Bold",
            fontSize=31,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BannerHeadline",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BannerSummary",
            fontName="Helvetica",
            fontSize=9.2,
            leading=11.8,
            alignment=TA_CENTER,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SidebarBullet",
            parent=styles["SidebarBody"],
            leftIndent=12,
            bulletIndent=1,
            spaceAfter=3.4,
        )
    )

    banner_height = config.get("banner_height", 2.05) * inch
    sidebar_width = config.get("sidebar_width", 2.18) * inch
    column_gap = config.get("column_gap", 0.26) * inch
    first_body_height = letter[1] - doc.topMargin - doc.bottomMargin - banner_height
    first_main = Frame(
        doc.leftMargin + sidebar_width + column_gap,
        doc.bottomMargin,
        doc.width - sidebar_width - column_gap,
        first_body_height,
        leftPadding=0,
        rightPadding=0,
        topPadding=18,
        bottomPadding=0,
        id="profile-banner-main",
    )
    later_main = Frame(
        doc.leftMargin + sidebar_width + column_gap,
        doc.bottomMargin,
        doc.width - sidebar_width - column_gap,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="profile-banner-later",
    )

    def draw_sidebar_panel(canvas, _doc, height: float) -> None:
        canvas.saveState()
        canvas.setFillColor(config.get("sidebar_bg", colors.HexColor("#F3F3F4")))
        canvas.rect(_doc.leftMargin - 4, _doc.bottomMargin, sidebar_width + 8, height, fill=1, stroke=0)
        canvas.restoreState()

    def draw_first_page(canvas, _doc) -> None:
        _draw_profile_banner_header(canvas, _doc, resume, styles, config)
        draw_sidebar_panel(canvas, _doc, first_body_height)
        sidebar_frame = Frame(
            _doc.leftMargin,
            _doc.bottomMargin,
            sidebar_width,
            first_body_height,
            leftPadding=0,
            rightPadding=0,
            topPadding=18,
            bottomPadding=0,
            id="profile-banner-sidebar",
        )
        sidebar_frame.addFromList(_build_profile_banner_sidebar_story(resume, sidebar_width, styles, config), canvas)

    def draw_later_page(canvas, _doc) -> None:
        draw_sidebar_panel(canvas, _doc, _doc.height)

    doc.addPageTemplates(
        [
            PageTemplate(id="first", frames=[first_main], onPage=draw_first_page),
            PageTemplate(id="later", frames=[later_main], onPage=draw_later_page),
        ]
    )

    main_story = [NextPageTemplate("later")]
    main_keys = [key for key in _normalized_section_order(getattr(resume, "section_order", None)) if key not in ["summary", "skills", "education"]]
    _build_ordered_story(main_story, resume, doc.width - sidebar_width - column_gap, styles, config, main_keys)

    doc.build(main_story)
    return buffer.getvalue()


def build_additional_template_pdf(resume: ResumePayload, template_id: str, section_color: str | None = None) -> bytes:
    override_palette = build_theme_palette(section_color) if section_color else None

    if template_id == "contemporary-accent":
        return _build_single_column_pdf(
            resume,
            {
                "accent": override_palette["accent"] if override_palette else colors.HexColor("#1E3A8A"),
                "name_font": "Helvetica-Bold",
                "name_size": 21,
                "headline_size": 10.0,
                "headline_leading": 11.4,
                "contact_size": 8.7,
                "section_text": override_palette["accent_deep"] if override_palette else colors.HexColor("#1E3A8A"),
                "section_variant": "pill",
                "pill_bg": override_palette["accent_soft"] if override_palette else colors.HexColor("#EFF6FF"),
                "top_band": True,
                "top_band_height": 8,
                "band_gap_after": 6,
                "header_gap_after": 7,
                "section_gap_after_header": 3,
                "section_gap_after": 2,
                "body_size": 8.75,
                "body_leading": 11.15,
                "item_role_size": 9.0,
                "item_role_leading": 10.8,
                "item_company_size": 8.55,
                "item_company_leading": 10.5,
                "item_meta_size": 8.35,
                "item_meta_leading": 10.1,
                "bullet_space_after": 0.9,
                "top_margin": 0.24,
                "bottom_margin": 0.16,
                "left_margin": 0.5,
                "right_margin": 0.5,
                "icon_contact_line": True,
                "contact_align": "left",
                "project_link_icon": True,
            },
        )

    if template_id == "executive-elegance":
        executive_sidebar_keys = ["skills"]
        if getattr(getattr(resume, "layout_options", None), "executive_certifications_in_sidebar", False):
            executive_sidebar_keys.append("certifications")

        return _build_sidebar_pdf(
            resume,
            {
                "accent": override_palette["accent_deep"] if override_palette else colors.HexColor("#8A6430"),
                "name_font": "Times-Bold",
                "name_size": 21.2,
                "name_leading": 22.4,
                "headline_size": 9.65,
                "headline_leading": 12.4,
                "section_text": override_palette["accent_deep"] if override_palette else colors.HexColor("#8A6430"),
                "rule_color": override_palette["accent_line"] if override_palette else colors.HexColor("#E5DCCD"),
                "body_size": 8.6,
                "body_leading": 11.2,
                "item_role_size": 8.9,
                "item_role_leading": 10.4,
                "item_company_size": 8.2,
                "item_company_leading": 9.8,
                "item_meta_size": 7.95,
                "item_meta_leading": 9.7,
                "bullet_space_after": 0.35,
                "left_margin": 0.44,
                "right_margin": 0.44,
                "top_margin": 0.14,
                "bottom_margin": 0.1,
                "sidebar_width": 2.08,
                "column_gap": 0.22,
                "sidebar_bg": override_palette["accent_surface_strong"] if override_palette else colors.HexColor("#F7F2EA"),
                "sidebar_text": colors.HexColor("#334155"),
                "sidebar_muted": colors.HexColor("#5F6B79"),
                "sidebar_title_color": override_palette["accent_deep"] if override_palette else colors.HexColor("#8A6430"),
                "sidebar_kicker_text": "EXECUTIVE PROFILE",
                "sidebar_kicker_size": 8.45,
                "sidebar_kicker_leading": 9.6,
                "sidebar_kicker_gap_after": 8,
                "sidebar_headline_gap_after": 10,
                "sidebar_name_gap_after": 10,
                "sidebar_show_divider": False,
                "sidebar_divider_thickness": 0.75,
                "sidebar_divider_color": override_palette["accent_line"] if override_palette else colors.HexColor("#E5DCCD"),
                "sidebar_divider_gap_after": 9,
                "sidebar_contact_size": 7.8,
                "sidebar_contact_leading": 9.7,
                "sidebar_body_size": 7.65,
                "sidebar_body_leading": 9.2,
                "sidebar_skill_space_after": 3.5,
                "sidebar_title_size": 9.85,
                "sidebar_title_leading": 10.9,
                "section_label_width": 1.55,
                "section_variant": "stacked",
                "uppercase_sections": True,
                "sidebar_section_variant": "stacked",
                "sidebar_uppercase_sections": True,
                "sidebar_section_title_style": "SidebarTitle",
                "sidebar_contact_title": "Contact",
                "section_titles_without_rule": ["Contact"],
                "header_gap_after": 5,
                "section_gap_after_header": 1.5,
                "section_gap_after": 2.4,
                "sidebar_section_gap_after_header": 1.5,
                "sidebar_section_gap_after": 10,
                "stacked_rule_gap": 2.4,
                "entry_space_after": 1.7,
                "sidebar_contact_icons": True,
                "sidebar_keys": executive_sidebar_keys,
                "experience_meta_ratio": 0.42,
                "experience_meta_style": "ItemMetaRight",
                "project_link_icon": True,
                "project_keep_first_bullet_with_intro": False,
                "keep_projects_together": False,
                "section_min_space_map": {
                    "Projects": 0.42 * inch,
                    "Education": 0.85 * inch,
                    "Certifications": 0.85 * inch,
                },
                "section_first_anchor_flowables": {
                    "Projects": 99,
                },
                "section_title_overrides": {"summary": "Professional Summary"},
            },
        )

    if template_id == "profile-banner":
        return _build_profile_banner_pdf(
            resume,
            {
                "accent": override_palette["accent"] if override_palette else colors.HexColor("#DC5B60"),
                "avatar_text": override_palette["accent_deep"] if override_palette else colors.HexColor("#B13F45"),
                "name_font": "Helvetica-Bold",
                "name_size": 22,
                "headline_size": 9.8,
                "section_text": colors.HexColor("#1E5967"),
                "sidebar_title_color": colors.HexColor("#1E5967"),
                "rule_color": colors.HexColor("#D8E3E6"),
                "body_size": 8.8,
                "body_leading": 11.6,
                "item_role_size": 9.1,
                "item_role_leading": 11.1,
                "item_company_size": 8.65,
                "item_company_leading": 10.6,
                "item_meta_size": 8.2,
                "item_meta_leading": 10,
                "bullet_space_after": 1.1,
                "entry_space_after": 5,
                "left_margin": 0.34,
                "right_margin": 0.34,
                "bottom_margin": 0.26,
                "banner_height": 2.05,
                "avatar_radius": 0.68,
                "sidebar_width": 2.18,
                "column_gap": 0.26,
                "sidebar_bg": colors.HexColor("#F3F3F4"),
                "sidebar_text": colors.HexColor("#23222A"),
                "sidebar_muted": colors.HexColor("#4B5563"),
                "sidebar_body_size": 8.55,
                "sidebar_body_leading": 10.7,
                "sidebar_meta_size": 8.1,
                "sidebar_meta_leading": 10.2,
                "sidebar_contact_size": 8.3,
                "sidebar_contact_leading": 10.5,
                "sidebar_title_size": 9.6,
                "sidebar_title_leading": 11,
                "section_variant": "stacked",
                "uppercase_sections": True,
                "section_titles_without_rule": ["Professional Experience", "Projects", "Certifications", "Certification"],
                "section_gap_after_header": 7,
                "section_gap_after": 8,
                "section_title_overrides": {"experience": "Professional Experience"},
                "experience_meta_ratio": 0.4,
                "experience_meta_style": "ItemMetaRight",
                "project_keep_first_bullet_with_intro": False,
            },
        )

    raise ValueError(f"Unsupported template: {template_id}")

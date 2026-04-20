from __future__ import annotations

from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, Flowable, HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from PIL import Image, ImageDraw

from .models import CertificationItem, EducationItem, ExperienceItem, ProjectItem, ResumePayload, SkillCategory
from .pdf_templates import build_additional_template_pdf
from .rich_text import to_reportlab_markup
from .theme_palette import build_theme_palette


ROOT_DIR = Path(__file__).resolve().parents[2]
ICON_ASSET_PATHS = {
    "phone": ROOT_DIR / "contact-logo-clean.png",
    "mail": ROOT_DIR / "email-logo-clean.png",
    "github": ROOT_DIR / "github-logo-clean.png",
    "linkedin": ROOT_DIR / "linkedin-logo-clean.png",
    "location": ROOT_DIR / "location-logo-clean.png",
}


FONT_PATHS = {
    "Georgia": Path(r"C:\Windows\Fonts\georgia.ttf"),
    "Georgia-Bold": Path(r"C:\Windows\Fonts\georgiab.ttf"),
    "Arial": Path(r"C:\Windows\Fonts\arial.ttf"),
    "Arial-Bold": Path(r"C:\Windows\Fonts\arialbd.ttf"),
    "Arial-Italic": Path(r"C:\Windows\Fonts\ariali.ttf"),
}

for font_name, font_path in FONT_PATHS.items():
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

REGISTERED_FONTS = set(pdfmetrics.getRegisteredFontNames())
SERIF_FONT = "Georgia" if "Georgia" in REGISTERED_FONTS else "Times-Roman"
SANS_FONT = "Arial" if "Arial" in REGISTERED_FONTS else "Helvetica"
SANS_BOLD_FONT = "Arial-Bold" if "Arial-Bold" in REGISTERED_FONTS else "Helvetica-Bold"
SANS_ITALIC_FONT = "Arial-Italic" if "Arial-Italic" in REGISTERED_FONTS else "Helvetica-Oblique"


TEXT = colors.HexColor("#1E1E1E")
MUTED = colors.HexColor("#555555")
BLUE = colors.HexColor("#1C5FDB")
LINE = colors.HexColor("#C9D8F4")
RED = colors.HexColor("#DB4A39")
DEFAULT_SECTION_ORDER = ["summary", "skills", "experience", "projects", "education", "certifications"]


def _rgb(color: colors.Color) -> tuple[int, int, int, int]:
    return (
        int(round(color.red * 255)),
        int(round(color.green * 255)),
        int(round(color.blue * 255)),
        255,
    )


def _normalized_section_order(section_order: list[str] | None) -> list[str]:
    safe_order = section_order or []
    unique_known = [key for index, key in enumerate(safe_order) if key in DEFAULT_SECTION_ORDER and safe_order.index(key) == index]
    missing = [key for key in DEFAULT_SECTION_ORDER if key not in unique_known]
    return [*unique_known, *missing]


@lru_cache(maxsize=16)
def _icon_image(kind: str) -> ImageReader:
    asset_path = ICON_ASSET_PATHS.get(kind)
    if asset_path and asset_path.exists():
        image = Image.open(asset_path).convert("RGBA")
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            image = image.crop(bbox)
        return ImageReader(image)

    size = 96
    image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    black = _rgb(TEXT)
    red = _rgb(RED)

    if kind == "phone":
        draw.polygon(
            [
                (12, 58),
                (18, 48),
                (28, 46),
                (32, 50),
                (52, 34),
                (48, 30),
                (56, 22),
                (64, 24),
                (74, 16),
                (84, 22),
                (88, 32),
                (82, 40),
                (74, 42),
                (70, 38),
                (50, 54),
                (54, 58),
                (46, 66),
                (38, 64),
                (28, 72),
                (18, 68),
            ],
            fill=black,
        )
    elif kind == "location":
        draw.ellipse((30, 10, 64, 42), fill=red)
        draw.rounded_rectangle((40, 36, 54, 52), radius=4, fill=red)
        draw.polygon([(47, 80), (42, 48), (52, 48)], fill=(94, 145, 208, 255))
    elif kind == "github":
        draw.polygon([(26, 22), (36, 8), (42, 24)], fill=black)
        draw.polygon([(54, 24), (60, 8), (70, 22)], fill=black)
        draw.ellipse((18, 20, 78, 80), fill=black)
        draw.ellipse((38, 42, 44, 48), fill=(255, 255, 255, 255))
        draw.ellipse((52, 42, 58, 48), fill=(255, 255, 255, 255))

    return ImageReader(image)


class ContactLineFlowable(Flowable):
    def __init__(self, resume: ResumePayload, width: float, accent_color: colors.Color = BLUE) -> None:
        super().__init__()
        self.resume = resume
        self.max_width = width
        self.accent_color = accent_color
        self.font_name = SANS_FONT
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
            segments.append({"kind": "linkedin", "label": "LinkedIn", "url": str(basics.linkedin), "color": self.accent_color})
        if basics.github:
            segments.append({"kind": "github", "label": "GitHub", "url": str(basics.github), "color": self.accent_color})
        if basics.website:
            segments.append({"kind": "website", "label": "Portfolio", "url": str(basics.website), "color": self.accent_color})
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
        self.canv.drawImage(_icon_image("phone"), x - 0.05, y - 1.35, width=10.4, height=10.4, mask="auto")

    def _draw_mail(self, x: float, y: float) -> None:
        self.canv.drawImage(
            _icon_image("mail"),
            x + 0.05,
            y - 1.32,
            width=10.0,
            height=10.0,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )

    def _draw_location(self, x: float, y: float) -> None:
        self.canv.drawImage(_icon_image("location"), x + 0.2, y - 1.08, width=9.2, height=9.2, mask="auto")

    def _draw_linkedin(self, x: float, y: float) -> None:
        self.canv.drawImage(_icon_image("linkedin"), x + 0.2, y - 0.52, width=8.75, height=8.75, mask="auto")

    def _draw_github(self, x: float, y: float) -> None:
        self.canv.drawImage(_icon_image("github"), x + 0.02, y - 1.02, width=10.1, height=10.1, mask="auto")

    def _draw_website(self, x: float, y: float) -> None:
        canv = self.canv
        canv.setStrokeColor(self.accent_color)
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

        x = max(0, (self.width - total_width) / 2)
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


class ProjectTitleFlowable(Flowable):
    def __init__(self, item: ProjectItem, width: float) -> None:
        super().__init__()
        self.item = item
        self.max_width = width
        self.font_name = SANS_BOLD_FONT
        self.font_size = 8.9
        self.icon_size = 10.4
        self.gap = 6.0
        self.height = 12.0

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = min(avail_width, self.max_width)
        return self.width, self.height

    def _draw_github_icon(self, x: float, y: float) -> None:
        self.canv.drawImage(_icon_image("github"), x, y - 1.08, width=10.2, height=10.2, mask="auto")

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
            icon_x = min(self.width - self.icon_size, title_width + self.gap)
            self._draw_github_icon(icon_x, baseline_y + 0.2)
            canv.linkURL(str(self.item.link), (icon_x, baseline_y - 1, icon_x + self.icon_size, baseline_y + 10), relative=1)

        canv.restoreState()


SECTION_MIN_SPACE = {
    "Summary": 1.45 * inch,
    "Skills": 1.8 * inch,
    "Experience": 2.3 * inch,
    "Projects": 2.2 * inch,
    "Certification": 1.4 * inch,
    "Certifications": 1.4 * inch,
    "Education": 1.5 * inch,
}


def _build_styles(theme_palette: dict[str, colors.Color] | None = None):
    styles = getSampleStyleSheet()
    section_title_color = theme_palette["accent"] if theme_palette else BLUE
    link_color = theme_palette["accent"] if theme_palette else BLUE
    styles.add(
        ParagraphStyle(
            name="Name",
            fontName=SERIF_FONT,
            fontSize=16.5,
            leading=17,
            alignment=TA_CENTER,
            textColor=TEXT,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Contact",
            fontName=SANS_FONT,
            fontSize=8.8,
            leading=11.2,
            alignment=TA_CENTER,
            textColor=TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            fontName=SANS_BOLD_FONT,
            fontSize=10.0,
            leading=10.8,
            alignment=TA_LEFT,
            textColor=section_title_color,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName=SANS_FONT,
            fontSize=8.35,
            leading=10.35,
            alignment=TA_LEFT,
            textColor=TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeBullet",
            parent=styles["Body"],
            leftIndent=13,
            bulletIndent=2,
            spaceAfter=1.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleLeft",
            fontName=SANS_FONT,
            fontSize=8.7,
            leading=10.3,
            textColor=TEXT,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleCenter",
            fontName=SANS_BOLD_FONT,
            fontSize=8.7,
            leading=10.3,
            textColor=link_color,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleCenterPlain",
            fontName=SANS_BOLD_FONT,
            fontSize=8.7,
            leading=10.3,
            textColor=TEXT,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleLeftBold",
            fontName=SANS_BOLD_FONT,
            fontSize=8.7,
            leading=10.3,
            textColor=TEXT,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleLocation",
            fontName=SANS_ITALIC_FONT,
            fontSize=8.6,
            leading=10.3,
            textColor=MUTED,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RoleDate",
            fontName=SANS_FONT,
            fontSize=8.6,
            leading=10.3,
            textColor=TEXT,
            alignment=TA_RIGHT,
        )
    )
    return styles


def _section_header(title: str, width: float, styles, rule_color: colors.Color = LINE) -> Table:
    table = Table(
        [[Paragraph(escape(title), styles["SectionTitle"]), HRFlowable(width="100%", thickness=0.8, color=rule_color)]],
        colWidths=[1.08 * inch, width - 1.08 * inch],
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


def _skill_block(skills: list[SkillCategory], styles):
    flowables = []
    for item in skills:
        text = f"<font name='{SANS_BOLD_FONT}'>{escape(item.name)}:</font> {escape(', '.join([s for s in item.items if s.strip()]))}"
        flowables.append(Paragraph(text, styles["ResumeBullet"], bulletText="\u2022"))
    return flowables


def _experience_header(item: ExperienceItem, width: float, styles) -> Table:
    duration = f"{item.start_date} - {'Current' if item.current or not item.end_date else item.end_date}"
    table = Table(
        [
            [
                Paragraph(escape(item.role), styles["RoleLeft"]),
                Paragraph(
                    f"<u><link href='{escape(str(item.company_link))}'>{escape(item.company)}</link></u>" if item.company_link else escape(item.company),
                    styles["RoleCenter"] if item.company_link else styles["RoleCenterPlain"],
                ),
                Paragraph(escape(item.location), styles["RoleLocation"]),
                Paragraph(escape(duration), styles["RoleDate"]),
            ]
        ],
        colWidths=[1.75 * inch, 1.75 * inch, 2.0 * inch, width - (1.75 + 1.75 + 2.0) * inch],
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
    return table


def _experience_block(item: ExperienceItem, width: float, styles) -> list:
    flowables = [_experience_header(item, width, styles), Spacer(1, 2)]
    for bullet in item.achievements:
        flowables.append(
            Paragraph(
                to_reportlab_markup(bullet, bold_font_name=styles["ResumeBullet"].fontName),
                styles["ResumeBullet"],
                bulletText="\u2022",
            )
        )
    flowables.append(Spacer(1, 3))
    return flowables


def _project_block(item: ProjectItem, width: float, styles) -> list:
    rows = [[ProjectTitleFlowable(item, width - 1.05 * inch), Paragraph(escape(item.year.strip()), styles["RoleDate"])]]
    if item.tech_stack.strip():
        rows.append(
            [
                Paragraph(f"<font color='{MUTED.hexval()}'>{escape(item.tech_stack.strip())}</font>", styles["Body"]),
                Paragraph("", styles["RoleDate"]),
            ]
        )

    header = Table(
        rows,
        colWidths=[width - 1.05 * inch, 1.05 * inch],
    )
    header.setStyle(
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
    flowables = [header]
    flowables.append(Spacer(1, 2))
    for bullet in item.highlights:
        flowables.append(
            Paragraph(
                to_reportlab_markup(bullet, bold_font_name=styles["ResumeBullet"].fontName),
                styles["ResumeBullet"],
                bulletText="\u2022",
            )
        )
    flowables.append(Spacer(1, 3))
    return flowables


def _education_row(item: EducationItem, width: float, styles) -> list:
    table = Table(
        [
            [
                Paragraph(escape(item.institution), styles["RoleLeftBold"]),
                Paragraph(escape(item.duration), styles["RoleDate"]),
            ],
            [
                Paragraph(escape(item.degree), styles["RoleLeft"]),
                Paragraph(""),
            ]
        ],
        colWidths=[width - 1.05 * inch, 1.05 * inch],
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
    flowables = [table]
    extras = [part for part in [item.location, item.score] if part]
    if extras:
        flowables.append(Paragraph(escape(" | ".join(extras)), styles["ResumeBullet"], bulletText="\u2022"))
    flowables.append(Spacer(1, 3))
    return flowables


def _certification_row(item: CertificationItem, width: float, styles) -> Table:
    table = Table(
        [[Paragraph(escape(f"{item.title}"), styles["RoleLeft"]), Paragraph(escape(item.year), styles["RoleDate"])]],
        colWidths=[width - 0.8 * inch, 0.8 * inch],
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
    return table


def _certification_block(item: CertificationItem, width: float, styles) -> list:
    flowables = [_certification_row(item, width, styles)]
    issuer = item.issuer.strip()
    if issuer:
        flowables.append(Paragraph(escape(issuer), styles["ResumeBullet"], bulletText="\u2022"))
    flowables.append(Spacer(1, 3))
    return flowables


def _append_flowables(story: list, flowables: list) -> None:
    for flowable in flowables:
        if isinstance(flowable, (list, tuple)):
            story.extend(flowable)
        else:
            story.append(flowable)


def _append_full_section(story: list, title: str, content: list, doc: SimpleDocTemplate, styles, rule_color: colors.Color = LINE) -> None:
    if not content:
        return
    story.append(CondPageBreak(SECTION_MIN_SPACE[title]))
    story.extend([_section_header(title, doc.width, styles, rule_color), Spacer(1, 4)])
    _append_flowables(story, content)


def _append_flowing_section(story: list, title: str, blocks: list, doc: SimpleDocTemplate, styles, rule_color: colors.Color = LINE) -> None:
    if not blocks:
        return
    story.append(CondPageBreak(SECTION_MIN_SPACE[title]))
    story.extend([_section_header(title, doc.width, styles, rule_color), Spacer(1, 4)])
    _append_flowables(story, blocks)


def build_classic_resume_pdf(resume: ResumePayload, section_color: str | None = None) -> bytes:
    theme_palette = build_theme_palette(section_color) if section_color else None
    styles = _build_styles(theme_palette)
    accent_color = theme_palette["accent"] if theme_palette else BLUE
    rule_color = theme_palette["accent_line"] if theme_palette else LINE
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.34 * inch,
        bottomMargin=0.22 * inch,
        title=f"{resume.basics.full_name} Resume",
        author=resume.basics.full_name,
    )

    story = [
        Paragraph(escape(resume.basics.full_name.upper()), styles["Name"]),
        ContactLineFlowable(resume, doc.width, accent_color=accent_color),
        Spacer(1, 5),
    ]
    section_order = _normalized_section_order(getattr(resume, "section_order", None))

    for section_key in section_order:
        if section_key == "summary" and resume.basics.summary.strip():
            _append_full_section(
                story,
                "Summary",
                [Paragraph(to_reportlab_markup(resume.basics.summary, bold_font_name=styles["Body"].fontName), styles["Body"]), Spacer(1, 5)],
                doc,
                styles,
                rule_color,
            )
        elif section_key == "skills" and resume.skills:
            _append_full_section(story, "Skills", [*_skill_block(resume.skills, styles), Spacer(1, 3)], doc, styles, rule_color)
        elif section_key == "experience" and resume.experience:
            _append_flowing_section(
                story,
                "Experience",
                [_experience_block(item, doc.width, styles) for item in resume.experience],
                doc,
                styles,
                rule_color,
            )
        elif section_key == "projects" and resume.projects:
            _append_full_section(
                story,
                "Projects",
                [_project_block(item, doc.width, styles) for item in resume.projects],
                doc,
                styles,
                rule_color,
            )
        elif section_key == "education" and resume.education:
            _append_full_section(
                story,
                "Education",
                [_education_row(item, doc.width, styles) for item in resume.education],
                doc,
                styles,
                rule_color,
            )
        elif section_key == "certifications" and resume.certifications:
            certification_title = "Certification" if len(resume.certifications) == 1 else "Certifications"
            certification_content = [_certification_block(item, doc.width, styles) for item in resume.certifications]
            _append_full_section(story, certification_title, certification_content, doc, styles, rule_color)

    doc.build(story)
    return buffer.getvalue()


def build_resume_pdf(resume: ResumePayload, template_id: str = "classic-professional", section_color: str | None = None) -> bytes:
    if template_id == "classic-professional":
        return build_classic_resume_pdf(resume, section_color)
    return build_additional_template_pdf(resume, template_id, section_color)

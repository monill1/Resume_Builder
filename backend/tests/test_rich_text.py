from __future__ import annotations

import unittest

from backend.app.models import ResumeGenerateRequest
from backend.app.pdf_generator import build_resume_pdf
from backend.app.rich_text import resolve_bold_font_name, strip_rich_text, to_reportlab_markup
from backend.app.sample_data import SAMPLE_RESUME
from backend.app.theme_palette import build_theme_palette


class RichTextTests(unittest.TestCase):
    def test_strip_rich_text_removes_bold_markers(self) -> None:
        self.assertEqual(strip_rich_text("Built **FastAPI** services"), "Built FastAPI services")

    def test_resolve_bold_font_name_matches_common_fonts(self) -> None:
        self.assertEqual(resolve_bold_font_name("Arial"), "Arial-Bold")
        self.assertEqual(resolve_bold_font_name("Helvetica"), "Helvetica-Bold")
        self.assertEqual(resolve_bold_font_name("Times-Roman"), "Times-Bold")

    def test_reportlab_markup_uses_explicit_bold_font(self) -> None:
        markup = to_reportlab_markup("Built **FastAPI** services", bold_font_name="Arial")
        self.assertIn("<font name='Arial-Bold'>FastAPI</font>", markup)
        self.assertNotIn("**", markup)

    def test_generate_request_accepts_section_color(self) -> None:
        payload = ResumeGenerateRequest(template_id="classic-professional", section_color="#1c5fdb", resume=SAMPLE_RESUME)
        self.assertEqual(payload.section_color, "#1c5fdb")

    def test_build_resume_pdf_accepts_custom_section_color(self) -> None:
        pdf_bytes = build_resume_pdf(SAMPLE_RESUME, "executive-elegance", "#8a6430")
        self.assertGreater(len(pdf_bytes), 1000)

    def test_theme_palette_builds_related_accent_colors(self) -> None:
        palette = build_theme_palette("#22c55e")
        self.assertEqual(palette["accent"].hexval().lower(), "0x22c55e")
        self.assertNotEqual(palette["accent"].hexval().lower(), palette["accent_line"].hexval().lower())


if __name__ == "__main__":
    unittest.main()

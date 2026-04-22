from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from backend.app.job_description import JobDescriptionAnalysis, JobSourceContent
from backend.app.resume_parser import ResumeAnalysis
from backend.app.services.semantic_matcher import MODEL_NAME, compute_semantic_match


class FakeSentenceTransformer:
    def encode(self, texts, **kwargs):
        return np.array([self._vector(text) for text in texts], dtype=float)

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            1.0 if any(token in lowered for token in ("api", "apis", "rest", "fastapi")) else 0.0,
            1.0 if any(token in lowered for token in ("backend", "server-side", "service")) else 0.0,
            1.0 if any(token in lowered for token in ("database", "postgresql", "sql")) else 0.0,
            1.0 if any(token in lowered for token in ("payroll", "compliance", "invoice")) else 0.0,
        ]


def _job(requirement: str) -> JobDescriptionAnalysis:
    source = JobSourceContent(
        source="pasted_description",
        job_url=None,
        title="Backend Engineer",
        description=requirement,
        text=requirement,
    )
    return JobDescriptionAnalysis(
        source=source,
        title="Backend Engineer",
        requirement_lines=[requirement],
        required_skills=[],
        preferred_skills=[],
        tools=[],
        years_required=None,
        degree_requirements=[],
        certifications=[],
        industry_keywords=[],
        action_phrases=[],
        responsibility_phrases=[requirement],
        location_requirements=[],
        authorization_requirements=[],
    )


def _job_with_lines(lines: list[str]) -> JobDescriptionAnalysis:
    text = "\n".join(lines)
    source = JobSourceContent(
        source="pasted_description",
        job_url=None,
        title="Backend Engineer",
        description=text,
        text=text,
    )
    return JobDescriptionAnalysis(
        source=source,
        title="Backend Engineer",
        requirement_lines=lines,
        required_skills=[],
        preferred_skills=[],
        tools=[],
        years_required=None,
        degree_requirements=[],
        certifications=[],
        industry_keywords=[],
        action_phrases=[],
        responsibility_phrases=[],
        location_requirements=[],
        authorization_requirements=[],
    )


def _resume(experience_bullet: str) -> ResumeAnalysis:
    section_lines = {
        "summary": ["Backend developer focused on production software."],
        "skills": ["Python, FastAPI, PostgreSQL"],
        "experience": [experience_bullet],
        "projects": [],
        "education": ["Bachelor of Engineering"],
        "certifications": [],
    }
    return ResumeAnalysis(
        section_text={section: "\n".join(lines) for section, lines in section_lines.items()},
        section_lines=section_lines,
        parse_preview="\n".join(line for lines in section_lines.values() for line in lines),
        experience_titles=["Backend Developer"],
        experience_years=3.0,
        keyword_inventory={},
        measurable_achievement_count=0,
        contact_signals={"email": True, "phone": True, "location": True},
        standard_sections_present={section: bool(lines) for section, lines in section_lines.items()},
        date_formats={"year_only"},
        parse_warnings=[],
    )


class SemanticMatcherTests(unittest.TestCase):
    @patch("backend.app.services.semantic_matcher.get_semantic_model", return_value=FakeSentenceTransformer())
    def test_rest_api_requirement_matches_fastapi_backend_bullet(self, _model) -> None:
        result = compute_semantic_match(
            _job("Built scalable REST APIs for customer workflows."),
            _resume("Developed backend APIs using FastAPI for customer workflows."),
        )

        self.assertEqual(result.model_name, MODEL_NAME)
        self.assertTrue(result.model_available)
        self.assertGreaterEqual(result.semantic_coverage, 80)
        self.assertEqual(result.jd_to_resume_matches[0]["band"], "strong")
        self.assertEqual(result.jd_to_resume_matches[0]["resume_section"], "experience")

    @patch("backend.app.services.semantic_matcher.get_semantic_model", return_value=FakeSentenceTransformer())
    def test_unrelated_requirement_keeps_semantic_coverage_low(self, _model) -> None:
        result = compute_semantic_match(
            _job("Manage payroll compliance and invoice reconciliation."),
            _resume("Developed backend APIs using FastAPI for customer workflows."),
        )

        self.assertLess(result.semantic_coverage, 65)
        self.assertTrue(all(item["band"] == "weak" for item in result.jd_to_resume_matches))

    @patch("backend.app.services.semantic_matcher.get_semantic_model", return_value=FakeSentenceTransformer())
    def test_location_notice_and_work_mode_are_not_semantically_matched(self, _model) -> None:
        result = compute_semantic_match(
            _job_with_lines(
                [
                    "Job Location: Hyderabad/Bangalore/Pune",
                    "Notice: Immediate to 30 days joiners required",
                    "Work Mode: Hybrid",
                    "Build scalable REST APIs for customer workflows.",
                ]
            ),
            _resume("Developed backend APIs using FastAPI for customer workflows."),
        )

        non_matchable = [item for item in result.jd_to_resume_matches if item["matchable"] is False]
        matchable = [item for item in result.jd_to_resume_matches if item["matchable"] is True]

        self.assertEqual(len(non_matchable), 3)
        self.assertTrue(all(item["match"] is None for item in non_matchable))
        self.assertTrue(all(item["reason"] == "Not applicable for resume matching" for item in non_matchable))
        self.assertEqual(matchable[0]["band"], "strong")

    @patch("backend.app.services.semantic_matcher.get_semantic_model", return_value=FakeSentenceTransformer())
    def test_weak_similarity_returns_no_evidence_instead_of_forced_sentence(self, _model) -> None:
        result = compute_semantic_match(
            _job("Manage payroll compliance and invoice reconciliation."),
            _resume("Developed backend APIs using FastAPI for customer workflows."),
        )

        weak_match = result.jd_to_resume_matches[0]
        self.assertIsNone(weak_match["match"])
        self.assertEqual(weak_match["best_resume_text"], "No relevant evidence found")
        self.assertEqual(weak_match["reason"], "No relevant evidence found")


if __name__ == "__main__":
    unittest.main()

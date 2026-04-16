from __future__ import annotations

import unittest

from backend.app.ats import analyze_resume_against_job, prepare_job_source
from backend.app.ats_optimizer import optimize_resume_against_job
from backend.app.ats_normalization import best_match_type
from backend.app.ats_samples import ATS_SAMPLE_CASES
from backend.app.models import ATSAnalysisRequest
from backend.app.sample_data import SAMPLE_RESUME


def analyze_case(case_key: str):
    case = ATS_SAMPLE_CASES[case_key]
    source = prepare_job_source(job_url=None, job_description=case["job_description"], target_title=case["job_title"])
    return analyze_resume_against_job(case["resume"], source)


class ATSScoringTests(unittest.TestCase):
    def test_request_accepts_pasted_description_without_url(self) -> None:
        case = ATS_SAMPLE_CASES["backend_developer"]
        payload = ATSAnalysisRequest(
            job_description=case["job_description"],
            target_title=case["job_title"],
            resume=case["resume"],
        )
        self.assertIsNone(payload.job_url)
        self.assertEqual(payload.target_title, "Backend Developer")

    def test_backend_developer_scores_as_strong_moderate_match(self) -> None:
        result = analyze_case("backend_developer")
        matched = {item.keyword for item in result.matched_keywords}
        missing = {item.keyword for item in result.missing_keywords}

        self.assertGreaterEqual(result.overall_score, 78)
        self.assertGreaterEqual(result.section_scores.skills_match, 80)
        self.assertIn("FastAPI", matched)
        self.assertIn("Kubernetes", missing)
        self.assertGreaterEqual(result.parsing_confidence, 0.9)

    def test_data_analyst_highlights_content_gaps_not_formatting_failure(self) -> None:
        result = analyze_case("data_analyst")
        missing = {item.keyword for item in result.missing_keywords}

        self.assertGreaterEqual(result.section_scores.formatting_parseability, 90)
        self.assertIn("Python", missing)
        self.assertIn("A/B Testing", missing)
        self.assertGreaterEqual(result.section_scores.experience_relevance, 70)

    def test_aiml_engineer_supports_acronym_and_alias_matching(self) -> None:
        result = analyze_case("aiml_engineer")
        matched = {item.keyword for item in result.matched_keywords}

        self.assertIn("Natural Language Processing", matched)
        self.assertIn("Generative AI", matched)
        self.assertGreaterEqual(result.section_scores.experience_relevance, 75)

    def test_product_analyst_flags_missing_python_requirement(self) -> None:
        result = analyze_case("product_analyst")
        missing = {item.keyword for item in result.missing_keywords}
        comparison = {item.requirement: item.status for item in result.comparison_view}

        self.assertIn("Python", missing)
        self.assertEqual(comparison["Python"], "missing")
        self.assertGreaterEqual(result.section_scores.keyword_coverage, 50)

    def test_normalization_matches_acronyms_and_variants(self) -> None:
        self.assertEqual(best_match_type("Natural Language Processing", "Built NLP pipelines for support routing."), "exact")
        self.assertEqual(best_match_type("PostgreSQL", "Optimized Postgres queries for analytics workloads."), "exact")

    def test_auto_fix_improves_supported_content_without_inventing_missing_skills(self) -> None:
        source = prepare_job_source(
            job_url=None,
            job_description=(
                "Backend Developer\n"
                "Required qualifications:\n"
                "- Experience with Python, FastAPI, REST APIs, Docker, AWS, and SQL.\n"
                "- Preferred experience with Kubernetes and Redis.\n"
                "Responsibilities:\n"
                "- Build backend APIs, partner with stakeholders, and ship reliable features."
            ),
            target_title="Backend Developer",
        )

        optimized = optimize_resume_against_job(SAMPLE_RESUME, source, target_score=85)
        optimized_skill_items = {item for group in optimized.optimized_resume.skills for item in group.items}

        self.assertGreaterEqual(optimized.updated_score, optimized.previous_score)
        self.assertIn("Python", optimized.optimized_resume.basics.summary)
        self.assertNotIn("Kubernetes", optimized_skill_items)
        self.assertIn("FastAPI", optimized_skill_items)

if __name__ == "__main__":
    unittest.main()

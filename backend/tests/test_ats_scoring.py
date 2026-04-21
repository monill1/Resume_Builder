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


def analyze_resume(resume, job_description: str, target_title: str):
    source = prepare_job_source(job_url=None, job_description=job_description, target_title=target_title)
    return analyze_resume_against_job(resume, source)


BACKEND_JD = ATS_SAMPLE_CASES["backend_developer"]["job_description"]


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
        self.assertGreaterEqual(result.job_match_score, 70)
        self.assertGreaterEqual(result.ats_readability_score, 90)
        self.assertEqual(result.overall_ats_score, result.overall_score)
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
        self.assertGreaterEqual(result.section_scores.experience_relevance, 70)

    def test_product_analyst_flags_missing_python_requirement(self) -> None:
        result = analyze_case("product_analyst")
        missing = {item.keyword for item in result.missing_keywords}
        comparison = {item.requirement: item.status for item in result.comparison_view}

        self.assertIn("Python", missing)
        self.assertEqual(comparison["Python"], "missing")
        self.assertGreaterEqual(result.section_scores.keyword_coverage, 50)

    def test_normalization_matches_acronyms_and_variants(self) -> None:
        self.assertEqual(best_match_type("Natural Language Processing", "Built NLP pipelines for support routing."), "alias")
        self.assertEqual(best_match_type("PostgreSQL", "Optimized Postgres queries for analytics workloads."), "alias")
        self.assertEqual(best_match_type("REST APIs", "Delivered API development for partner integrations."), "alias")

    def test_response_exposes_split_scores_and_breakdown(self) -> None:
        result = analyze_case("backend_developer")

        self.assertGreaterEqual(result.job_match_score, 0)
        self.assertGreaterEqual(result.ats_readability_score, 0)
        self.assertIn("skills_match", result.score_breakdown.job_match)
        self.assertIn("parseability", result.score_breakdown.ats_readability)
        self.assertAlmostEqual(result.score_breakdown.weights["job_match"], 0.75)
        self.assertAlmostEqual(result.score_breakdown.weights["readability"], 0.25)

    def test_skills_only_matches_are_weaker_than_contextual_evidence(self) -> None:
        contextual = analyze_case("backend_developer")
        skills_only_resume = ATS_SAMPLE_CASES["backend_developer"]["resume"].model_copy(deep=True)
        skills_only_resume.basics.headline = "Software Engineer"
        skills_only_resume.basics.summary = "Software engineer with delivery experience across web services, team collaboration, and production support."
        skills_only_resume.projects = []
        for item in skills_only_resume.experience:
            item.role = "Software Engineer"
            item.achievements = ["Supported internal delivery workflows and collaborated with teammates on sprint planning."]

        skills_only = analyze_resume(skills_only_resume, BACKEND_JD, "Backend Developer")
        weak = {item.keyword for item in skills_only.weak_evidence_skills}
        strong = {item.keyword for item in contextual.strong_evidence_skills}

        self.assertLess(skills_only.job_match_score, contextual.job_match_score)
        self.assertIn("FastAPI", weak)
        self.assertIn("FastAPI", strong)
        self.assertLess(skills_only.score_breakdown.job_match["keyword_coverage"], contextual.score_breakdown.job_match["keyword_coverage"])

    def test_missing_required_skills_create_critical_gaps(self) -> None:
        result = analyze_resume(ATS_SAMPLE_CASES["data_analyst"]["resume"], BACKEND_JD, "Backend Developer")
        missing_required = {item.keyword for item in result.missing_required_skills}
        critical_titles = " ".join(item.title for item in result.critical_gaps)

        self.assertIn("FastAPI", missing_required)
        self.assertIn("Docker", missing_required)
        self.assertIn("Missing required skill", critical_titles)
        self.assertLess(result.job_match_score, 70)

    def test_missing_preferred_skills_do_not_create_hard_screen_gap(self) -> None:
        jd = """
Backend Developer
Required qualifications:
- 3+ years building APIs with Python, FastAPI, PostgreSQL, Docker, and AWS.
Preferred qualifications:
- GraphQL experience.
Responsibilities:
- Build backend APIs and improve production services.
""".strip()
        result = analyze_resume(ATS_SAMPLE_CASES["backend_developer"]["resume"], jd, "Backend Developer")
        missing_preferred = {item.keyword for item in result.missing_preferred_skills}
        critical_titles = " ".join(item.title for item in result.critical_gaps)

        self.assertIn("GraphQL", missing_preferred)
        self.assertNotIn("GraphQL", critical_titles)
        self.assertGreaterEqual(result.job_match_score, 70)

    def test_keyword_stuffing_penalty_flags_repetition(self) -> None:
        resume = ATS_SAMPLE_CASES["backend_developer"]["resume"].model_copy(deep=True)
        resume.basics.headline = "Backend Developer"
        resume.basics.summary = (
            "Python FastAPI PostgreSQL Docker AWS " * 9
            + "backend services and production support."
        )
        resume.skills[0].items = ["Python", "Python", "Python", "FastAPI", "FastAPI", "PostgreSQL", "Docker", "AWS"]
        resume.projects = []
        for item in resume.experience:
            item.achievements = ["Supported team delivery and wrote documentation for internal services."]

        result = analyze_resume(resume, BACKEND_JD, "Backend Developer")

        self.assertTrue(result.stuffing_warnings)
        self.assertLess(result.score_breakdown.ats_readability["repetition_stuffing"], 100)
        self.assertTrue(result.suggestions.medium_impact)

    def test_good_job_match_can_be_limited_by_readability(self) -> None:
        resume = ATS_SAMPLE_CASES["backend_developer"]["resume"].model_copy(deep=True)
        resume.section_order = ["education", "certifications", "projects", "experience", "skills", "summary"]
        resume.education = []
        resume.certifications = []

        result = analyze_resume(resume, BACKEND_JD, "Backend Developer")

        self.assertGreaterEqual(result.job_match_score, 65)
        self.assertLess(result.ats_readability_score, 95)
        self.assertLess(result.overall_score, result.ats_readability_score * 0.25 + result.job_match_score * 0.75 + 1)

    def test_good_readability_with_weak_job_match_stays_conservative(self) -> None:
        result = analyze_resume(ATS_SAMPLE_CASES["data_analyst"]["resume"], BACKEND_JD, "Backend Developer")

        self.assertGreaterEqual(result.ats_readability_score, 85)
        self.assertLess(result.job_match_score, result.ats_readability_score)
        self.assertLess(result.overall_score, 75)

    def test_partial_role_alignment_uses_role_families(self) -> None:
        jd = """
Business Analyst
Requirements:
- 2+ years of experience with SQL, dashboards, stakeholder communication, and business reporting.
Preferred:
- Product analytics or experimentation exposure.
Responsibilities:
- Analyze business processes, define KPIs, and communicate insights to partners.
""".strip()
        result = analyze_resume(ATS_SAMPLE_CASES["data_analyst"]["resume"], jd, "Business Analyst")
        role_alignment = result.score_breakdown.job_match["role_alignment"]

        self.assertGreaterEqual(role_alignment, 55)
        self.assertLess(role_alignment, 100)
        self.assertGreaterEqual(result.job_match_score, 55)

    def test_years_of_experience_mismatch_is_critical(self) -> None:
        resume = ATS_SAMPLE_CASES["backend_developer"]["resume"].model_copy(deep=True)
        resume.experience = resume.experience[:1]
        resume.experience[0].start_date = "2025"
        resume.experience[0].end_date = None
        resume.experience[0].current = True
        jd = BACKEND_JD.replace("3+ years", "5+ years")

        result = analyze_resume(resume, jd, "Senior Backend Developer")
        critical_titles = " ".join(item.title for item in result.critical_gaps)

        self.assertLess(result.score_breakdown.job_match["seniority_years_match"], 60)
        self.assertIn("Experience level below stated requirement", critical_titles)
        self.assertLessEqual(result.job_match_score, 78)

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

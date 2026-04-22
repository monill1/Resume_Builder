from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..ats_normalization import clean_phrase, dedupe_preserve_order, normalize_text, split_sentences, tokenize
from ..job_description import JobDescriptionAnalysis
from ..resume_parser import ResumeAnalysis


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SECTION_WEIGHTS = {
    "experience": 0.40,
    "projects": 0.30,
    "skills": 0.20,
    "summary": 0.10,
    "education": 0.05,
}

STRONG_MATCH_THRESHOLD = 0.80
PARTIAL_MATCH_THRESHOLD = 0.65

SKILL_ALIAS_MAP = {
    "rest api": ["fastapi", "django api", "backend api", "api development", "restful api", "rest apis"],
    "machine learning": ["ml", "scikit-learn", "sklearn", "pytorch", "tensorflow"],
    "database": ["postgresql", "postgres", "mysql", "sql", "database design"],
    "backend": ["fastapi", "django", "flask", "server-side", "backend api", "backend service"],
}

EDUCATION_RELEVANCE_TERMS = {
    "degree",
    "bachelor",
    "master",
    "phd",
    "education",
    "computer science",
    "certification",
    "license",
}

_MODEL: Any | None = None


@dataclass(frozen=True)
class ResumeSemanticChunk:
    text: str
    section: str
    weighted_text: str


@dataclass(frozen=True)
class SemanticMatcherResult:
    semantic_coverage: int
    matched_concepts: list[dict[str, object]]
    partial_concepts: list[dict[str, object]]
    missing_concepts: list[dict[str, object]]
    jd_to_resume_matches: list[dict[str, object]]
    confidence_factors: dict[str, float]
    model_name: str
    model_available: bool


def warm_semantic_model() -> None:
    """Load the sentence-transformer once during application startup."""
    get_semantic_model()


def get_semantic_model() -> Any:
    """Return the globally cached sentence-transformer model.

    The import is intentionally lazy so unit tests and non-ATS imports do not
    pay model startup cost. FastAPI startup calls this once in production.
    """
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def compute_semantic_match(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> SemanticMatcherResult:
    jd_chunks = parse_job_requirements(job)
    resume_chunks = parse_resume_chunks(job, resume)
    if not jd_chunks or not resume_chunks:
        return _empty_result(jd_chunks, resume_chunks)

    model_available = True
    try:
        embeddings = _embed_texts([*jd_chunks, *[chunk.weighted_text for chunk in resume_chunks]])
    except Exception:
        model_available = False
        embeddings = _fallback_embeddings([*jd_chunks, *[chunk.weighted_text for chunk in resume_chunks]])

    jd_embeddings = embeddings[: len(jd_chunks)]
    resume_embeddings = embeddings[len(jd_chunks) :]
    similarity_matrix = _cosine_similarity_matrix(jd_embeddings, resume_embeddings)

    matches: list[dict[str, object]] = []
    for jd_index, jd_text in enumerate(jd_chunks):
        candidates: list[tuple[float, float, int, ResumeSemanticChunk]] = []
        for resume_index, resume_chunk in enumerate(resume_chunks):
            raw_similarity = float(similarity_matrix[jd_index][resume_index])
            adjusted_similarity = _adjust_similarity(jd_text, resume_chunk, raw_similarity)
            candidates.append((adjusted_similarity, SECTION_WEIGHTS.get(resume_chunk.section, 0.0), resume_index, resume_chunk))
        adjusted_similarity, _, best_index, resume_chunk = max(candidates, key=lambda item: (item[0], item[1], -item[2]))
        raw_similarity = float(similarity_matrix[jd_index][best_index])
        band = _band_for_similarity(adjusted_similarity)
        matches.append(
            {
                "jd_text": jd_text,
                "best_resume_text": resume_chunk.text,
                "resume_section": resume_chunk.section,
                "similarity": round(adjusted_similarity, 4),
                "raw_similarity": round(raw_similarity, 4),
                "section_weight": SECTION_WEIGHTS.get(resume_chunk.section, 0.0),
                "band": band,
            }
        )

    matched = [item for item in matches if item["band"] == "strong"]
    partial = [item for item in matches if item["band"] == "partial"]
    missing = [item for item in matches if item["band"] == "weak"]
    semantic_coverage = round(100 * sum(float(item["similarity"]) for item in matches) / len(matches))

    return SemanticMatcherResult(
        semantic_coverage=max(0, min(100, semantic_coverage)),
        matched_concepts=_concept_payloads(matched),
        partial_concepts=_concept_payloads(partial),
        missing_concepts=_concept_payloads(missing),
        jd_to_resume_matches=matches,
        confidence_factors=_confidence_factors(jd_chunks, resume_chunks, matches),
        model_name=MODEL_NAME,
        model_available=model_available,
    )


def parse_job_requirements(job: JobDescriptionAnalysis) -> list[str]:
    lines = [*getattr(job, "requirement_lines", []), *job.responsibility_phrases, *job.action_phrases]
    requirements: list[str] = []
    for line in lines:
        cleaned = clean_phrase(_strip_marker(line))
        if len(cleaned.split()) < 3:
            continue
        for fragment in _split_requirement(cleaned):
            if _is_low_value_heading(fragment):
                continue
            requirements.append(fragment)

    if not requirements:
        requirements = [f"Experience with {term}" for term in dedupe_preserve_order([*job.required_skills, *job.tools])[:10]]
    return dedupe_preserve_order(requirements)[:16]


def parse_resume_chunks(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> list[ResumeSemanticChunk]:
    education_relevant = _education_is_relevant(job)
    chunks: list[ResumeSemanticChunk] = []
    for section in ("summary", "skills", "experience", "projects", "education"):
        if section == "education" and not education_relevant:
            continue
        for line in resume.section_lines.get(section, []):
            cleaned = clean_phrase(line)
            if len(cleaned.split()) < 2:
                continue
            if section in {"experience", "projects"} and _looks_like_entry_header(cleaned):
                continue
            chunks.append(
                ResumeSemanticChunk(
                    text=cleaned,
                    section=section,
                    weighted_text=_expand_aliases(cleaned),
                )
            )
    return chunks


def _embed_texts(texts: list[str]) -> Any:
    import numpy as np

    unique_texts = list(dict.fromkeys(texts))
    model = get_semantic_model()
    unique_embeddings = model.encode(
        unique_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    cache = {text: unique_embeddings[index] for index, text in enumerate(unique_texts)}
    return np.vstack([cache[text] for text in texts])


def _fallback_embeddings(texts: list[str]) -> list[list[float]]:
    vocabulary = sorted({token for text in texts for token in _concept_tokens(text)})
    if not vocabulary:
        return [[0.0] for _ in texts]
    token_index = {token: index for index, token in enumerate(vocabulary)}
    matrix = [[0.0 for _ in vocabulary] for _ in texts]
    for row_index, text in enumerate(texts):
        for token in _concept_tokens(text):
            matrix[row_index][token_index[token]] += 1.0
    for row_index, row in enumerate(matrix):
        norm = sum(value * value for value in row) ** 0.5 or 1.0
        matrix[row_index] = [value / norm for value in row]
    return matrix


def _cosine_similarity_matrix(left_embeddings: Any, right_embeddings: Any) -> list[list[float]]:
    try:
        from sklearn.metrics.pairwise import cosine_similarity

        matrix = cosine_similarity(left_embeddings, right_embeddings)
        return matrix.tolist() if hasattr(matrix, "tolist") else matrix
    except Exception:
        left_rows = left_embeddings.tolist() if hasattr(left_embeddings, "tolist") else left_embeddings
        right_rows = right_embeddings.tolist() if hasattr(right_embeddings, "tolist") else right_embeddings
        return [[_cosine(left, right) for right in right_rows] for left in left_rows]


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _adjust_similarity(jd_text: str, resume_chunk: ResumeSemanticChunk, raw_similarity: float) -> float:
    section_weight = SECTION_WEIGHTS.get(resume_chunk.section, 0.0)
    concept_overlap = _concept_overlap(jd_text, resume_chunk.text)
    alias_overlap = _alias_overlap(jd_text, resume_chunk.text)

    adjusted = raw_similarity + (section_weight * 0.12)
    if concept_overlap or alias_overlap:
        if resume_chunk.section in {"experience", "projects"}:
            adjusted += 0.10
        elif resume_chunk.section == "skills":
            adjusted += 0.04
        elif resume_chunk.section == "summary":
            adjusted += 0.01
    if resume_chunk.section == "summary" and not concept_overlap and not alias_overlap:
        adjusted -= 0.06
    return max(0.0, min(1.0, adjusted))


def _band_for_similarity(similarity: float) -> str:
    if similarity >= STRONG_MATCH_THRESHOLD:
        return "strong"
    if similarity >= PARTIAL_MATCH_THRESHOLD:
        return "partial"
    return "weak"


def _concept_payloads(matches: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "jd_text": item["jd_text"],
            "best_resume_text": item["best_resume_text"],
            "resume_section": item["resume_section"],
            "similarity": item["similarity"],
            "band": item["band"],
        }
        for item in matches
    ]


def _confidence_factors(
    jd_chunks: list[str],
    resume_chunks: list[ResumeSemanticChunk],
    matches: list[dict[str, object]],
) -> dict[str, float]:
    jd_parse_quality = min(1.0, 0.35 + len(jd_chunks) * 0.08)
    section_count = len({chunk.section for chunk in resume_chunks})
    evidence_sections = {str(item["resume_section"]) for item in matches if item["band"] in {"strong", "partial"}}
    resume_parse_quality = min(1.0, 0.30 + section_count * 0.12 + min(len(resume_chunks), 12) * 0.025)
    evidence_coverage = len(evidence_sections & {"experience", "projects", "skills"}) / 3
    semantic_coverage = sum(float(item["similarity"]) for item in matches) / len(matches) if matches else 0.0
    return {
        "jd_parse_quality": round(jd_parse_quality, 2),
        "resume_parse_quality": round(resume_parse_quality, 2),
        "evidence_coverage": round(evidence_coverage, 2),
        "semantic_coverage": round(semantic_coverage, 2),
    }


def _empty_result(jd_chunks: list[str], resume_chunks: list[ResumeSemanticChunk]) -> SemanticMatcherResult:
    return SemanticMatcherResult(
        semantic_coverage=0,
        matched_concepts=[],
        partial_concepts=[],
        missing_concepts=[],
        jd_to_resume_matches=[],
        confidence_factors={
            "jd_parse_quality": 0.0 if not jd_chunks else 0.4,
            "resume_parse_quality": 0.0 if not resume_chunks else 0.4,
            "evidence_coverage": 0.0,
            "semantic_coverage": 0.0,
        },
        model_name=MODEL_NAME,
        model_available=False,
    )


def _expand_aliases(text: str) -> str:
    normalized = normalize_text(text)
    concepts: list[str] = []
    for canonical, aliases in SKILL_ALIAS_MAP.items():
        terms = [canonical, *aliases]
        if any(_phrase_present(term, normalized) for term in terms):
            concepts.extend([canonical, *aliases])
    return " ".join([text, *dedupe_preserve_order(concepts)])


def _alias_overlap(left: str, right: str) -> bool:
    left_expanded = set(_concept_tokens(_expand_aliases(left)))
    right_expanded = set(_concept_tokens(_expand_aliases(right)))
    return bool(left_expanded & right_expanded)


def _concept_overlap(left: str, right: str) -> bool:
    left_tokens = {token for token in _concept_tokens(left) if len(token) > 2}
    right_tokens = {token for token in _concept_tokens(right) if len(token) > 2}
    return bool(left_tokens & right_tokens)


def _concept_tokens(text: str) -> list[str]:
    return [token for token in tokenize(_expand_aliases(text)) if len(token) > 2]


def _split_requirement(line: str) -> list[str]:
    fragments = split_sentences(line) or [line]
    output: list[str] = []
    for fragment in fragments:
        pieces = re.split(
            r"\s+(?:and|;)\s+(?=(?:build|built|develop|design|create|analyze|deploy|optimize|collaborate|lead|own|manage)\b)",
            fragment,
            flags=re.IGNORECASE,
        )
        output.extend(clean_phrase(piece) for piece in pieces if len(clean_phrase(piece).split()) >= 3)
    return output


def _strip_marker(text: str) -> str:
    return re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", text or "")


def _is_low_value_heading(text: str) -> bool:
    lowered = normalize_text(text).strip(" :")
    return lowered in {
        "requirements",
        "required qualifications",
        "preferred qualifications",
        "responsibilities",
        "what you will do",
        "what you ll do",
    }


def _looks_like_entry_header(text: str) -> bool:
    if " | " not in text:
        return False
    return not re.search(
        r"\b(built|build|developed|develop|designed|design|created|create|optimized|analyzed|deployed|implemented|led|managed|improved|delivered)\b",
        text,
        re.IGNORECASE,
    )


def _education_is_relevant(job: JobDescriptionAnalysis) -> bool:
    if job.degree_requirements or job.certifications:
        return True
    haystack = normalize_text(" ".join([job.title, job.source.description, job.source.text[:1000]]))
    return any(term in haystack for term in EDUCATION_RELEVANCE_TERMS)


def _phrase_present(phrase: str, normalized_text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(normalize_text(phrase))}(?!\w)", normalized_text))

from __future__ import annotations

import re
import logging
import os
from dataclasses import dataclass
from typing import Any

from ..ats_normalization import clean_phrase, dedupe_preserve_order, extract_known_terms, normalize_text, split_sentences, tokenize
from ..job_description import JobDescriptionAnalysis
from ..resume_parser import ResumeAnalysis


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_MODEL_NAME = "local-tfidf-semantic-fallback"
SEMANTIC_ENGINE_ENV = "ATS_SEMANTIC_ENGINE"
MIN_HF_MEMORY_MB = 900

logger = logging.getLogger(__name__)

SECTION_WEIGHTS = {
    "experience": 0.40,
    "projects": 0.30,
    "skills": 0.20,
    "summary": 0.10,
    "education": 0.05,
}

STRONG_MATCH_THRESHOLD = 0.80
PARTIAL_MATCH_THRESHOLD = 0.65
NO_EVIDENCE_REASON = "No relevant evidence found"
NOT_APPLICABLE_REASON = "Not applicable for resume matching"
MATCHABLE_JD_TYPES = {"skills", "responsibility", "tools/tech", "experience"}

SKILL_ALIAS_MAP = {
    "rest api": ["fastapi", "django api", "backend api", "api development", "restful api", "rest apis"],
    "machine learning": ["ml", "scikit-learn", "sklearn", "pytorch", "tensorflow"],
    "database": ["postgresql", "postgres", "mysql", "sql", "database design"],
    "backend": ["fastapi", "django", "flask", "server-side", "backend api", "backend service"],
    "agentic ai": ["langchain", "langgraph", "autogen", "auto gen", "llamaindex", "llama index", "ai agents"],
    "vector database": ["vector db", "pinecone", "weaviate", "chroma", "faiss", "qdrant"],
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
_MODEL_LOAD_FAILED = False


@dataclass(frozen=True)
class ResumeSemanticChunk:
    text: str
    section: str
    weighted_text: str


@dataclass(frozen=True)
class JDRequirementChunk:
    text: str
    jd_type: str

    @property
    def matchable(self) -> bool:
        return self.jd_type in MATCHABLE_JD_TYPES


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
    """Load the sentence-transformer once when the host has enough memory.

    Render free instances are currently limited to 512 MB. Importing PyTorch
    and loading MiniLM can exceed that before the API binds to its port, so
    auto mode skips warmup on constrained hosts and uses the deterministic
    fallback matcher instead.
    """
    if not _should_use_hf_model():
        logger.info("Semantic matcher warmup skipped; using local fallback matcher.")
        return
    get_semantic_model()


def get_semantic_model() -> Any:
    """Return the globally cached sentence-transformer model.

    The import is intentionally lazy so unit tests and non-ATS imports do not
    pay model startup cost. FastAPI startup calls this once in production.
    """
    global _MODEL, _MODEL_LOAD_FAILED
    if not _should_use_hf_model():
        raise RuntimeError("Hugging Face semantic model disabled for this runtime.")
    if _MODEL_LOAD_FAILED:
        raise RuntimeError("Hugging Face semantic model previously failed to load.")
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(MODEL_NAME)
        except Exception:
            _MODEL_LOAD_FAILED = True
            raise
    return _MODEL


def compute_semantic_match(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> SemanticMatcherResult:
    jd_requirement_chunks = parse_job_requirement_chunks(job)
    matchable_chunks = [chunk for chunk in jd_requirement_chunks if chunk.matchable]
    resume_chunks = parse_resume_chunks(job, resume)
    if not jd_requirement_chunks or not resume_chunks:
        return _empty_result(jd_requirement_chunks, resume_chunks)

    model_available = True
    model_name = MODEL_NAME
    try:
        embeddings = _embed_texts([*[chunk.text for chunk in matchable_chunks], *[chunk.weighted_text for chunk in resume_chunks]])
    except Exception:
        model_available = False
        model_name = FALLBACK_MODEL_NAME
        embeddings = _fallback_embeddings([*[chunk.text for chunk in matchable_chunks], *[chunk.weighted_text for chunk in resume_chunks]])

    jd_embeddings = embeddings[: len(matchable_chunks)]
    resume_embeddings = embeddings[len(matchable_chunks) :]
    similarity_matrix = _cosine_similarity_matrix(jd_embeddings, resume_embeddings)

    scored_by_text: dict[str, dict[str, object]] = {}
    for jd_index, jd_chunk in enumerate(matchable_chunks):
        scored_by_text[jd_chunk.text] = _best_resume_match_payload(jd_chunk, resume_chunks, similarity_matrix[jd_index])

    matches: list[dict[str, object]] = []
    for jd_chunk in jd_requirement_chunks:
        if not jd_chunk.matchable:
            matches.append(_non_matchable_payload(jd_chunk))
        else:
            matches.append(scored_by_text.get(jd_chunk.text, _no_evidence_payload(jd_chunk, 0.0, 0.0)))

    matched = [item for item in matches if item.get("matchable") and item["band"] == "strong"]
    partial = [item for item in matches if item.get("matchable") and item["band"] == "partial"]
    missing = [item for item in matches if item.get("matchable") and item["band"] == "weak"]
    scored_matches = [item for item in matches if item.get("matchable")]
    semantic_coverage = round(
        sum(int(item.get("semantic_score", 0)) for item in scored_matches) / len(scored_matches)
    ) if scored_matches else 0

    return SemanticMatcherResult(
        semantic_coverage=max(0, min(100, semantic_coverage)),
        matched_concepts=_concept_payloads(matched),
        partial_concepts=_concept_payloads(partial),
        missing_concepts=_concept_payloads(missing),
        jd_to_resume_matches=matches,
        confidence_factors=_confidence_factors(jd_requirement_chunks, resume_chunks, matches),
        model_name=model_name,
        model_available=model_available,
    )


def _best_resume_match_payload(
    jd_chunk: JDRequirementChunk,
    resume_chunks: list[ResumeSemanticChunk],
    similarities: Any,
) -> dict[str, object]:
    candidates: list[tuple[float, float, int, ResumeSemanticChunk]] = []
    for resume_index, resume_chunk in enumerate(resume_chunks):
        raw_similarity = float(similarities[resume_index])
        adjusted_similarity = _adjust_similarity(jd_chunk.text, resume_chunk, raw_similarity)
        candidates.append((adjusted_similarity, SECTION_WEIGHTS.get(resume_chunk.section, 0.0), resume_index, resume_chunk))
    adjusted_similarity, _, best_index, resume_chunk = max(candidates, key=lambda item: (item[0], item[1], -item[2]))
    raw_similarity = float(similarities[best_index])
    band = _band_for_similarity(adjusted_similarity)
    semantic_score = _score_for_similarity(adjusted_similarity)
    if adjusted_similarity < PARTIAL_MATCH_THRESHOLD:
        return _no_evidence_payload(jd_chunk, adjusted_similarity, raw_similarity)
    return {
        "jd_text": jd_chunk.text,
        "jd_type": jd_chunk.jd_type,
        "matchable": True,
        "match": {
            "text": resume_chunk.text,
            "section": resume_chunk.section,
            "similarity": round(adjusted_similarity, 4),
            "band": band,
        },
        "best_resume_text": resume_chunk.text,
        "resume_section": resume_chunk.section,
        "similarity": round(adjusted_similarity, 4),
        "raw_similarity": round(raw_similarity, 4),
        "section_weight": SECTION_WEIGHTS.get(resume_chunk.section, 0.0),
        "semantic_score": semantic_score,
        "band": band,
        "reason": None,
    }


def _non_matchable_payload(jd_chunk: JDRequirementChunk) -> dict[str, object]:
    return {
        "jd_text": jd_chunk.text,
        "jd_type": jd_chunk.jd_type,
        "matchable": False,
        "match": None,
        "best_resume_text": "",
        "resume_section": "",
        "similarity": 0.0,
        "raw_similarity": 0.0,
        "section_weight": 0.0,
        "semantic_score": None,
        "band": "not_applicable",
        "reason": NOT_APPLICABLE_REASON,
    }


def _no_evidence_payload(jd_chunk: JDRequirementChunk, similarity: float, raw_similarity: float) -> dict[str, object]:
    return {
        "jd_text": jd_chunk.text,
        "jd_type": jd_chunk.jd_type,
        "matchable": True,
        "match": None,
        "best_resume_text": NO_EVIDENCE_REASON,
        "resume_section": "",
        "similarity": round(similarity, 4),
        "raw_similarity": round(raw_similarity, 4),
        "section_weight": 0.0,
        "semantic_score": _score_for_similarity(similarity),
        "band": "weak",
        "reason": NO_EVIDENCE_REASON,
    }


def _score_for_similarity(similarity: float) -> int:
    if similarity >= STRONG_MATCH_THRESHOLD:
        return round(80 + ((similarity - STRONG_MATCH_THRESHOLD) / (1 - STRONG_MATCH_THRESHOLD)) * 20)
    if similarity >= PARTIAL_MATCH_THRESHOLD:
        return round(50 + ((similarity - PARTIAL_MATCH_THRESHOLD) / (STRONG_MATCH_THRESHOLD - PARTIAL_MATCH_THRESHOLD)) * 30)
    return round(min(30.0, (similarity / PARTIAL_MATCH_THRESHOLD) * 30)) if similarity > 0 else 0


def _should_use_hf_model() -> bool:
    engine = os.getenv(SEMANTIC_ENGINE_ENV, "auto").strip().lower()
    if engine in {"0", "false", "off", "fallback", "tfidf", "local"}:
        return False
    if engine in {"1", "true", "on", "hf", "huggingface", "sentence-transformer"}:
        return True

    if _is_render_runtime():
        return False

    memory_limit_mb = _memory_limit_mb()
    if memory_limit_mb is not None and memory_limit_mb < MIN_HF_MEMORY_MB:
        return False
    return True


def _is_render_runtime() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "RENDER",
            "RENDER_SERVICE_ID",
            "RENDER_SERVICE_NAME",
            "RENDER_EXTERNAL_URL",
        )
    )


def _memory_limit_mb() -> int | None:
    """Best-effort Linux cgroup memory limit detection for hosted runtimes."""
    for path in (
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    ):
        try:
            raw_value = open(path, encoding="utf-8").read().strip()
        except OSError:
            continue
        if not raw_value or raw_value == "max":
            continue
        try:
            limit_bytes = int(raw_value)
        except ValueError:
            continue
        if limit_bytes <= 0:
            continue
        # Some hosts expose a huge sentinel value when there is no real limit.
        if limit_bytes > 10**15:
            continue
        return limit_bytes // (1024 * 1024)
    return None


def parse_job_requirements(job: JobDescriptionAnalysis) -> list[str]:
    return [chunk.text for chunk in parse_job_requirement_chunks(job) if chunk.matchable]


def parse_job_requirement_chunks(job: JobDescriptionAnalysis) -> list[JDRequirementChunk]:
    lines = [*getattr(job, "requirement_lines", []), *job.responsibility_phrases, *job.action_phrases]
    requirements: list[JDRequirementChunk] = []
    for line in lines:
        cleaned = clean_phrase(_strip_marker(line))
        if len(cleaned.split()) < 3:
            continue
        for fragment in _split_requirement(cleaned):
            if _is_low_value_heading(fragment):
                continue
            jd_type = classify_jd_line(fragment)
            if jd_type == "tools/tech":
                requirements.extend(_tool_chunks(fragment, jd_type))
            else:
                requirements.append(JDRequirementChunk(text=fragment, jd_type=jd_type))

    if not requirements:
        requirements = [
            JDRequirementChunk(text=f"Experience with {term}", jd_type="tools/tech")
            for term in dedupe_preserve_order([*job.required_skills, *job.tools])[:10]
        ]
    return _dedupe_requirement_chunks(requirements)[:18]


def classify_jd_line(text: str) -> str:
    lowered = normalize_text(text)
    known_terms = extract_known_terms(text, categories={"hard_skill", "soft_skill"})
    if _line_matches_any(lowered, ("notice period", "immediate joiner", "joiners required", "days joiner", "days joiners", "serving notice")):
        return "notice_period"
    if _line_matches_any(lowered, ("job location", "location:", "located in", "based in", "relocation")):
        return "location"
    if _line_matches_any(lowered, ("work mode", "hybrid", "remote", "onsite", "on-site", "work from office", "wfo")):
        return "work_mode"
    if _line_matches_any(lowered, ("degree", "bachelor", "master", "phd", "b.tech", "m.tech", "certification", "license")):
        return "education"
    if _line_matches_any(lowered, ("about us", "about the company", "benefits", "salary", "equal opportunity", "company overview")):
        return "other"
    if re.search(r"\b\d+\s*(?:\+|plus)?\s*(?:years?|yrs?)\b", lowered) or lowered.startswith(("exp:", "experience:")):
        return "experience"
    if _normalized_action_word(lowered):
        return "responsibility"
    if known_terms and _line_matches_any(lowered, ("technical skill", "tech stack", "tools", "technologies", "mandatory skill", "skills:", "skill:")):
        return "tools/tech"
    if known_terms:
        return "skills"
    if _line_matches_any(lowered, ("responsibilities", "what you will do", "what you ll do", "you will")):
        return "responsibility"
    return "other"


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
    action_overlap = bool(_normalized_action_word(jd_text) and _normalized_action_word(resume_chunk.text))
    jd_tools = _known_terms(jd_text)
    resume_tools = _known_terms(resume_chunk.text)
    tool_matches = [tool for tool in jd_tools if tool in resume_tools]

    adjusted = raw_similarity + (section_weight * 0.12)
    if concept_overlap or alias_overlap:
        if resume_chunk.section in {"experience", "projects"}:
            adjusted += 0.10
        elif resume_chunk.section == "skills":
            adjusted += 0.04
        elif resume_chunk.section == "summary":
            adjusted += 0.01
    if jd_tools:
        if not tool_matches:
            adjusted = min(adjusted * 0.45, 0.55)
        else:
            coverage = len(tool_matches) / len(jd_tools)
            adjusted += 0.05 * coverage
            if coverage < 1:
                adjusted -= 0.12 * (1 - coverage)
            if coverage >= 0.5 and resume_chunk.section in {"experience", "projects", "skills"}:
                adjusted = max(adjusted, PARTIAL_MATCH_THRESHOLD)
    if not (concept_overlap or alias_overlap or action_overlap or tool_matches):
        adjusted = min(adjusted, PARTIAL_MATCH_THRESHOLD - 0.01)
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
            "jd_type": item.get("jd_type", ""),
            "best_resume_text": item["best_resume_text"],
            "resume_section": item["resume_section"],
            "similarity": item["similarity"],
            "semantic_score": item.get("semantic_score", 0),
            "band": item["band"],
            "match": item.get("match"),
            "reason": item.get("reason"),
        }
        for item in matches
    ]


def _confidence_factors(
    jd_chunks: list[JDRequirementChunk],
    resume_chunks: list[ResumeSemanticChunk],
    matches: list[dict[str, object]],
) -> dict[str, float]:
    matchable_count = sum(1 for chunk in jd_chunks if chunk.matchable)
    jd_parse_quality = min(1.0, 0.35 + matchable_count * 0.08)
    section_count = len({chunk.section for chunk in resume_chunks})
    evidence_sections = {str(item["resume_section"]) for item in matches if item["band"] in {"strong", "partial"}}
    resume_parse_quality = min(1.0, 0.30 + section_count * 0.12 + min(len(resume_chunks), 12) * 0.025)
    evidence_coverage = len(evidence_sections & {"experience", "projects", "skills"}) / 3
    scored_matches = [item for item in matches if item.get("matchable")]
    semantic_coverage = (
        sum(int(item.get("semantic_score", 0)) for item in scored_matches) / (len(scored_matches) * 100)
        if scored_matches
        else 0.0
    )
    return {
        "jd_parse_quality": round(jd_parse_quality, 2),
        "resume_parse_quality": round(resume_parse_quality, 2),
        "evidence_coverage": round(evidence_coverage, 2),
        "semantic_coverage": round(semantic_coverage, 2),
    }


def _empty_result(jd_chunks: list[JDRequirementChunk], resume_chunks: list[ResumeSemanticChunk]) -> SemanticMatcherResult:
    non_matchable_matches = [_non_matchable_payload(chunk) for chunk in jd_chunks if not chunk.matchable]
    return SemanticMatcherResult(
        semantic_coverage=0,
        matched_concepts=[],
        partial_concepts=[],
        missing_concepts=[],
        jd_to_resume_matches=non_matchable_matches,
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


def _known_terms(text: str) -> list[str]:
    return extract_known_terms(_expand_aliases(text), categories={"hard_skill", "soft_skill"})


def _tool_chunks(text: str, jd_type: str) -> list[JDRequirementChunk]:
    tools = _known_terms(text)
    if len(tools) < 2:
        return [JDRequirementChunk(text=text, jd_type=jd_type)]
    return [JDRequirementChunk(text=f"Experience with {tool}", jd_type=jd_type) for tool in tools]


def _dedupe_requirement_chunks(chunks: list[JDRequirementChunk]) -> list[JDRequirementChunk]:
    seen: set[tuple[str, str]] = set()
    output: list[JDRequirementChunk] = []
    for chunk in chunks:
        key = (normalize_text(chunk.text), chunk.jd_type)
        if key in seen:
            continue
        seen.add(key)
        output.append(chunk)
    return output


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


def _line_matches_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalized_action_word(text: str) -> str | None:
    tokens = set(tokenize(text))
    action_groups = {
        "analyze": {"analyze", "analysis", "evaluate", "interpret", "measure", "research"},
        "build": {"build", "built", "develop", "deliver", "implement", "create", "ship", "launch"},
        "collaborate": {"collaborate", "partner", "communicate", "coordinate", "align", "work"},
        "deploy": {"deploy", "release", "publish", "containerize"},
        "lead": {"lead", "own", "manage", "mentor", "drive"},
        "optimize": {"optimize", "optimise", "improve", "tune", "reduce", "increase", "scale", "enhance"},
    }
    for canonical, aliases in action_groups.items():
        if canonical in tokens or aliases & tokens:
            return canonical
    return None


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

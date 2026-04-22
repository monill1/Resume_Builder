from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache

from .ats_evidence import score_bullet_quality
from .ats_normalization import (
    KEYWORD_RULES,
    STOPWORDS,
    clean_phrase,
    dedupe_preserve_order,
    normalize_text,
    split_sentences,
    tokenize,
)
from .job_description import JobDescriptionAnalysis
from .resume_parser import ResumeAnalysis


ACTION_ALIASES = {
    "analyze": {"analyze", "analys", "evaluate", "interpret", "investigate", "measure", "research"},
    "architect": {"architect", "design", "model", "plan"},
    "automate": {"automate", "script", "streamline"},
    "build": {"build", "built", "develop", "deliver", "implement", "create", "ship", "launched", "launch"},
    "collaborate": {"collaborate", "collaboration", "partner", "communicate", "communication", "coordinate", "work", "align"},
    "deploy": {"deploy", "release", "publish", "containerize", "orchestrate"},
    "lead": {"lead", "led", "own", "owned", "manage", "mentor", "drive"},
    "maintain": {"maintain", "support", "operate", "monitor", "debug", "troubleshoot"},
    "optimize": {"optimize", "optimise", "improve", "tune", "reduce", "increase", "scale", "enhance"},
    "test": {"test", "validate", "verify", "qa"},
}

OBJECT_ALIASES = {
    "apis": {"api", "apis", "rest", "restful", "endpoint", "endpoints", "service", "services", "backend"},
    "architecture": {"architecture", "system", "systems", "platform", "scalable", "scale"},
    "dashboards": {"dashboard", "dashboards", "report", "reports", "reporting", "visualization", "visualisation", "bi"},
    "data": {"data", "dataset", "datasets", "analytics", "analysis", "insight", "insights"},
    "databases": {"database", "databases", "sql", "postgres", "postgresql", "query", "queries", "schema"},
    "deployment": {"deploy", "deployment", "cloud", "docker", "kubernetes", "ci/cd", "cicd", "pipeline"},
    "models": {"model", "models", "ml", "machine", "learning", "prediction", "classifier", "nlp"},
    "performance": {"performance", "latency", "throughput", "speed", "cost", "reliability", "availability"},
    "pipelines": {"pipeline", "pipelines", "etl", "workflow", "workflows", "airflow", "batch"},
    "stakeholders": {"stakeholder", "stakeholders", "cross-functional", "business", "partner", "partners", "product", "manager", "managers", "team", "teams", "client", "customer"},
}


@dataclass(frozen=True)
class SemanticRequirementMatch:
    job_requirement: str
    matched_resume_bullet: str
    resume_section: str
    semantic_score: int
    match_strength: str
    matched_signals: list[str]


@dataclass(frozen=True)
class ResponsibilityPhrase:
    phrase: str
    action: str | None
    objects: list[str]
    tools: list[str]
    outcomes: list[str]


@dataclass(frozen=True)
class ResponsibilityMatch:
    responsibility: str
    matched_resume_bullet: str
    resume_section: str
    score: int
    action_match: bool
    object_matches: list[str]
    tool_matches: list[str]
    outcome_match: bool


@dataclass(frozen=True)
class SemanticMatchResult:
    requirement_matches: list[SemanticRequirementMatch]
    matched_requirements: list[dict[str, object]]
    weakly_matched_requirements: list[dict[str, object]]
    unmatched_requirements: list[dict[str, object]]
    responsibility_phrases: list[ResponsibilityPhrase]
    matched_responsibilities: list[dict[str, object]]
    missing_responsibilities: list[dict[str, object]]
    semantic_requirement_match_score: int
    responsibility_match_score: int
    semantic_coverage: float
    strong_bullet_match_count: int


def match_semantic_requirements(job: JobDescriptionAnalysis, resume: ResumeAnalysis) -> SemanticMatchResult:
    requirements = extract_requirement_lines(job)
    resume_bullets = extract_resume_bullets(resume)
    requirement_matches = [_best_requirement_match(requirement, resume_bullets) for requirement in requirements]
    responsibility_phrases = extract_responsibility_phrases(job)
    responsibility_matches = [_best_responsibility_match(phrase, resume_bullets) for phrase in responsibility_phrases]

    matched_requirements: list[dict[str, object]] = []
    weakly_matched: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    for match in requirement_matches:
        payload = _requirement_payload(match)
        if match.semantic_score >= 66:
            matched_requirements.append(payload)
        elif match.semantic_score >= 44:
            weakly_matched.append(payload)
        else:
            unmatched.append(payload)

    matched_responsibilities: list[dict[str, object]] = []
    missing_responsibilities: list[dict[str, object]] = []
    for match in responsibility_matches:
        payload = _responsibility_payload(match)
        if match.score >= 62:
            matched_responsibilities.append(payload)
        else:
            missing_responsibilities.append(
                {
                    "responsibility": match.responsibility,
                    "best_resume_bullet": match.matched_resume_bullet,
                    "best_score": match.score,
                    "details": "No experience or project bullet strongly supports this responsibility.",
                }
            )

    semantic_score = _average_requirement_score(requirement_matches)
    responsibility_score = _average_responsibility_score(responsibility_matches)
    strong_count = sum(1 for match in requirement_matches if match.semantic_score >= 70)
    semantic_coverage = round(
        sum(1 for match in requirement_matches if match.semantic_score >= 55) / len(requirement_matches),
        2,
    ) if requirement_matches else 0.0

    return SemanticMatchResult(
        requirement_matches=requirement_matches,
        matched_requirements=matched_requirements[:12],
        weakly_matched_requirements=weakly_matched[:12],
        unmatched_requirements=unmatched[:12],
        responsibility_phrases=responsibility_phrases,
        matched_responsibilities=matched_responsibilities[:12],
        missing_responsibilities=missing_responsibilities[:12],
        semantic_requirement_match_score=semantic_score,
        responsibility_match_score=responsibility_score,
        semantic_coverage=semantic_coverage,
        strong_bullet_match_count=strong_count,
    )


def extract_requirement_lines(job: JobDescriptionAnalysis) -> list[str]:
    lines = [*getattr(job, "requirement_lines", []), *job.responsibility_phrases, *job.action_phrases]
    cleaned: list[str] = []
    for line in lines:
        line = clean_phrase(_strip_leading_marker(line))
        lowered = normalize_text(line)
        if len(line.split()) < 3:
            continue
        if any(marker in lowered for marker in ("degree", "bachelor", "master", "phd", "certification", "license", "authorized to work", "visa", "sponsorship")):
            continue
        if lowered in {"requirements", "required qualifications", "responsibilities", "preferred qualifications"}:
            continue
        cleaned.extend(_split_atomic_line(line))

    if not cleaned:
        cleaned = [f"Experience with {term}" for term in dedupe_preserve_order([*job.required_skills, *job.tools])[:8]]
    return dedupe_preserve_order(cleaned)[:14]


def extract_resume_bullets(resume: ResumeAnalysis) -> list[dict[str, str]]:
    bullets: list[dict[str, str]] = []
    for section in ("experience", "projects"):
        for line in resume.section_lines.get(section, []):
            cleaned = clean_phrase(line)
            if not _looks_like_resume_bullet(cleaned):
                continue
            bullets.append({"section": section, "text": cleaned})
    return bullets


def extract_responsibility_phrases(job: JobDescriptionAnalysis) -> list[ResponsibilityPhrase]:
    phrases = extract_requirement_lines(job)
    responsibility_phrases: list[ResponsibilityPhrase] = []
    for phrase in phrases:
        action = _normalized_action(phrase)
        objects = _objects_for_text(phrase)
        tools = list(_known_terms_cached(phrase))
        outcomes = _outcomes_for_text(phrase)
        lowered = normalize_text(phrase)
        if not action and lowered.startswith(("experience with", "strong experience", "proficiency", "skilled in")):
            continue
        if action or objects:
            responsibility_phrases.append(
                ResponsibilityPhrase(
                    phrase=phrase,
                    action=action,
                    objects=objects,
                    tools=tools,
                    outcomes=outcomes,
                )
            )
    return responsibility_phrases[:12]


def _best_requirement_match(requirement: str, bullets: list[dict[str, str]]) -> SemanticRequirementMatch:
    if not bullets:
        return SemanticRequirementMatch(
            job_requirement=requirement,
            matched_resume_bullet="",
            resume_section="",
            semantic_score=0,
            match_strength="missing",
            matched_signals=[],
        )
    scored = [_score_requirement_pair(requirement, bullet["text"], bullet["section"], [requirement, *[item["text"] for item in bullets]]) for bullet in bullets]
    return max(scored, key=lambda item: item.semantic_score)


def _score_requirement_pair(requirement: str, bullet: str, section: str, corpus: list[str]) -> SemanticRequirementMatch:
    req_tokens = _content_tokens(requirement)
    bullet_tokens = _content_tokens(bullet)
    coverage = len(set(req_tokens) & set(bullet_tokens)) / len(set(req_tokens)) if req_tokens else 0.0
    jaccard = _jaccard(req_tokens, bullet_tokens)
    tfidf = _tfidf_cosine(requirement, bullet, corpus)
    ngram = _ngram_similarity(requirement, bullet)
    action_score, action_signal = _action_similarity(requirement, bullet)
    object_score, object_signals = _object_similarity(requirement, bullet)
    tool_score, tool_signals = _tool_similarity(requirement, bullet)
    outcome_score = _outcome_similarity(requirement, bullet)
    quality, quality_signals = score_bullet_quality(bullet, has_term=bool(tool_signals))

    combined = (
        0.24 * tfidf
        + 0.17 * coverage
        + 0.08 * jaccard
        + 0.09 * ngram
        + 0.18 * action_score
        + 0.14 * object_score
        + 0.10 * tool_score
    )
    if action_score >= 0.85 and (object_score >= 0.45 or tool_score >= 0.45):
        combined += 0.14
    if tool_score >= 0.99 and (object_score >= 0.45 or quality >= 55):
        combined += 0.10
    if outcome_score and ("metric" in quality_signals or "context" in quality_signals):
        combined += 0.04
    if section == "experience":
        combined += 0.02
    if quality >= 70:
        combined += 0.03

    score = round(max(0.0, min(1.0, combined)) * 100)
    if normalize_text(requirement).startswith(("experience with", "strong experience", "proficiency", "skilled in")) and tool_score >= 0.99:
        score = max(score, 68 if quality >= 55 else 58)
    signals = []
    if tfidf >= 0.42 or coverage >= 0.5:
        signals.append("semantic_terms")
    if action_signal:
        signals.append("action")
    if object_signals:
        signals.extend(f"object:{item}" for item in object_signals[:3])
    if tool_signals:
        signals.extend(f"tool:{item}" for item in tool_signals[:3])
    if outcome_score:
        signals.append("outcome")
    if "metric" in quality_signals:
        signals.append("metric")

    return SemanticRequirementMatch(
        job_requirement=requirement,
        matched_resume_bullet=bullet,
        resume_section=section,
        semantic_score=score,
        match_strength=_strength_label(score),
        matched_signals=dedupe_preserve_order(signals),
    )


def _best_responsibility_match(phrase: ResponsibilityPhrase, bullets: list[dict[str, str]]) -> ResponsibilityMatch:
    if not bullets:
        return ResponsibilityMatch(
            responsibility=phrase.phrase,
            matched_resume_bullet="",
            resume_section="",
            score=0,
            action_match=False,
            object_matches=[],
            tool_matches=[],
            outcome_match=False,
        )
    scored = [_score_responsibility_pair(phrase, bullet["text"], bullet["section"]) for bullet in bullets]
    return max(scored, key=lambda item: item.score)


def _score_responsibility_pair(phrase: ResponsibilityPhrase, bullet: str, section: str) -> ResponsibilityMatch:
    bullet_action = _normalized_action(bullet)
    bullet_objects = _objects_for_text(bullet)
    bullet_tools = list(_known_terms_cached(bullet))
    bullet_outcomes = _outcomes_for_text(bullet)

    action_match = bool(phrase.action and bullet_action and phrase.action == bullet_action)
    related_action = bool(phrase.action and bullet_action and _related_actions(phrase.action, bullet_action))
    object_matches = [item for item in phrase.objects if item in bullet_objects]
    tool_matches = [item for item in phrase.tools if item in bullet_tools]
    outcome_match = bool(set(phrase.outcomes) & set(bullet_outcomes))
    token_score = _token_phrase_similarity(phrase.phrase, bullet)

    score = 100 * (
        0.26 * (1.0 if action_match else 0.65 if related_action else 0.0)
        + 0.28 * (len(object_matches) / len(phrase.objects) if phrase.objects else _object_similarity(phrase.phrase, bullet)[0] * 0.75)
        + 0.18 * (len(tool_matches) / len(phrase.tools) if phrase.tools else _tool_similarity(phrase.phrase, bullet)[0] * 0.7)
        + 0.18 * token_score
        + 0.10 * (1.0 if outcome_match else 0.0)
    )
    if action_match and (object_matches or tool_matches):
        score += 8
    if section == "experience":
        score += 3
    return ResponsibilityMatch(
        responsibility=phrase.phrase,
        matched_resume_bullet=bullet,
        resume_section=section,
        score=round(max(0, min(100, score))),
        action_match=action_match or related_action,
        object_matches=object_matches,
        tool_matches=tool_matches,
        outcome_match=outcome_match,
    )


def _content_tokens(text: str) -> list[str]:
    return list(_content_tokens_cached(text))


@lru_cache(maxsize=1024)
def _content_tokens_cached(text: str) -> tuple[str, ...]:
    return tuple(_normalize_semantic_token(token) for token in tokenize(text) if token not in STOPWORDS and len(token) > 2 and not token.isdigit())


def _normalize_semantic_token(token: str) -> str:
    for canonical, aliases in ACTION_ALIASES.items():
        if token in aliases:
            return canonical
    for canonical, aliases in OBJECT_ALIASES.items():
        if token in aliases:
            return canonical
    return token


def _tfidf_cosine(left: str, right: str, corpus: list[str]) -> float:
    docs = [_content_tokens(item) for item in corpus[:18] if item]
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    doc_count = max(1, len(docs))
    document_frequency: dict[str, int] = {}
    for tokens in docs:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    def vector(tokens: list[str]) -> dict[str, float]:
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return {
            token: count * (math.log((doc_count + 1) / (document_frequency.get(token, 0) + 1)) + 1)
            for token, count in counts.items()
        }

    left_vector = vector(left_tokens)
    right_vector = vector(right_tokens)
    numerator = sum(value * right_vector.get(token, 0.0) for token, value in left_vector.items())
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    return len(left_set & right_set) / len(left_set | right_set) if left_set and right_set else 0.0


def _ngram_similarity(left: str, right: str) -> float:
    left_grams = _word_ngrams(_content_tokens(left), 2)
    right_grams = _word_ngrams(_content_tokens(right), 2)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def _word_ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _action_similarity(left: str, right: str) -> tuple[float, bool]:
    left_action = _normalized_action(left)
    right_action = _normalized_action(right)
    if not left_action or not right_action:
        return 0.0, False
    if left_action == right_action:
        return 1.0, True
    if _related_actions(left_action, right_action):
        return 0.68, True
    return 0.0, False


def _object_similarity(left: str, right: str) -> tuple[float, list[str]]:
    left_objects = _objects_for_text(left)
    right_objects = _objects_for_text(right)
    if not left_objects or not right_objects:
        return 0.0, []
    matches = [item for item in left_objects if item in right_objects]
    return len(matches) / len(left_objects), matches


def _tool_similarity(left: str, right: str) -> tuple[float, list[str]]:
    left_tools = list(_known_terms_cached(left))
    right_tools = list(_known_terms_cached(right))
    if not left_tools or not right_tools:
        return 0.0, []
    matches = [item for item in left_tools if item in right_tools]
    return len(matches) / len(left_tools), matches


def _outcome_similarity(left: str, right: str) -> bool:
    return bool(set(_outcomes_for_text(left)) & set(_outcomes_for_text(right)))


def _token_phrase_similarity(left: str, right: str) -> float:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    coverage = len(set(left_tokens) & set(right_tokens)) / len(set(left_tokens)) if left_tokens else 0.0
    return max(coverage, _jaccard(left_tokens, right_tokens))


def _normalized_action(text: str) -> str | None:
    return _normalized_action_cached(text)


@lru_cache(maxsize=1024)
def _normalized_action_cached(text: str) -> str | None:
    ordered_tokens = _content_tokens(text)
    for token in ordered_tokens:
        if token in ACTION_ALIASES:
            return token
    tokens = set(ordered_tokens)
    for canonical, aliases in ACTION_ALIASES.items():
        if canonical in tokens or aliases & tokens:
            return canonical
    return None


def _objects_for_text(text: str) -> list[str]:
    return list(_objects_for_text_cached(text))


@lru_cache(maxsize=1024)
def _objects_for_text_cached(text: str) -> tuple[str, ...]:
    tokens = set(_content_tokens(text))
    matches = [canonical for canonical, aliases in OBJECT_ALIASES.items() if canonical in tokens or aliases & tokens]
    return tuple(dedupe_preserve_order(matches))


def _outcomes_for_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    outcomes = []
    if re.search(r"\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?(?:x|k|m|b)\b|\b\d+\b", normalized):
        outcomes.append("metric")
    if any(token in normalized for token in ("performance", "latency", "cost", "revenue", "accuracy", "efficiency")):
        outcomes.append("business_or_system_outcome")
    if any(token in normalized for token in ("customer", "stakeholder", "user", "business", "sales", "reporting")):
        outcomes.append("user_or_business_context")
    return outcomes


@lru_cache(maxsize=1024)
def _known_terms_cached(text: str) -> tuple[str, ...]:
    normalized = f" {normalize_text(text).replace('-', ' ')} "
    found: list[str] = []
    for rule in KEYWORD_RULES:
        if rule.category not in {"hard_skill", "soft_skill"}:
            continue
        for alias in (rule.canonical, *rule.aliases):
            alias_norm = normalize_text(alias)
            if alias_norm and f" {alias_norm} " in normalized:
                found.append(rule.canonical)
                break
    return tuple(dedupe_preserve_order(found))


def _related_actions(left: str, right: str) -> bool:
    related = {
        "build": {"architect", "deploy", "maintain"},
        "architect": {"build", "optimize"},
        "optimize": {"maintain", "analyze", "architect"},
        "analyze": {"optimize", "build"},
        "deploy": {"build", "maintain"},
        "collaborate": {"lead"},
        "lead": {"collaborate"},
    }
    return right in related.get(left, set())


def _average_requirement_score(matches: list[SemanticRequirementMatch]) -> int:
    if not matches:
        return 55
    weighted = 0.0
    for match in matches:
        if match.match_strength == "strong":
            weighted += match.semantic_score
        elif match.match_strength == "partial":
            weighted += match.semantic_score * 0.92
        else:
            weighted += match.semantic_score * 0.82
    return round(weighted / len(matches))


def _average_responsibility_score(matches: list[ResponsibilityMatch]) -> int:
    if not matches:
        return 55
    return round(sum(match.score for match in matches) / len(matches))


def _strength_label(score: int) -> str:
    if score >= 66:
        return "strong"
    if score >= 44:
        return "partial"
    return "missing"


def _requirement_payload(match: SemanticRequirementMatch) -> dict[str, object]:
    return {
        "job_requirement": match.job_requirement,
        "matched_resume_bullet": match.matched_resume_bullet,
        "resume_section": match.resume_section,
        "semantic_score": match.semantic_score,
        "match_strength": match.match_strength,
        "matched_signals": match.matched_signals,
    }


def _responsibility_payload(match: ResponsibilityMatch) -> dict[str, object]:
    return {
        "responsibility": match.responsibility,
        "matched_resume_bullet": match.matched_resume_bullet,
        "resume_section": match.resume_section,
        "score": match.score,
        "action_match": match.action_match,
        "object_matches": match.object_matches,
        "tool_matches": match.tool_matches,
        "outcome_match": match.outcome_match,
    }


def _split_atomic_line(line: str) -> list[str]:
    tools = list(_known_terms_cached(line))
    lowered = normalize_text(line)
    if len(tools) >= 3 and not _normalized_action(line) and any(marker in lowered for marker in ("experience with", "strong experience", "proficiency", "skilled in")):
        return [f"Experience with {tool}" for tool in tools]
    fragments = split_sentences(line)
    output: list[str] = []
    for fragment in fragments or [line]:
        pieces = re.split(r"\s+(?:and|;)\s+(?=(?:build|develop|design|create|analyze|deploy|optimize|collaborate|lead|own|manage)\b)", fragment, flags=re.IGNORECASE)
        output.extend(clean_phrase(piece) for piece in pieces if clean_phrase(piece))
    return output


def _strip_leading_marker(text: str) -> str:
    return re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", text or "")


def _looks_like_resume_bullet(line: str) -> bool:
    if len(line.split()) < 5:
        return False
    if " | " in line and not re.search(r"\b(built|developed|created|optimized|analyzed|deployed|led|implemented|designed)\b", line, re.IGNORECASE):
        return False
    return True

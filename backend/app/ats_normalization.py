from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable


STOPWORDS = {
    "a",
    "about",
    "across",
    "after",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "have",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "you",
    "your",
}
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#./-]*")


@dataclass(frozen=True)
class KeywordRule:
    canonical: str
    aliases: tuple[str, ...]
    category: str


KEYWORD_RULES = [
    KeywordRule("Python", ("python", "python3"), "hard_skill"),
    KeywordRule("SQL", ("sql", "structured query language"), "hard_skill"),
    KeywordRule("PostgreSQL", ("postgresql", "postgres", "postgre sql"), "hard_skill"),
    KeywordRule("FastAPI", ("fastapi",), "hard_skill"),
    KeywordRule("Django", ("django",), "hard_skill"),
    KeywordRule("Flask", ("flask",), "hard_skill"),
    KeywordRule("REST APIs", ("rest api", "rest apis", "restful api", "restful apis", "api development"), "hard_skill"),
    KeywordRule("GraphQL", ("graphql",), "hard_skill"),
    KeywordRule("Docker", ("docker", "containerization"), "hard_skill"),
    KeywordRule("Kubernetes", ("kubernetes", "k8s"), "hard_skill"),
    KeywordRule("AWS", ("aws", "amazon web services"), "hard_skill"),
    KeywordRule("GCP", ("gcp", "google cloud platform"), "hard_skill"),
    KeywordRule("Azure", ("azure", "microsoft azure"), "hard_skill"),
    KeywordRule("Git", ("git", "github", "gitlab"), "hard_skill"),
    KeywordRule("CI/CD", ("ci/cd", "continuous integration", "continuous delivery", "continuous deployment"), "hard_skill"),
    KeywordRule("Linux", ("linux",), "hard_skill"),
    KeywordRule("Redis", ("redis",), "hard_skill"),
    KeywordRule("Kafka", ("kafka", "apache kafka"), "hard_skill"),
    KeywordRule("Airflow", ("airflow", "apache airflow"), "hard_skill"),
    KeywordRule("dbt", ("dbt",), "hard_skill"),
    KeywordRule("Snowflake", ("snowflake",), "hard_skill"),
    KeywordRule("BigQuery", ("bigquery", "big query"), "hard_skill"),
    KeywordRule("Pandas", ("pandas",), "hard_skill"),
    KeywordRule("NumPy", ("numpy",), "hard_skill"),
    KeywordRule("Scikit-learn", ("scikit-learn", "sklearn"), "hard_skill"),
    KeywordRule("TensorFlow", ("tensorflow",), "hard_skill"),
    KeywordRule("PyTorch", ("pytorch",), "hard_skill"),
    KeywordRule("Machine Learning", ("machine learning", "ml"), "hard_skill"),
    KeywordRule("Natural Language Processing", ("natural language processing", "nlp"), "hard_skill"),
    KeywordRule("Generative AI", ("generative ai", "gen ai", "large language models", "llms", "llm"), "hard_skill"),
    KeywordRule("Statistics", ("statistics", "statistical analysis", "statistical modeling"), "hard_skill"),
    KeywordRule("A/B Testing", ("a/b testing", "ab testing", "experimentation"), "hard_skill"),
    KeywordRule("Regression Analysis", ("regression analysis", "regression modeling"), "hard_skill"),
    KeywordRule("Excel", ("excel", "microsoft excel"), "hard_skill"),
    KeywordRule("Tableau", ("tableau",), "hard_skill"),
    KeywordRule("Power BI", ("power bi", "powerbi"), "hard_skill"),
    KeywordRule("Looker", ("looker",), "hard_skill"),
    KeywordRule("Mixpanel", ("mixpanel",), "hard_skill"),
    KeywordRule("Amplitude", ("amplitude",), "hard_skill"),
    KeywordRule("Product Analytics", ("product analytics", "product analysis"), "hard_skill"),
    KeywordRule("Data Analysis", ("data analysis", "analytics"), "hard_skill"),
    KeywordRule("Data Visualization", ("data visualization", "dashboarding", "dashboards", "reporting"), "hard_skill"),
    KeywordRule("ETL", ("etl", "elt", "data pipeline", "data pipelines"), "hard_skill"),
    KeywordRule("Data Modeling", ("data modeling", "data modelling"), "hard_skill"),
    KeywordRule("Feature Engineering", ("feature engineering",), "hard_skill"),
    KeywordRule("MLOps", ("mlops", "ml ops"), "hard_skill"),
    KeywordRule("Streamlit", ("streamlit",), "hard_skill"),
    KeywordRule("React", ("react", "react.js"), "hard_skill"),
    KeywordRule("JavaScript", ("javascript",), "hard_skill"),
    KeywordRule("TypeScript", ("typescript",), "hard_skill"),
    KeywordRule("Communication", ("communication", "communicate", "communicating"), "soft_skill"),
    KeywordRule("Stakeholder Management", ("stakeholder management", "stakeholder communication", "cross-functional"), "soft_skill"),
    KeywordRule("Leadership", ("leadership", "lead", "leading"), "soft_skill"),
    KeywordRule("Collaboration", ("collaboration", "collaborative", "collaborated"), "soft_skill"),
    KeywordRule("Problem Solving", ("problem solving", "solve problems", "problem-solver"), "soft_skill"),
    KeywordRule("Mentoring", ("mentoring", "mentor", "coaching"), "soft_skill"),
    KeywordRule("Ownership", ("ownership", "end-to-end ownership"), "soft_skill"),
    KeywordRule("SaaS", ("saas", "software as a service"), "domain"),
    KeywordRule("E-commerce", ("e-commerce", "ecommerce"), "domain"),
    KeywordRule("FinTech", ("fintech", "payments"), "domain"),
    KeywordRule("Healthcare", ("healthcare", "health care"), "domain"),
    KeywordRule("B2B", ("b2b",), "domain"),
    KeywordRule("Consumer Products", ("consumer products", "consumer apps"), "domain"),
    KeywordRule("AWS Certification", ("aws certified", "aws certification"), "certification"),
    KeywordRule("Google Analytics", ("google analytics", "ga4"), "certification"),
]

def normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9+#./\s-]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def split_sentences(text: str) -> list[str]:
    return [segment.strip() for segment in SENTENCE_SPLIT_RE.split(text or "") if segment.strip()]


def tokenize(text: str) -> list[str]:
    return [lemmatize_token(token) for token in TOKEN_RE.findall(normalize_text(text))]


def lemmatize_token(token: str) -> str:
    token = token.lower().strip(".-_/")
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 5:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3 and not token.endswith(("ss", "us")):
        return token[:-1]
    return token


def phrase_key(text: str) -> str:
    return " ".join(token for token in tokenize(text) if token)


def clean_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip(" -:|,.;")).strip()


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = clean_phrase(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def get_keyword_rule(term: str) -> KeywordRule | None:
    if not term:
        return None
    rule = KEYWORD_RULE_BY_CANONICAL.get(term.lower())
    if rule:
        return rule
    return ALIAS_TO_RULE.get(phrase_key(term))


def canonicalize_term(term: str) -> str:
    rule = get_keyword_rule(term)
    return rule.canonical if rule else clean_phrase(term)


def aliases_for(term: str) -> tuple[str, ...]:
    rule = get_keyword_rule(term)
    if rule:
        return (rule.canonical, *rule.aliases)
    cleaned = clean_phrase(term)
    return (cleaned,) if cleaned else tuple()


def classify_term(term: str) -> str:
    rule = get_keyword_rule(term)
    return rule.category if rule else "keyword"


def exact_phrase_present(phrase: str, text: str) -> bool:
    if not phrase or not text:
        return False
    escaped = re.escape(normalize_text(phrase))
    haystack = normalize_text(text)
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", haystack))


def semantic_phrase_present(term: str, text: str) -> bool:
    if not term or not text:
        return False
    normalized_text = phrase_key(text)
    if not normalized_text:
        return False
    term_tokens = [token for token in phrase_key(term).split() if token and token not in STOPWORDS]
    if not term_tokens:
        return False
    if " ".join(term_tokens) in normalized_text:
        return True
    sentence_tokens = [set(tokenize(sentence)) for sentence in split_sentences(text)]
    for token_set in sentence_tokens:
        overlap = sum(1 for token in term_tokens if token in token_set)
        if overlap / len(term_tokens) >= 0.75:
            return True
    return False


def best_match_type(term: str, text: str) -> str | None:
    for alias in aliases_for(term):
        if exact_phrase_present(alias, text):
            return "exact"
    for alias in aliases_for(term):
        if semantic_phrase_present(alias, text):
            return "semantic"
    return None


def extract_known_terms(text: str, *, categories: set[str] | None = None) -> list[str]:
    found: list[str] = []
    for rule in KEYWORD_RULES:
        if categories and rule.category not in categories:
            continue
        if any(best_match_type(alias, text) for alias in (rule.canonical, *rule.aliases)):
            found.append(rule.canonical)
    return dedupe_preserve_order(found)


def similarity_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, phrase_key(left), phrase_key(right)).ratio()


def top_term_frequencies(text: str, *, limit: int = 10, minimum_length: int = 4) -> list[str]:
    counts: dict[str, int] = {}
    for token in tokenize(text):
        if len(token) < minimum_length or token in STOPWORDS or token.isdigit():
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def find_evidence_snippets(text: str, term: str, *, max_hits: int = 2) -> list[str]:
    snippets: list[str] = []
    for sentence in split_sentences(text):
        if best_match_type(term, sentence):
            snippets.append(clean_phrase(sentence))
        if len(snippets) == max_hits:
            break
    return snippets


KEYWORD_RULE_BY_CANONICAL = {rule.canonical.lower(): rule for rule in KEYWORD_RULES}
ALIAS_TO_RULE = {phrase_key(alias): rule for rule in KEYWORD_RULES for alias in (rule.canonical, *rule.aliases)}

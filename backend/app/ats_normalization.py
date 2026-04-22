from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from .rich_text import strip_rich_text


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
    skill_category: str = "general"
    related: tuple[str, ...] = tuple()


KEYWORD_RULES = [
    KeywordRule("Python", ("python", "python3"), "hard_skill", "programming", ("Pandas", "NumPy", "Django", "FastAPI", "Flask")),
    KeywordRule("SQL", ("sql", "structured query language"), "hard_skill", "database", ("PostgreSQL", "database design", "analytics")),
    KeywordRule("PostgreSQL", ("postgresql", "postgres", "postgre sql", "pgsql", "psql"), "hard_skill", "database", ("SQL", "database design")),
    KeywordRule("FastAPI", ("fastapi", "fast api"), "hard_skill", "backend", ("Python", "REST APIs", "API Development", "backend")),
    KeywordRule("Django", ("django",), "hard_skill", "backend", ("Python", "REST APIs", "backend")),
    KeywordRule("Flask", ("flask",), "hard_skill", "backend", ("Python", "REST APIs", "backend")),
    KeywordRule("REST APIs", ("rest api", "rest apis", "restful api", "restful apis", "api development", "api design", "api integration"), "hard_skill", "backend", ("FastAPI", "Django", "Flask", "backend services")),
    KeywordRule("Microservices", ("microservices", "micro services", "service-oriented architecture"), "hard_skill", "backend", ("REST APIs", "Docker", "Kubernetes")),
    KeywordRule("GraphQL", ("graphql",), "hard_skill", "backend", ("API Development",)),
    KeywordRule("Docker", ("docker", "containerization", "containers"), "hard_skill", "devops", ("Kubernetes", "CI/CD")),
    KeywordRule("Kubernetes", ("kubernetes", "k8s"), "hard_skill", "devops", ("Docker", "container orchestration")),
    KeywordRule("AWS", ("aws", "amazon web services", "ec2", "lambda", "s3", "ecs"), "hard_skill", "cloud", ("cloud infrastructure", "Docker")),
    KeywordRule("GCP", ("gcp", "google cloud platform"), "hard_skill", "cloud", ("cloud infrastructure",)),
    KeywordRule("Azure", ("azure", "microsoft azure"), "hard_skill", "cloud", ("cloud infrastructure",)),
    KeywordRule("Git", ("git", "github", "gitlab"), "hard_skill", "tools", ("version control",)),
    KeywordRule("CI/CD", ("ci/cd", "cicd", "continuous integration", "continuous delivery", "continuous deployment", "deployment pipeline"), "hard_skill", "devops", ("Git", "Docker")),
    KeywordRule("Linux", ("linux",), "hard_skill", "platform", ("shell scripting",)),
    KeywordRule("Redis", ("redis", "caching"), "hard_skill", "database", ("cache", "backend performance")),
    KeywordRule("Kafka", ("kafka", "apache kafka", "event streaming"), "hard_skill", "data_platform", ("stream processing", "event-driven")),
    KeywordRule("Airflow", ("airflow", "apache airflow"), "hard_skill", "data_platform", ("data pipelines", "ETL")),
    KeywordRule("dbt", ("dbt",), "hard_skill", "data_platform", ("Data Modeling", "SQL")),
    KeywordRule("Snowflake", ("snowflake",), "hard_skill", "database", ("SQL", "data warehouse")),
    KeywordRule("BigQuery", ("bigquery", "big query"), "hard_skill", "database", ("SQL", "data warehouse")),
    KeywordRule("Pandas", ("pandas",), "hard_skill", "data_analysis", ("Python", "Data Analysis", "NumPy")),
    KeywordRule("NumPy", ("numpy",), "hard_skill", "data_analysis", ("Python", "Pandas")),
    KeywordRule("Scikit-learn", ("scikit-learn", "sklearn", "scikit learn"), "hard_skill", "machine_learning", ("Python", "Machine Learning")),
    KeywordRule("TensorFlow", ("tensorflow",), "hard_skill", "machine_learning", ("Machine Learning", "deep learning")),
    KeywordRule("PyTorch", ("pytorch",), "hard_skill", "machine_learning", ("Machine Learning", "deep learning")),
    KeywordRule("Machine Learning", ("machine learning", "machine-learning", "ml", "ai/ml", "ai ml", "aiml"), "hard_skill", "machine_learning", ("Scikit-learn", "PyTorch", "TensorFlow", "modeling")),
    KeywordRule("Natural Language Processing", ("natural language processing", "natural-language processing", "nlp"), "hard_skill", "machine_learning", ("Machine Learning", "text classification", "transformers")),
    KeywordRule("Generative AI", ("generative ai", "gen ai", "genai", "gen-ai", "large language model", "large language models", "llms", "llm"), "hard_skill", "ai", ("Prompt Engineering", "Natural Language Processing", "transformers")),
    KeywordRule("Agentic AI", ("agentic ai", "agenticai", "ai agents", "agent workflows", "autonomous agents"), "hard_skill", "ai", ("Generative AI", "LangChain", "AutoGen", "LangGraph", "LlamaIndex")),
    KeywordRule("LangChain", ("langchain", "lang chain"), "hard_skill", "ai", ("Generative AI", "Agentic AI", "LangGraph")),
    KeywordRule("LangGraph", ("langgraph", "lang graph"), "hard_skill", "ai", ("LangChain", "Agentic AI")),
    KeywordRule("LlamaIndex", ("llamaindex", "llama index"), "hard_skill", "ai", ("Generative AI", "Agentic AI")),
    KeywordRule("AutoGen", ("autogen", "auto gen", "microsoft autogen"), "hard_skill", "ai", ("Generative AI", "Agentic AI")),
    KeywordRule("Vector DB", ("vector db", "vector database", "vector databases", "pinecone", "weaviate", "chroma", "faiss", "qdrant"), "hard_skill", "ai", ("Generative AI", "Machine Learning", "Data Modeling")),
    KeywordRule("Prompt Engineering", ("prompt engineering", "prompt design", "prompting"), "hard_skill", "ai", ("Generative AI", "LLM")),
    KeywordRule("Statistics", ("statistics", "statistical analysis", "statistical modeling"), "hard_skill", "analytics", ("A/B Testing", "Regression Analysis")),
    KeywordRule("A/B Testing", ("a/b testing", "ab testing", "experimentation", "experiment design"), "hard_skill", "analytics", ("Statistics", "Product Analytics")),
    KeywordRule("Regression Analysis", ("regression analysis", "regression modeling"), "hard_skill", "analytics", ("Statistics",)),
    KeywordRule("Excel", ("excel", "microsoft excel"), "hard_skill", "analytics", ("reporting",)),
    KeywordRule("Tableau", ("tableau",), "hard_skill", "analytics", ("Data Visualization", "dashboarding")),
    KeywordRule("Power BI", ("power bi", "powerbi"), "hard_skill", "analytics", ("Data Visualization", "dashboarding")),
    KeywordRule("Looker", ("looker",), "hard_skill", "analytics", ("Data Visualization", "dashboarding")),
    KeywordRule("Mixpanel", ("mixpanel",), "hard_skill", "product_analytics", ("Product Analytics", "funnel analysis")),
    KeywordRule("Amplitude", ("amplitude",), "hard_skill", "product_analytics", ("Product Analytics", "funnel analysis")),
    KeywordRule("Product Analytics", ("product analytics", "product analysis"), "hard_skill", "product_analytics", ("A/B Testing", "Mixpanel", "Amplitude")),
    KeywordRule("Data Analysis", ("data analysis", "analytics"), "hard_skill", "data_analysis", ("Pandas", "SQL", "Excel")),
    KeywordRule("Data Visualization", ("data visualization", "dashboarding", "dashboards", "reporting"), "hard_skill", "analytics", ("Tableau", "Power BI", "Looker")),
    KeywordRule("ETL", ("etl", "elt", "data pipeline", "data pipelines"), "hard_skill", "data_platform", ("Airflow", "SQL")),
    KeywordRule("Data Modeling", ("data modeling", "data modelling"), "hard_skill", "data_platform", ("SQL", "dbt")),
    KeywordRule("Feature Engineering", ("feature engineering",), "hard_skill", "machine_learning", ("Machine Learning", "Python")),
    KeywordRule("MLOps", ("mlops", "ml ops", "model deployment"), "hard_skill", "machine_learning", ("Docker", "CI/CD", "Machine Learning")),
    KeywordRule("Streamlit", ("streamlit",), "hard_skill", "frontend", ("Python", "dashboarding")),
    KeywordRule("React", ("react", "react.js", "reactjs"), "hard_skill", "frontend", ("JavaScript", "TypeScript")),
    KeywordRule("JavaScript", ("javascript", "js"), "hard_skill", "frontend", ("React", "TypeScript")),
    KeywordRule("TypeScript", ("typescript", "ts"), "hard_skill", "frontend", ("JavaScript", "React")),
    KeywordRule("Communication", ("communication", "communicate", "communicating"), "soft_skill", "collaboration"),
    KeywordRule("Stakeholder Management", ("stakeholder management", "stakeholder communication", "cross-functional", "business partners"), "soft_skill", "collaboration"),
    KeywordRule("Leadership", ("leadership", "lead", "leading"), "soft_skill", "leadership"),
    KeywordRule("Collaboration", ("collaboration", "collaborative", "collaborated", "partnered"), "soft_skill", "collaboration"),
    KeywordRule("Problem Solving", ("problem solving", "solve problems", "problem-solver"), "soft_skill", "general"),
    KeywordRule("Mentoring", ("mentoring", "mentor", "coaching"), "soft_skill", "leadership"),
    KeywordRule("Ownership", ("ownership", "end-to-end ownership", "owned"), "soft_skill", "leadership"),
    KeywordRule("SaaS", ("saas", "software as a service"), "domain", "software"),
    KeywordRule("E-commerce", ("e-commerce", "ecommerce"), "domain", "commerce"),
    KeywordRule("FinTech", ("fintech", "payments"), "domain", "finance"),
    KeywordRule("Healthcare", ("healthcare", "health care"), "domain", "health"),
    KeywordRule("B2B", ("b2b",), "domain", "business"),
    KeywordRule("Consumer Products", ("consumer products", "consumer apps"), "domain", "consumer"),
    KeywordRule("AWS Certification", ("aws certified", "aws certification"), "certification", "cloud"),
    KeywordRule("Google Analytics", ("google analytics", "ga4"), "certification", "analytics"),
]

def normalize_text(text: str) -> str:
    lowered = strip_rich_text(text).lower()
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
    return re.sub(r"\s+", " ", strip_rich_text(text).strip(" -:|,.;")).strip()


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


def dedupe_canonical_terms(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        canonical = canonicalize_term(item)
        if not canonical:
            continue
        key = canonical.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(canonical)
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


def related_terms_for(term: str) -> tuple[str, ...]:
    rule = get_keyword_rule(term)
    return rule.related if rule else tuple()


def classify_term(term: str) -> str:
    rule = get_keyword_rule(term)
    return rule.category if rule else "keyword"


def skill_category_for(term: str) -> str:
    rule = get_keyword_rule(term)
    return rule.skill_category if rule else "general"


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
    normalized_tokens = normalized_text.split()
    if len(term_tokens) == 1:
        return term_tokens[0] in normalized_tokens
    if " ".join(term_tokens) in normalized_text:
        return True
    sentence_tokens = [set(tokenize(sentence)) for sentence in split_sentences(text)]
    for token_set in sentence_tokens:
        overlap = sum(1 for token in term_tokens if token in token_set)
        if overlap / len(term_tokens) >= 0.75:
            return True
    return False


def fuzzy_phrase_present(term: str, text: str) -> bool:
    phrase = phrase_key(term)
    if not phrase or len(phrase) < 5 or not text:
        return False
    if any(symbol in phrase for symbol in ("/", "+", "#", ".")):
        return False
    term_tokens = phrase.split()
    if not term_tokens:
        return False
    if len(term_tokens) < 2:
        return False
    if any(len(token.strip("/")) < 3 for token in term_tokens):
        return False
    text_tokens = tokenize(text)
    window = max(1, len(term_tokens))
    candidates = [" ".join(text_tokens[index : index + window]) for index in range(0, max(0, len(text_tokens) - window + 1))]
    candidates.extend(" ".join(text_tokens[index : index + window + 1]) for index in range(0, max(0, len(text_tokens) - window)))
    return any(SequenceMatcher(None, phrase, candidate).ratio() >= 0.88 for candidate in candidates if candidate)


def best_match_type(term: str, text: str) -> str | None:
    aliases = aliases_for(term)
    if not aliases:
        return None
    canonical = aliases[0]
    if exact_phrase_present(canonical, text):
        return "exact"
    for alias in aliases[1:]:
        if exact_phrase_present(alias, text):
            return "alias"
    for alias in aliases:
        if semantic_phrase_present(alias, text):
            return "phrase"
    for alias in aliases:
        if fuzzy_phrase_present(alias, text):
            return "fuzzy"
    for related in related_terms_for(term):
        if exact_phrase_present(related, text) or semantic_phrase_present(related, text):
            return "related"
    return None


def is_strong_match_type(match_type: str | None) -> bool:
    return match_type in {"exact", "alias", "phrase", "fuzzy"}


def match_strength(match_type: str | None) -> float:
    if match_type == "exact":
        return 1.0
    if match_type == "alias":
        return 0.94
    if match_type == "phrase":
        return 0.84
    if match_type == "fuzzy":
        return 0.76
    if match_type == "related":
        return 0.52
    if match_type == "semantic":
        return 0.72
    return 0.0


def canonical_match_type(term: str, text: str) -> str | None:
    match_type = best_match_type(term, text)
    if match_type:
        return match_type
    canonical = canonicalize_term(term)
    if canonical != clean_phrase(term):
        return best_match_type(canonical, text)
    return None


def _legacy_best_match_type(term: str, text: str) -> str | None:
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
        if any(exact_phrase_present(alias, text) or semantic_phrase_present(alias, text) for alias in (rule.canonical, *rule.aliases)):
            found.append(rule.canonical)
    return dedupe_canonical_terms(found)


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

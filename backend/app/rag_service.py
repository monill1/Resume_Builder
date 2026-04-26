from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAG_ENGINE_ENV = "ATS_RAG_ENGINE"
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
KNOWLEDGE_DIR = Path(__file__).parent / "rag_knowledge"
CHUNK_TARGET_CHARS = 1100
MAX_CONTEXT_CHUNKS = 5

logger = logging.getLogger(__name__)

_INDEX: "RagIndex | None" = None


@dataclass(frozen=True)
class RagChunk:
    source: str
    title: str
    text: str


@dataclass
class RagIndex:
    chunks: list[RagChunk]
    engine_name: str
    model: Any | None = None
    embeddings: Any | None = None
    vectorizer: Any | None = None


def warm_rag_index() -> None:
    get_rag_index()


def retrieve_market_context(query: str, *, top_k: int = MAX_CONTEXT_CHUNKS) -> list[dict[str, object]]:
    normalized_query = _normalize_space(query)
    if not normalized_query:
        return []

    index = get_rag_index()
    if not index.chunks:
        return []

    if index.engine_name != "tfidf" and index.model is not None and index.embeddings is not None:
        from sklearn.metrics.pairwise import cosine_similarity

        query_embedding = index.model.encode([normalized_query], normalize_embeddings=True)
        scores = cosine_similarity(query_embedding, index.embeddings)[0]
    elif index.vectorizer is not None and index.embeddings is not None:
        from sklearn.metrics.pairwise import cosine_similarity

        query_embedding = index.vectorizer.transform([normalized_query])
        scores = cosine_similarity(query_embedding, index.embeddings)[0]
    elif index.engine_name == "lexical":
        scores = [_lexical_similarity(normalized_query, chunk.text) for chunk in index.chunks]
    else:
        return []

    ranked_indexes = sorted(range(len(scores)), key=lambda index_value: float(scores[index_value]), reverse=True)[:top_k]
    results: list[dict[str, object]] = []
    for chunk_index in ranked_indexes:
        score = float(scores[chunk_index])
        if score <= 0:
            continue
        chunk = index.chunks[int(chunk_index)]
        results.append(
            {
                "source": chunk.source,
                "title": chunk.title,
                "text": chunk.text,
                "score": round(score, 4),
            }
        )
    return results


def build_rag_query(*, target_title: str, job_description: str, resume_summary: str, skills: list[str]) -> str:
    return _normalize_space(
        "\n".join(
            [
                f"Target role: {target_title}",
                f"Job description: {job_description}",
                f"Resume summary: {resume_summary}",
                f"Candidate skills: {', '.join(skills)}",
                "Need role-specific project ideas, portfolio proof examples, resume project bullets, and learn-before-submit skills.",
                "Need professional coach rewrite patterns, score lift edits, best placement, existing resume line improvement, and section-specific evidence bullets.",
            ]
        )
    )


def get_rag_index() -> RagIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def _build_index() -> RagIndex:
    chunks = _load_knowledge_chunks()
    engine_preference = os.getenv(RAG_ENGINE_ENV, "auto").strip().lower()

    if engine_preference != "tfidf":
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(DEFAULT_MODEL_NAME, local_files_only=True)
            embeddings = model.encode([chunk.text for chunk in chunks], normalize_embeddings=True)
            return RagIndex(chunks=chunks, engine_name=DEFAULT_MODEL_NAME, model=model, embeddings=embeddings)
        except Exception as exc:
            logger.warning("RAG embedding model unavailable; falling back to TF-IDF retrieval: %s", exc)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        embeddings = vectorizer.fit_transform([chunk.text for chunk in chunks]) if chunks else None
        return RagIndex(chunks=chunks, engine_name="tfidf", vectorizer=vectorizer, embeddings=embeddings)
    except Exception as exc:
        logger.warning("TF-IDF retrieval unavailable; using lexical RAG fallback: %s", exc)
        return RagIndex(chunks=chunks, engine_name="lexical")


def _load_knowledge_chunks() -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = _extract_title(text) or path.stem.replace("_", " ").title()
        for chunk_text in _chunk_markdown(text):
            chunks.append(RagChunk(source=path.name, title=title, text=chunk_text))
    return chunks


def _chunk_markdown(text: str) -> list[str]:
    structured_text = re.sub(
        r"\n(?=(?:RewritePattern|Project):)",
        "\n\n",
        text,
    )
    blocks = [block.strip() for block in re.split(r"\n\s*\n", structured_text) if block.strip()]
    chunks: list[str] = []
    current = ""

    for block in blocks:
        if current and len(current) + len(block) + 2 > CHUNK_TARGET_CHARS:
            chunks.append(_normalize_space(current))
            current = block
        else:
            current = f"{current}\n\n{block}".strip()

    if current:
        chunks.append(_normalize_space(current))
    return chunks


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _lexical_similarity(query: str, text: str) -> float:
    query_terms = set(_tokens(query))
    text_terms = set(_tokens(text))
    if not query_terms or not text_terms:
        return 0.0
    overlap = query_terms & text_terms
    return len(overlap) / max(1, len(query_terms))


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9+#./-]+", text.lower()) if len(token) > 2]

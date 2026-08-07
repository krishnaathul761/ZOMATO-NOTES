"""
semantic_search.py — Phase 4 Intelligence Layer
Local, fully offline semantic search using sentence-transformers.

First run: downloads ~90 MB of model weights to ~/.cache/huggingface/
All subsequent runs: fully offline, no API key required.

Model is lazy-loaded on first use to keep startup memory low (Render free tier).
"""
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Lazy-loaded — model loads on first smart-search request, not at startup.
# This keeps server startup memory under Render's 512MB free tier limit.
_model = None


def _get_model() -> SentenceTransformer:
    """Return the cached model, loading it on first call."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def compute_embeddings(texts: list[str]) -> np.ndarray:
    """Returns a 2-D float32 array of shape (len(texts), 384)."""
    return _get_model().encode(texts, convert_to_numpy=True)


def cosine_similarity_scores(query_vec: np.ndarray,
                              corpus_matrix: np.ndarray) -> np.ndarray:
    """
    Cosine similarity between one query vector and every row in corpus_matrix.
    Returns a 1-D array of scores, one per corpus row.
    Formula: dot(q_norm, c_norm^T)
    The +1e-10 guard prevents division-by-zero on zero vectors.
    """
    query_norm  = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    corpus_norm = corpus_matrix / (
        np.linalg.norm(corpus_matrix, axis=1, keepdims=True) + 1e-10
    )
    return corpus_norm @ query_norm


def semantic_search(query: str, notes: list[dict], top_k: int = 3) -> list[dict]:
    """
    Rank notes by cosine similarity to the query string.
    Returns up to top_k notes, each with a 'similarity' field appended.
    """
    if not notes:
        return []

    contents    = [n["content"] for n in notes]
    corpus_embs = compute_embeddings(contents)
    query_emb   = compute_embeddings([query])[0]
    scores      = cosine_similarity_scores(query_emb, corpus_embs)

    # argsort gives ascending; reverse for descending, then take top_k
    ranked_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in ranked_indices:
        note = dict(notes[idx])                         # copy — don't mutate input
        note["similarity"] = round(float(scores[idx]), 4)
        results.append(note)
    return results

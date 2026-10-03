"""ml/mentor_service.py — Human mentor recommendation engine"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import joblib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

_model: Any = None
_mentor_embeddings: Any = None
_mentors: Any = None
MENTOR_SIMILARITY_THRESHOLD = 0.35


def _load_model():
    global _model, _mentor_embeddings, _mentors
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _mentor_embeddings = joblib.load(MODELS_DIR / "mentor_embeddings.pkl")
        with (BASE_DIR / "data" / "mentors.json").open(encoding="utf-8") as mentor_file:
            _mentors = json.load(mentor_file)


def build_query(industry: str, stage: str, problem: str) -> str:
    return f"{industry} {stage} {problem}"


def recommend_mentors(
    industry: str,
    stage: str,
    problem: str,
    top_k: int = 5,
) -> list[dict]:
    _load_model()
    query = build_query(industry, stage, problem)
    query_embedding = _model.encode([query])
    scores = cosine_similarity(query_embedding, _mentor_embeddings)[0]
    eligible_indices = np.flatnonzero(scores >= MENTOR_SIMILARITY_THRESHOLD)
    top_indices = eligible_indices[np.argsort(scores[eligible_indices])[::-1][:top_k]]

    results = []
    for idx in top_indices:
        mentor = _mentors[idx]
        results.append({
            "id": mentor["id"],
            "name": mentor["name"],
            "current_role": mentor["current_role"],
            "match_score": round(float(scores[idx]) * 100, 1),
            "industry": mentor["industry"],
            "skills": mentor["skills"],
        })
    return results

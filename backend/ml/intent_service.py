"""
backend/ml/intent_service.py — Intent classification service for GenFusion.

Architecture:
    SentenceTransformer("all-MiniLM-L6-v2")
        → 384-dim embedding
        → RandomForestClassifier (intent_classifier.pkl)
        → LabelEncoder          (label_encoder.pkl)

Usage:
    from backend.ml.intent_service import intent_classifier

    result = intent_classifier.predict("How can I improve funding readiness?")
    # => {"intent": "funding_readiness", "confidence": 0.91, "label": "funding_readiness"}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).resolve().parent
MODEL_PATH  = BASE_DIR / "models" / "intent_classifier.pkl"
ENCODER_PATH = BASE_DIR / "models" / "label_encoder.pkl"

EMBEDDER_NAME       = "all-MiniLM-L6-v2"
CONFIDENCE_THRESHOLD = 0.35


# ══════════════════════════════════════════════════════════════════════════════
# Keyword fallback map
# ══════════════════════════════════════════════════════════════════════════════

_KEYWORD_MAP: dict[str, str] = {
    # survival
    "survival":         "survival_score",
    "survive":          "survival_score",
    "succeed":          "survival_score",
    "odds":             "survival_score",
    "viability":        "survival_score",
    # funding
    "funding":          "funding_readiness",
    "raise":            "funding_readiness",
    "investor":         "funding_readiness",
    "fundraising":      "funding_readiness",
    "seed":             "funding_readiness",
    "pitch":            "funding_readiness",
    "series":           "funding_readiness",
    "vc":               "funding_readiness",
    "angel":            "funding_readiness",
    "capital":          "funding_readiness",
    # risk
    "risk":             "risk_assessment",
    "threat":           "risk_assessment",
    "danger":           "risk_assessment",
    "vulnerable":       "risk_assessment",
    "exposure":         "risk_assessment",
    "mitigation":       "risk_assessment",
    # market
    "market":           "market_analysis",
    "tam":              "market_analysis",
    "sam":              "market_analysis",
    "som":              "market_analysis",
    "industry":         "market_analysis",
    "segment":          "market_analysis",
    "demand":           "market_analysis",
    # competitor
    "competitor":       "competitor_analysis",
    "competition":      "competitor_analysis",
    "rival":            "competitor_analysis",
    "competitive":      "competitor_analysis",
    "landscape":        "competitor_analysis",
    # financial health
    "burn":             "financial_health",
    "runway":           "financial_health",
    "revenue":          "financial_health",
    "cash":             "financial_health",
    "mrr":              "financial_health",
    "arr":              "financial_health",
    "financial":        "financial_health",
    "profit":           "financial_health",
    "loss":             "financial_health",
    "breakeven":        "financial_health",
    "break-even":       "financial_health",
    # team
    "team":             "team_evaluation",
    "founder":          "team_evaluation",
    "co-founder":       "team_evaluation",
    "cofounder":        "team_evaluation",
    "hiring":           "team_evaluation",
    "hire":             "team_evaluation",
    "culture":          "team_evaluation",
    "leadership":       "team_evaluation",
    # recommendation
    "recommend":        "recommendation",
    "advice":           "recommendation",
    "action":           "recommendation",
    "improve":          "recommendation",
    "fix":              "recommendation",
    "suggest":          "recommendation",
    "next steps":       "recommendation",
    "what should":      "recommendation",
    # swot
    "swot":             "swot_analysis",
    "strength":         "swot_analysis",
    "weakness":         "swot_analysis",
    "opportunity":      "swot_analysis",
    # analyze
    "analyze":          "analyze_startup",
    "analysis":         "analyze_startup",
    "evaluate":         "analyze_startup",
    "review":           "analyze_startup",
    "score":            "analyze_startup",
    "report":           "analyze_startup",
    "assessment":       "analyze_startup",
    # general
    "hello":            "general_question",
    "hi":               "general_question",
    "help":             "general_question",
    "what can you":     "general_question",
    "who are you":      "general_question",
}


# ══════════════════════════════════════════════════════════════════════════════
# IntentClassifier
# ══════════════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """
    Production intent classifier for GenFusion startup queries.

    Pipeline:
        raw text
          → SentenceTransformer embedding (384-dim)
          → RandomForestClassifier.predict_proba()
          → LabelEncoder.inverse_transform()
          → {"intent", "confidence", "label"}

    Falls back to keyword matching when:
        • model files are missing / corrupted
        • SentenceTransformer fails to load
        • model confidence < CONFIDENCE_THRESHOLD
        • input is empty or None
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        encoder_path: Path = ENCODER_PATH,
        embedder_name: str = EMBEDDER_NAME,
    ) -> None:
        self.model_path    = model_path
        self.encoder_path  = encoder_path
        self.embedder_name = embedder_name

        self._embedder:   Any = None   # SentenceTransformer
        self._classifier: Any = None   # RandomForestClassifier
        self._encoder:    Any = None   # LabelEncoder
        self._load_error: str | None = None

    # ── Lazy loader ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Lazy-load all three components on first call. Idempotent."""
        if (
            self._embedder   is not None
            and self._classifier is not None
            and self._encoder    is not None
        ):
            return                                   # all three already loaded

        logger.info("IntentClassifier: loading components…")

        # 1. SentenceTransformer
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._embedder = SentenceTransformer(self.embedder_name)
            logger.info("IntentClassifier: embedder '%s' loaded", self.embedder_name)
        except ImportError:
            self._load_error = "sentence_transformers package not installed"
            logger.warning("IntentClassifier: %s — keyword fallback active", self._load_error)
            return
        except Exception as exc:
            self._load_error = f"SentenceTransformer load failed: {exc}"
            logger.warning("IntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            return

        # 2. RandomForestClassifier
        if not self.model_path.exists():
            self._load_error = f"Model file not found: {self.model_path}"
            logger.warning(
                "IntentClassifier: %s — run `python -m backend.ml.train_intent_model` first. "
                "Keyword fallback active.",
                self._load_error,
            )
            self._embedder = None
            return
        try:
            self._classifier = joblib.load(self.model_path)
            logger.info("IntentClassifier: classifier loaded from %s", self.model_path)
        except Exception as exc:
            self._load_error = f"Classifier load failed: {exc}"
            logger.warning("IntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            return

        # 3. LabelEncoder
        if not self.encoder_path.exists():
            self._load_error = f"Encoder file not found: {self.encoder_path}"
            logger.warning("IntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder   = None
            self._classifier = None
            return
        try:
            self._encoder = joblib.load(self.encoder_path)
            logger.info("IntentClassifier: encoder loaded from %s", self.encoder_path)
        except Exception as exc:
            self._load_error = f"Encoder load failed: {exc}"
            logger.warning("IntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder   = None
            self._classifier = None
            return

        logger.info("IntentClassifier: all components loaded successfully ✓")

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def loaded(self) -> bool:
        """True only when all three components are ready."""
        return (
            self._embedder   is not None
            and self._classifier is not None
            and self._encoder    is not None
        )

    def reload(self) -> None:
        """
        Force a full reload of all components.
        Useful after training a new model without restarting the process.
        """
        logger.info("IntentClassifier: reloading all components…")
        self._embedder   = None
        self._classifier = None
        self._encoder    = None
        self._load_error = None
        self._load()

    def health_check(self) -> dict[str, Any]:
        """
        Return component availability without triggering a load.

        Returns:
            {
                "loaded":        bool,
                "model_exists":  bool,
                "encoder_exists": bool,
                "embedder_name": str,
                "load_error":    str | None,
            }
        """
        return {
            "loaded":         self.loaded,
            "model_exists":   self.model_path.exists(),
            "encoder_exists": self.encoder_path.exists(),
            "embedder_name":  self.embedder_name,
            "load_error":     self._load_error,
        }

    def predict(self, text: str | None) -> dict[str, Any]:
        """
        Predict intent for a query string.

        Args:
            text: Raw user message. None or empty → general_question.

        Returns:
            {"intent": str, "confidence": float, "label": str}
        """
        # ── Guard: empty / None input ──────────────────────────────────────
        if not text or not str(text).strip():
            return _make_result("general_question", 1.0)

        clean = str(text).strip().lower()

        # ── Lazy load ──────────────────────────────────────────────────────
        self._load()

        # ── ML prediction ─────────────────────────────────────────────────
        if self.loaded:
            try:
                embedding = self._embedder.encode([clean])           # shape (1, 384)
                probs     = self._classifier.predict_proba(embedding) # shape (1, n_classes)
                pred_idx  = int(probs[0].argmax())
                confidence = float(probs[0][pred_idx])

                if confidence >= CONFIDENCE_THRESHOLD:
                    label = self._encoder.inverse_transform([pred_idx])[0]
                    logger.debug(
                        "IntentClassifier ML: '%s' → %s (%.3f)",
                        text[:60], label, confidence,
                    )
                    return _make_result(str(label), round(confidence, 3))

                logger.debug(
                    "IntentClassifier: low confidence %.3f < %.2f — keyword fallback",
                    confidence, CONFIDENCE_THRESHOLD,
                )

            except Exception as exc:
                logger.error(
                    "IntentClassifier predict error: %s — keyword fallback", exc, exc_info=True
                )

        # ── Keyword fallback ───────────────────────────────────────────────
        result = _keyword_match(clean)
        logger.debug(
            "IntentClassifier keyword: '%s' → %s (%.2f)",
            text[:60], result["intent"], result["confidence"],
        )
        return result


# ══════════════════════════════════════════════════════════════════════════════
# Private helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_result(intent: str, confidence: float) -> dict[str, Any]:
    return {"intent": intent, "confidence": confidence, "label": intent}


def _keyword_match(text: str) -> dict[str, Any]:
    """
    Zero-shot keyword fallback.

    Checks multi-word phrases first, then single tokens.
    Returns general_question if nothing matches.
    """
    # Multi-word phrases (highest priority)
    for phrase, intent in _KEYWORD_MAP.items():
        if " " in phrase and phrase in text:
            return _make_result(intent, 0.65)

    # Single-word tokens
    tokens = text.split()
    for token in tokens:
        if token in _KEYWORD_MAP:
            return _make_result(_KEYWORD_MAP[token], 0.55)

    return _make_result("general_question", 0.40)


# ══════════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ══════════════════════════════════════════════════════════════════════════════

intent_classifier = IntentClassifier()
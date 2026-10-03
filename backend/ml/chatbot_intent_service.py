"""
backend/ml/chatbot_intent_service.py — Intent classifier for the Startup Chatbot.

Fully independent from the AI Mentor intent classifier.
Uses its own models stored in backend/ml/models/chatbot/.

Usage:
    from ml.chatbot_intent_service import chatbot_intent_classifier

    result = chatbot_intent_classifier.predict("How many months of runway do I have?")
    # => {"intent": "runway_analysis", "confidence": 0.91}
"""

from __future__ import annotations

import joblib
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent
MODEL_PATH    = BASE_DIR / "models" / "chatbot" / "chatbot_intent_classifier.pkl"
ENCODER_PATH  = BASE_DIR / "models" / "chatbot" / "chatbot_label_encoder.pkl"

EMBEDDER_NAME       = "all-MiniLM-L6-v2"
CONFIDENCE_THRESHOLD = 0.35

_KEYWORD_MAP: dict[str, str] = {
    # burn_rate_analysis
    "burn rate":        "burn_rate_analysis",
    "burn":             "burn_rate_analysis",
    "burning":          "burn_rate_analysis",
    "spend":            "burn_rate_analysis",
    "cash burn":        "burn_rate_analysis",
    "cash is":          "burn_rate_analysis",
    "burning cash":     "burn_rate_analysis",
    # competitive_intelligence
    "competitor":       "competitive_intelligence",
    "competitors":      "competitive_intelligence",
    "competition":      "competitive_intelligence",
    "rival":            "competitive_intelligence",
    "rivals":           "competitive_intelligence",
    "competitive":      "competitive_intelligence",
    "landscape":        "competitive_intelligence",
    "market map":       "competitive_intelligence",
    "comp analysis":    "competitive_intelligence",
    # execution_readiness
    "execute":          "execution_readiness",
    "execution":        "execution_readiness",
    "roadmap":          "execution_readiness",
    "deliver":          "execution_readiness",
    "execute plan":     "execution_readiness",
    "operational":      "execution_readiness",
    # founder_copilot
    "founder":          "founder_copilot",
    "co-founder":       "founder_copilot",
    "cofounder":        "founder_copilot",
    "copilot":          "founder_copilot",
    "help me":          "founder_copilot",
    "guide":            "founder_copilot",
    "stuck":            "founder_copilot",
    "frustrated":       "founder_copilot",
    "overwhelmed":      "founder_copilot",
    "advise":           "founder_copilot",
    "suggestion":       "founder_copilot",
    "think through":    "founder_copilot",
    # team_health
    "team":             "team_health",
    "hiring":           "team_health",
    "hire":             "team_health",
    "culture":          "team_health",
    "people":           "team_health",
    "talent":           "team_health",
    "recruit":          "team_health",
    "staff":            "team_health",
    # funding_readiness
    "funding":          "funding_readiness",
    "raise":            "funding_readiness",
    "raising":          "funding_readiness",
    "investor":         "funding_readiness",
    "investors":        "funding_readiness",
    "fundraising":      "funding_readiness",
    "fund":             "funding_readiness",
    "seed":             "funding_readiness",
    "pitch":            "funding_readiness",
    "deck":             "funding_readiness",
    "series":           "funding_readiness",
    "vc":               "funding_readiness",
    "angel":            "funding_readiness",
    "capital":          "funding_readiness",
    "fundraise":        "funding_readiness",
    "venture":          "funding_readiness",
    "pre seed":         "funding_readiness",
    "pre-seed":         "funding_readiness",
    "fund me":          "funding_readiness",
    "raise money":      "funding_readiness",
    "raise capital":    "funding_readiness",
    # growth_strategy
    "growth":           "growth_strategy",
    "grow":             "growth_strategy",
    "scale":            "growth_strategy",
    "expand":           "growth_strategy",
    "channels":         "growth_strategy",
    "acquisition":      "growth_strategy",
    "customer acqui":   "growth_strategy",
    "go to market":     "growth_strategy",
    "go-to-market":     "growth_strategy",
    "gtm strategy":     "growth_strategy",
    "gtm":              "growth_strategy",
    "revenue growth":   "growth_strategy",
    # traction_analysis
    "traction":         "traction_analysis",
    "momentum":         "traction_analysis",
    "adoption":         "traction_analysis",
    "users":            "traction_analysis",
    "customers":        "traction_analysis",
    "engagement":       "traction_analysis",
    "retention":        "traction_analysis",
    "growth rate":      "traction_analysis",
    # investor_readiness
    "investor ready":   "investor_readiness",
    "due diligence":    "investor_readiness",
    "diligence":        "investor_readiness",
    "ready for inv":    "investor_readiness",
    "investable":       "investor_readiness",
    # market_timing
    "market timing":    "market_timing",
    "timing":           "market_timing",
    "too early":        "market_timing",
    "too late":         "market_timing",
    "right time":       "market_timing",
    "good time":        "market_timing",
    "time to launch":   "market_timing",
    # market_validation
    "market valid":     "market_validation",
    "product market":   "market_validation",
    "pmf":              "market_validation",
    "problem":          "market_validation",
    "pain point":       "market_validation",
    "pain points":      "market_validation",
    "demand":           "market_validation",
    "fit":              "market_validation",
    "validating":       "market_validation",
    "test my":          "market_validation",
    "startup idea":     "market_validation",
    "idea validation":  "market_validation",
    # risk_assessment
    "risk":             "risk_assessment",
    "risks":            "risk_assessment",
    "risky":            "risk_assessment",
    "threat":           "risk_assessment",
    "threats":          "risk_assessment",
    "danger":           "risk_assessment",
    "mitigation":       "risk_assessment",
    "mitigate":         "risk_assessment",
    "exposure":         "risk_assessment",
    "vulnerable":       "risk_assessment",
    "worst case":       "risk_assessment",
    # runway_analysis
    "runway":           "runway_analysis",
    "run away":         "runway_analysis",
    "cash left":        "runway_analysis",
    "months left":      "runway_analysis",
    "money left":       "runway_analysis",
    "out of money":     "runway_analysis",
    "run out":          "runway_analysis",
    "how long":         "runway_analysis",
    # startup_action_plan
    "action plan":      "startup_action_plan",
    "next steps":       "startup_action_plan",
    "recommend":        "startup_action_plan",
    "advice":           "startup_action_plan",
    "priorities":       "startup_action_plan",
    "todo":             "startup_action_plan",
    # startup_health
    "health":           "startup_health",
    "overall":          "startup_health",
    "score":            "startup_health",
    "healthy":          "startup_health",
    "health check":     "startup_health",
    # startup_prediction
    "predict":          "startup_prediction",
    "forecast":         "startup_prediction",
    "prediction":       "startup_prediction",
    "projection":       "startup_prediction",
    "outcome":          "startup_prediction",
    "survive":          "startup_prediction",
    "survival":         "startup_prediction",
    "odds":             "startup_prediction",
    "chances":          "startup_prediction",
    "success rate":     "startup_prediction",
    "likelihood":       "startup_prediction",
    "probability":      "startup_prediction",
    # swot_analysis
    "swot":             "swot_analysis",
    "strength":         "swot_analysis",
    "strengths":        "swot_analysis",
    "weakness":         "swot_analysis",
    "weaknesses":       "swot_analysis",
    "opportunity":      "swot_analysis",
    "opportunities":    "swot_analysis",
    "swot analysis":    "swot_analysis",
    # mentor_recommendation
    "recommend a mentor":"mentor_recommendation",
    "find a mentor":     "mentor_recommendation",
    "find me a mentor":  "mentor_recommendation",
    "best mentor":       "mentor_recommendation",
    "guide my startup":  "mentor_recommendation",
    "mentor for":        "mentor_recommendation",
    "mentor in":         "mentor_recommendation",
    "mentor who":        "mentor_recommendation",
    "mentor with":       "mentor_recommendation",
    "best founders":     "mentor_recommendation",
    "founder advice":    "mentor_recommendation",
    "founder to learn":  "mentor_recommendation",
    "mentor":            "mentor_recommendation",
    "mentors":           "mentor_recommendation",
    "mentorship":        "mentor_recommendation",
    "advisor":           "mentor_recommendation",
    "advisors":          "mentor_recommendation",
    "advisory":          "mentor_recommendation",
    "need a mentor":     "mentor_recommendation",
    "i need a mentor":   "mentor_recommendation",
    "who should i talk": "mentor_recommendation",
    "who can help":      "mentor_recommendation",
    "who can guide":     "mentor_recommendation",
    "learn from":        "mentor_recommendation",
    "connect me with":   "mentor_recommendation",
    "suggest a mentor":  "mentor_recommendation",
    "top mentor":        "mentor_recommendation",
    "founder help":      "mentor_recommendation",
    "startup guidance":  "mentor_recommendation",
    "need a mentor":     "mentor_recommendation",
    "need an advisor":   "mentor_recommendation",
    "guide me":          "mentor_recommendation",
    "startup mentor":    "mentor_recommendation",
    "need founder":      "mentor_recommendation",
    "need guidance":     "mentor_recommendation",
    "expert advice":     "mentor_recommendation",
    "talk to a mentor":  "mentor_recommendation",
    "connect to mentor": "mentor_recommendation",
    "pair me with":      "mentor_recommendation",
    "introduce me to":   "mentor_recommendation",
    "mentorship program":"mentor_recommendation",
    "get mentorship":    "mentor_recommendation",
}


class ChatbotIntentClassifier:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        encoder_path: Path = ENCODER_PATH,
        embedder_name: str = EMBEDDER_NAME,
    ) -> None:
        self.model_path    = model_path
        self.encoder_path  = encoder_path
        self.embedder_name = embedder_name

        self._embedder:   Any = None
        self._classifier: Any = None
        self._encoder:    Any = None
        self._load_error: str | None = None

    def _load(self) -> None:
        if self._embedder is not None and self._classifier is not None and self._encoder is not None:
            return

        logger.info("ChatbotIntentClassifier: loading components…")

        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.embedder_name)
            logger.info("ChatbotIntentClassifier: embedder '%s' loaded", self.embedder_name)
        except ImportError:
            self._load_error = "sentence_transformers package not installed"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            return
        except Exception as exc:
            self._load_error = f"SentenceTransformer load failed: {exc}"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            return

        if not self.model_path.exists():
            self._load_error = f"Model file not found: {self.model_path}"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            return
        try:
            self._classifier = joblib.load(self.model_path)
            logger.info("ChatbotIntentClassifier: classifier loaded from %s", self.model_path)
        except Exception as exc:
            self._load_error = f"Classifier load failed: {exc}"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            return

        if not self.encoder_path.exists():
            self._load_error = f"Encoder file not found: {self.encoder_path}"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            self._classifier = None
            return
        try:
            self._encoder = joblib.load(self.encoder_path)
            logger.info("ChatbotIntentClassifier: encoder loaded from %s", self.encoder_path)
        except Exception as exc:
            self._load_error = f"Encoder load failed: {exc}"
            logger.warning("ChatbotIntentClassifier: %s — keyword fallback active", self._load_error)
            self._embedder = None
            self._classifier = None
            return

        logger.info("ChatbotIntentClassifier: all components loaded successfully")

    @property
    def loaded(self) -> bool:
        return self._embedder is not None and self._classifier is not None and self._encoder is not None

    def reload(self) -> None:
        logger.info("ChatbotIntentClassifier: reloading all components…")
        self._embedder = None
        self._classifier = None
        self._encoder = None
        self._load_error = None
        self._load()

    def predict(self, text: str | None) -> dict[str, Any]:
        if not text or not str(text).strip():
            return {"intent": "founder_copilot", "confidence": 1.0, "source": "fallback"}

        clean = str(text).strip().lower()
        self._load()

        if self.loaded:
            try:
                embedding = self._embedder.encode([clean])
                probs = self._classifier.predict_proba(embedding)
                pred_idx = int(probs[0].argmax())
                confidence = float(probs[0][pred_idx])

                if confidence >= CONFIDENCE_THRESHOLD:
                    label = self._encoder.inverse_transform([pred_idx])[0]
                    logger.debug(
                        "ChatbotIntentClassifier ML: '%s' → %s (%.3f)",
                        text[:60], label, confidence,
                    )
                    return {"intent": str(label), "confidence": round(confidence, 3), "source": "ml"}

                logger.debug(
                    "ChatbotIntentClassifier: low confidence %.3f < %.2f — keyword fallback",
                    confidence, CONFIDENCE_THRESHOLD,
                )
            except Exception as exc:
                logger.error("ChatbotIntentClassifier predict error: %s — keyword fallback", exc, exc_info=True)

        result = _keyword_match(clean)
        logger.debug(
            "ChatbotIntentClassifier keyword: '%s' → %s (%.2f)",
            text[:60], result["intent"], result["confidence"],
        )
        return result


def _keyword_match(text: str) -> dict[str, Any]:
    for phrase, intent in _KEYWORD_MAP.items():
        if " " in phrase and phrase in text:
            return {"intent": intent, "confidence": 0.70, "source": "keyword"}

    tokens = text.split()

    for token in tokens:
        if token in _KEYWORD_MAP:
            return {"intent": _KEYWORD_MAP[token], "confidence": 0.60, "source": "keyword"}

    sorted_keywords = sorted(_KEYWORD_MAP.items(), key=lambda x: -len(x[0]))
    for token in tokens:
        for keyword, intent in sorted_keywords:
            if " " not in keyword and len(keyword) >= 3 and token.startswith(keyword):
                return {"intent": intent, "confidence": 0.50, "source": "keyword"}

    return {"intent": "founder_copilot", "confidence": 0.40, "source": "fallback"}


chatbot_intent_classifier = ChatbotIntentClassifier()

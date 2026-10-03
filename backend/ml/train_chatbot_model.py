"""
backend/ml/train_chatbot_model.py — Train the Startup Chatbot intent classifier.

Separate from the AI Mentor intent classifier.
Uses intents_v3.json with class_weight="balanced" for minority-class support.
Saves to backend/ml/models/chatbot/ — does NOT touch mentor models.
"""

import json
import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path

from sentence_transformers import SentenceTransformer

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "chatbot_intents.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

texts = [item["text"] for item in data]
labels = [item["intent"] for item in data]

print(f"Samples: {len(texts)}")
print(f"Classes: {sorted(set(labels))}")

print("\nGenerating Embeddings...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, show_progress_bar=True)
print(f"Embedding shape: {embeddings.shape}")

encoder = LabelEncoder()
y = encoder.fit_transform(labels)

X_train, X_test, y_train, y_test = train_test_split(
    embeddings, y, test_size=0.2, random_state=42, stratify=y
)

print("\nTraining Random Forest (n=500, class_weight=balanced)...")
classifier = RandomForestClassifier(
    n_estimators=500,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
classifier.fit(X_train, y_train)
print("Done\n")

y_pred = classifier.predict(X_test)

accuracy  = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
recall    = recall_score(y_test, y_pred, average="weighted", zero_division=0)
f1        = f1_score(y_test, y_pred, average="weighted", zero_division=0)

print(f"Accuracy:  {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1 Score:  {f1:.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=encoder.classes_, zero_division=0))

cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=encoder.classes_)
disp.plot()
plt.title("Chatbot Intent Classifier — Confusion Matrix")

MODELS_DIR = BASE_DIR / "models" / "chatbot"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

plt.savefig(MODELS_DIR / "chatbot_confusion_matrix.png")
print(f"\nSaved: {MODELS_DIR / 'chatbot_confusion_matrix.png'}")

joblib.dump(classifier, MODELS_DIR / "chatbot_intent_classifier.pkl")
joblib.dump(encoder, MODELS_DIR / "chatbot_label_encoder.pkl")
joblib.dump(
    {
        "accuracy":  float(accuracy),
        "precision": float(precision),
        "recall":    float(recall),
        "f1_score":  float(f1),
        "n_classes": len(encoder.classes_),
        "classes":   list(encoder.classes_),
        "n_samples": len(texts),
        "embedder":  "all-MiniLM-L6-v2",
    },
    MODELS_DIR / "chatbot_metrics.pkl",
)

print("\nModels Saved:")
print("  chatbot_intent_classifier.pkl")
print("  chatbot_label_encoder.pkl")
print("  chatbot_metrics.pkl")
print("  chatbot_confusion_matrix.png")

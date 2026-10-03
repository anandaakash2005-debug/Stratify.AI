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

DATA_FILE = Path("ml/data/intents_v2.json")

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

texts = [item["text"] for item in data]
labels = [item["intent"] for item in data]

print(f"Samples: {len(texts)}")
print(f"Classes: {set(labels)}")

print("\nGenerating Embeddings...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(texts, show_progress_bar=True)
print(f"Embedding shape: {embeddings.shape}")

encoder = LabelEncoder()
y = encoder.fit_transform(labels)

X_train, X_test, y_train, y_test = train_test_split(
    embeddings, y, test_size=0.2, random_state=42, stratify=y
)

print("\nTraining Random Forest...")
classifier = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
classifier.fit(X_train, y_train)
print("Done\n")

y_pred = classifier.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average="weighted")
recall = recall_score(y_test, y_pred, average="weighted")
f1 = f1_score(y_test, y_pred, average="weighted")

print(f"Accuracy:  {accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1 Score:  {f1:.4f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=encoder.classes_))

cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=encoder.classes_)
disp.plot()
plt.title("Intent Classifier Confusion Matrix")

MODELS_DIR = Path("ml/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

plt.savefig(MODELS_DIR / "confusion_matrix.png")
print("\nSaved: confusion_matrix.png")

joblib.dump(classifier, MODELS_DIR / "mentor_intent_classifier.pkl")
joblib.dump(encoder, MODELS_DIR / "mentor_label_encoder.pkl")
joblib.dump(
    {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
    },
    MODELS_DIR / "mentor_metrics.pkl",
)

print("\nModels Saved:")
print("  mentor_intent_classifier.pkl")
print("  mentor_label_encoder.pkl")
print("  mentor_metrics.pkl")

import json
import joblib

from pathlib import Path
from sentence_transformers import SentenceTransformer


def mentor_to_text(mentor):
    return " ".join([
        " ".join(mentor.get("industry", [])),
        " ".join(mentor.get("stages", [])),
        " ".join(mentor.get("skills", [])),
        mentor.get("current_role", ""),
        " ".join(mentor.get("previous_roles", [])),
        mentor.get("bio", "")
    ])


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "mentors.json"
MODELS_DIR = BASE_DIR / "models"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    mentors = json.load(f)

print(f"Loaded {len(mentors)} mentors")

mentor_texts = [mentor_to_text(m) for m in mentors]

print("Generating Mentor Embeddings...")
model = SentenceTransformer("all-MiniLM-L6-v2")
mentor_embeddings = model.encode(mentor_texts, show_progress_bar=True)
print(f"Embedding shape: {mentor_embeddings.shape}")


MODELS_DIR.mkdir(parents=True, exist_ok=True)

joblib.dump(mentor_embeddings, MODELS_DIR / "mentor_embeddings.pkl")
joblib.dump(mentors, MODELS_DIR / "mentor_metadata.pkl")

print("\nModels Saved:")
print("  mentor_embeddings.pkl")
print("  mentor_metadata.pkl")

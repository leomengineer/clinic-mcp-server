"""Local sentence-transformers embeddings (copied from docs-rag-chatbot)."""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(texts):
    """Embed a list of strings. Returns list of float vectors (384-dim)."""
    if not texts:
        return []
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_one(text):
    return embed([text])[0]

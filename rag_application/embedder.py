from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"


def get_embedder():
    """
    Load and return the sentence transformer model.
    """
    model = SentenceTransformer(MODEL_NAME)
    return model


def embed_chunks(chunks, model):
    """
    Take a list of text chunks and return their embeddings as a list of vectors.

    chunks: list of strings
    model: a SentenceTransformer model instance

    Returns a list of numpy arrays (one embedding per chunk).
    """
    embeddings = model.encode(chunks, show_progress_bar=True)
    return embeddings

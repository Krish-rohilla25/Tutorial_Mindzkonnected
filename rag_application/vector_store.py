import chromadb

CHROMA_DB_PATH = "./rag_application/chroma_db"
COLLECTION_NAME = "pdf_chunks"


def build_vector_store(chunks, embeddings):
    """
    Create a ChromaDB collection from chunks and their embeddings.

    chunks: list of text strings
    embeddings: list of numpy arrays from the embedder

    Returns the ChromaDB collection object.
    """
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Delete all existing collections via the ChromaDB API before creating a
    # new one. This clears both disk and the Rust backend's in-memory registry.
    for col in client.list_collections():
        client.delete_collection(name=col.name)

    collection = client.create_collection(name=COLLECTION_NAME)

    # ChromaDB expects ids as strings, embeddings as lists, documents as strings
    ids = [str(i) for i in range(len(chunks))]
    embeddings_as_lists = [e.tolist() for e in embeddings]

    collection.add(
        ids=ids,
        embeddings=embeddings_as_lists,
        documents=chunks,
    )

    return collection


def retrieve_chunks(collection, query_embedding, top_k=5):
    """
    Given a query embedding, find the top_k most similar chunks.

    collection: a ChromaDB collection
    query_embedding: numpy array of the question embedding
    top_k: number of chunks to return

    Returns a list of text strings (the matching chunks).
    """
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
    )

    matched_chunks = results["documents"][0]
    return matched_chunks

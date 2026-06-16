from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text, chunk_size=1000, chunk_overlap=200):
    """
    Split a large string of text into smaller overlapping chunks.

    chunk_size: max characters per chunk
    chunk_overlap: how many characters each chunk shares with the previous one
                   (helps preserve context at chunk boundaries)

    Returns a list of text strings (chunks).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    chunks = splitter.split_text(text)
    return chunks

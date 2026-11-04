from functools import lru_cache
from dataclasses import dataclass
from app.core.config import settings

import tiktoken

ENCODING_NAME = "cl100k_base"

@dataclass
class TextChunk:
    chunk_index: int
    token_count: int
    text: str


@lru_cache(maxsize=1)
def get_encoder() -> tiktoken.Encoding:
    """Load the tokenizer the first time it is needed, then reuse the same object."""
    return tiktoken.get_encoding(ENCODING_NAME)


def split_text_into_chunks(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE_TOKENS,
    chunk_overlap: int = settings.CHUNK_OVERLAP_TOKENS,
) -> list[TextChunk]:
    """Cut text into overlapping chunks, measured in tokens."""
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_size must be > 0 and chunk_overlap must be >= 0 and < chunk_size")

    encoder = get_encoder()
    token_ids = encoder.encode(text)
    step = chunk_size - chunk_overlap

    chunks: list[TextChunk] = []
    start = 0
    while start < len(token_ids):
        window = token_ids[start : start + chunk_size]
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                token_count=len(window),
                text=encoder.decode_bytes(window).decode("utf-8", errors="ignore"),
            )
        )
        if start + chunk_size >= len(token_ids):
            break
        start += step
    return chunks
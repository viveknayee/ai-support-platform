import pytest

from app.core.config import settings
from app.services.text_processor import get_encoder, split_text_into_chunks

ENGLISH = "The quick brown fox jumps over the lazy dog. " * 120
HINDI = "नमस्ते, यह एक परीक्षण वाक्य है। " * 120


def test_empty_text_returns_no_chunks():
    assert split_text_into_chunks("") == []


def test_short_text_is_one_chunk():
    chunks = split_text_into_chunks("Hello world")

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "Hello world"
    assert chunks[0].token_count == len(get_encoder().encode("Hello world"))


def test_chunks_follow_the_sliding_window_rule():
    encoder = get_encoder()
    token_ids = encoder.encode(ENGLISH)
    size = settings.CHUNK_SIZE_TOKENS
    step = size - settings.CHUNK_OVERLAP_TOKENS

    chunks = split_text_into_chunks(ENGLISH)

    for i, chunk in enumerate(chunks):
        window = token_ids[i * step : i * step + size]
        assert chunk.text == encoder.decode(window)
        assert chunk.token_count == len(window)


def test_chunk_indexes_are_in_order_from_zero():
    chunks = split_text_into_chunks(ENGLISH)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_no_chunk_is_bigger_than_chunk_size():
    chunks = split_text_into_chunks(ENGLISH)

    assert all(c.token_count <= settings.CHUNK_SIZE_TOKENS for c in chunks)


def test_overlap_is_counted_exactly_once_between_neighbours():
    total_tokens = len(get_encoder().encode(ENGLISH))

    chunks = split_text_into_chunks(ENGLISH)

    counted = sum(c.token_count for c in chunks)
    repeated = settings.CHUNK_OVERLAP_TOKENS * (len(chunks) - 1)
    assert counted - repeated == total_tokens


def test_text_exactly_chunk_size_is_one_chunk():
    total_tokens = len(get_encoder().encode(ENGLISH))

    chunks = split_text_into_chunks(ENGLISH, chunk_size=total_tokens, chunk_overlap=50)

    assert len(chunks) == 1


def test_one_token_over_chunk_size_is_two_chunks():
    total_tokens = len(get_encoder().encode(ENGLISH))

    chunks = split_text_into_chunks(ENGLISH, chunk_size=total_tokens - 1, chunk_overlap=50)

    assert len(chunks) == 2


def test_hindi_text_has_no_broken_characters():
    chunks = split_text_into_chunks(HINDI)

    assert len(chunks) > 1
    assert all("\ufffd" not in c.text for c in chunks)


@pytest.mark.parametrize(
    "chunk_size, chunk_overlap",
    [(0, 0), (400, 400), (400, 500), (400, -1)],
)
def test_bad_settings_raise_value_error(chunk_size, chunk_overlap):
    with pytest.raises(ValueError):
        split_text_into_chunks("some text", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
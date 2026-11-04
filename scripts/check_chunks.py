from app.services.text_processor import split_text_into_chunks

samples = {
    "english": "The quick brown fox jumps over the lazy dog. " * 120,
    "hindi": "नमस्ते, यह एक परीक्षण वाक्य है। " * 120,
}

for name, text in samples.items():
    chunks = split_text_into_chunks(text)
    broken = sum("\ufffd" in c.text for c in chunks)
    print(name)
    print("  chunks       :", len(chunks))
    print("  token counts :", [c.token_count for c in chunks])
    print("  broken chunks:", broken)
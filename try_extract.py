from pathlib import Path
from app.services.text_extractor import extract_text, ExtractionError

for f in sorted(Path("test_files").iterdir()):
    try:
        t = extract_text(f)
        print("OK  ", f.name, len(t), repr(t[:60]))
    except ExtractionError as e:
        print("FAIL", f.name, "->", e)
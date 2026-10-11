from pathlib import Path

import pdfplumber
from pypdf import PdfReader


class ExtractionError(Exception):
    """Raised when a file cannot be turned into text.
    The message is safe to show to the user (it is saved in Document.error_message)."""


def extract_pdf_text(path: Path) -> str:
    # Block 1: password check with pypdf (it says clearly if the PDF is locked)
    try:
        if PdfReader(str(path)).is_encrypted:
            raise ExtractionError("PDF is password-protected. Please upload an unlocked copy.")
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError("PDF file is damaged and cannot be read.")

    # Block 2: read the text page by page with pdfplumber
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception:
        raise ExtractionError("PDF file is damaged and cannot be read.")

    # Block 3: scanned PDF = pictures only, so no text came out
    text = "\n\n".join(pages).strip()
    if not text:
        raise ExtractionError("No text found in this PDF. It may be a scanned image (OCR is not supported yet).")
    return text


def extract_txt_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig also removes the invisible BOM
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")  # old Windows (ANSI) files
    text = text.strip()
    if not text:
        raise ExtractionError("The text file has no readable text.")
    return text


def extract_text(path: Path) -> str:
    path = Path(path)                           
    if not path.is_file():                       
        raise FileNotFoundError(path)            
    suffix = path.suffix.lower()              
    if suffix == ".pdf":
        return extract_pdf_text(path)              
    if suffix == ".txt":
        return extract_txt_text(path)              
    raise ExtractionError(f"Unsupported file type: {suffix}")
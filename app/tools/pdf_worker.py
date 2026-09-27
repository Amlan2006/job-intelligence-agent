"""PDF text extraction worker. Input is bytes; output is a bounded JSON result."""

import io
import json
import sys

from pypdf import PdfReader


def extract_pdf(content: bytes, max_pages: int, max_characters: int) -> dict:
    if not content.startswith(b"%PDF-"):
        return {"error": "INVALID_PDF"}
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            return {"error": "ENCRYPTED_PDF"}
        if len(reader.pages) > max_pages:
            return {"error": "PDF_PAGE_LIMIT"}
        pages = []
        characters = 0
        blank = 0
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            blank += not bool(text)
            characters += len(text)
            if characters > max_characters:
                return {"error": "PDF_TEXT_LIMIT"}
            pages.append(text)
        if not any(pages):
            return {"error": "OCR_REQUIRED"}
        return {
            "text": "\n\n".join(pages),
            "page_count": len(pages),
            "warnings": ["PARTIAL_TEXT: some pages have no extractable text"] if blank else [],
        }
    except Exception:
        return {"error": "RESUME_PARSE_FAILED"}


if __name__ == "__main__":
    max_bytes, max_pages, max_characters = map(int, sys.argv[1:])
    content = sys.stdin.buffer.read(max_bytes + 1)
    result = (
        {"error": "PDF_SIZE_LIMIT"}
        if len(content) > max_bytes
        else extract_pdf(content, max_pages, max_characters)
    )
    print(json.dumps(result))

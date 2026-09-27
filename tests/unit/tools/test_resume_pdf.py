import asyncio
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.tools.pdf_worker import extract_pdf
from app.tools.resume_pdf import ResumePDFParser
from tests.resume_fixtures import make_pdf, make_scanned_pdf


def test_valid_pdf_text():
    parsed = extract_pdf(make_pdf(), 20, 50000)
    assert parsed["page_count"] == 1
    assert "Ledger API" in parsed["text"]
    assert not parsed["warnings"]


def test_sparse_resume():
    assert extract_pdf(make_pdf(["Skills: Python"]), 20, 50000)["text"] == "Skills: Python"


@pytest.mark.parametrize(
    "content,code",
    [
        (b"not a pdf", "INVALID_PDF"),
        (b"%PDF-1.7\nbroken", "RESUME_PARSE_FAILED"),
        (make_pdf([]), "OCR_REQUIRED"),
        (make_pdf(encrypted=True), "ENCRYPTED_PDF"),
    ],
)
def test_unusable_pdfs(content, code):
    assert extract_pdf(content, 20, 50000)["error"] == code


def test_page_and_text_limits():
    assert extract_pdf(make_pdf(pages=2), 1, 50000)["error"] == "PDF_PAGE_LIMIT"
    assert extract_pdf(make_pdf(), 20, 5)["error"] == "PDF_TEXT_LIMIT"


def test_image_only_pdf_requires_ocr():
    assert extract_pdf(make_scanned_pdf(), 20, 50000)["error"] == "OCR_REQUIRED"


async def test_real_worker():
    parser = ResumePDFParser(Settings(_env_file=None))
    assert "Python" in (await parser.parse(make_pdf()))["text"]


async def test_worker_timeout_kills_process(monkeypatch):
    process = AsyncMock()
    process.returncode = None
    process.kill = lambda: None

    async def slow(*args):
        await asyncio.sleep(10)

    process.communicate.side_effect = slow
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(TimeoutError):
        await ResumePDFParser(Settings(_env_file=None, resume_parse_timeout_seconds=0.01)).parse(
            b"pdf"
        )
    process.wait.assert_awaited_once()

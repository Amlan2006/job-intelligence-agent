from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

RESUME_LINES = [
    "Alex Sample - Backend Engineer",
    "Skills: Python, Postgres, PostgreSQL, Golang, Docker, Solidity.",
    "Project: Ledger API - Built a Python API with Postgres and Docker.",
    "Employment: Example Labs - Backend Engineer - Jan 2023 to Dec 2025.",
    "Built reliable API services. 3 years of professional experience.",
    "Open source: SDK Toolkit - Contributed Solidity tests.",
]


def make_pdf(lines: list[str] | None = None, pages: int = 1, encrypted: bool = False) -> bytes:
    stream = BytesIO()
    document = canvas.Canvas(stream, invariant=1)
    for _ in range(pages):
        for index, line in enumerate(RESUME_LINES if lines is None else lines):
            document.drawString(50, 780 - index * 24, line)
        document.showPage()
    document.save()
    if encrypted:
        writer = PdfWriter()
        writer.append(PdfReader(BytesIO(stream.getvalue())))
        writer.encrypt("test-password")
        stream = BytesIO()
        writer.write(stream)
    return stream.getvalue()


def make_scanned_pdf() -> bytes:
    stream = BytesIO()
    document = canvas.Canvas(stream, invariant=1)
    image = Image.new("RGB", (100, 100), "white")
    document.drawImage(ImageReader(image), 50, 600, width=100, height=100)
    document.showPage()
    document.save()
    return stream.getvalue()

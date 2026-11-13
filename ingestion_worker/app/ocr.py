"""Text recognition for scanned PDFs.

Scanned court filings, signed contracts and notarized documents are common in
legal work, and they have no text layer: a plain conversion yields nothing and
the file would never match a search. Such PDFs are run through ocrmypdf
(Tesseract, Spanish + English) before chunking.

OCR is heavy (the worker has been OOM-killed by big files before), so it runs
as a separate process, one page-job at a time, with a time limit.
"""

import subprocess
import sys

from app.failures import OcrFailed


def needs_ocr(text: str, pages: int, min_chars_per_page: int) -> bool:
    """True when the extracted text is too thin for the number of pages to be a
    real text layer (an empty scan, or a scan with only a stamp or page number)."""
    pages = max(pages, 1)
    return len(text.strip()) < min_chars_per_page * pages


def count_pdf_pages(path: str) -> int:
    from pdfminer.pdfpage import PDFPage

    with open(path, "rb") as f:
        return sum(1 for _ in PDFPage.get_pages(f))


def run_ocr(source: str, destination: str, languages: str, timeout_seconds: int) -> None:
    """Write an OCR'd copy of source to destination. Pages that already have
    text are left as they are (--skip-text), so mixed documents work."""
    command = [
        sys.executable, "-m", "ocrmypdf",
        "--language", languages,
        "--skip-text",
        "--jobs", "1",  # keep memory bounded
        "--optimize", "0",  # we only need the text, not a smaller file
        "--output-type", "pdf",
        "--quiet",
        source, destination,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise OcrFailed("timed out") from exc
    except subprocess.CalledProcessError as exc:
        # Includes encrypted PDFs and files ocrmypdf can't repair. The detail is
        # kept for the worker's log; the person gets a plain-language reason.
        raise OcrFailed(exc.stderr.decode(errors="replace")[-500:]) from exc

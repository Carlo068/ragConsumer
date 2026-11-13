import subprocess
import sys

import pytest

from app import ocr
from app.failures import TIMED_OUT, UNREADABLE, OcrFailed, failure_reason
from app.ocr import needs_ocr, run_ocr


def test_an_empty_pdf_needs_ocr():
    assert needs_ocr("", pages=3, min_chars_per_page=50)


def test_a_scan_with_only_a_page_number_still_needs_ocr():
    assert needs_ocr("\n\n 12 \n", pages=10, min_chars_per_page=50)


def test_a_pdf_with_a_real_text_layer_does_not():
    assert not needs_ocr("palabra " * 400, pages=4, min_chars_per_page=50)


def test_the_threshold_scales_with_the_page_count():
    text = "x" * 400
    assert not needs_ocr(text, pages=4, min_chars_per_page=50)
    assert needs_ocr(text, pages=40, min_chars_per_page=50)


def test_a_zero_page_count_is_treated_as_one_page():
    assert not needs_ocr("x" * 60, pages=0, min_chars_per_page=50)


def test_ocr_runs_as_a_bounded_separate_process_in_spanish_and_english(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"], seen["kwargs"] = command, kwargs

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    run_ocr("in.pdf", "out.pdf", "spa+eng", 123)

    command = seen["command"]
    assert command[:3] == [sys.executable, "-m", "ocrmypdf"]
    assert command[command.index("--language") + 1] == "spa+eng"
    assert "--skip-text" in command  # pages that already have text are kept
    assert command[command.index("--jobs") + 1] == "1"  # bounded memory
    assert command[-2:] == ["in.pdf", "out.pdf"]
    assert seen["kwargs"]["timeout"] == 123


def test_a_timeout_becomes_a_retryable_failure(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    with pytest.raises(OcrFailed) as error:
        run_ocr("in.pdf", "out.pdf", "spa+eng", 1)
    assert failure_reason(error.value) == TIMED_OUT


def test_an_unreadable_scan_becomes_the_unreadable_message(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(8, command, stderr=b"EncryptedPdfError: file is encrypted")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    with pytest.raises(OcrFailed) as error:
        run_ocr("in.pdf", "out.pdf", "spa+eng", 1)
    assert failure_reason(error.value) == UNREADABLE
    # The raw detail is kept for the log but is never what is stored or shown.
    assert "Encrypted" in str(error.value) and "Encrypted" not in failure_reason(error.value)

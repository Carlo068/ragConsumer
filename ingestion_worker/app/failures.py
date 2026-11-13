"""Turns an indexing failure into a short code the web app can explain.

The raw exception (paths, library internals) goes to the worker's log only; the
person sees a plain-language message for one of these codes. Kept free of heavy imports so it can be tested alone.
"""


class NoTextFound(Exception):
    """The file was read but contained no text (typically a scan or a photo)."""


class UnreadableFile(Exception):
    """The file is damaged, protected, or not really the format it claims."""


class IndexOutdated(Exception):
    """A matter's index was built with different search models than the ones
    this worker uses, so adding to it would corrupt it."""


class DocumentDeleted(Exception):
    """The document was deleted while it was being indexed: stop and clean up."""


class OcrFailed(Exception):
    """Text recognition could not process the file (or ran out of time)."""


# What is stored for a failed file is one of these short codes, never a sentence:
# the web app turns each into plain language in the reader's own language
# (frontend/src/i18n/messages, upload.failure.*).
NO_TEXT = "no_text"
UNREADABLE = "unreadable"
TIMED_OUT = "timed_out"
INDEX_OUTDATED = "index_outdated"
UNEXPECTED = "unexpected"

# markitdown's own exception types, matched by name so this module needs no import.
_UNREADABLE_ERRORS = {
    "UnsupportedFormatException",
    "FileConversionException",
    "MissingDependencyException",
    "BadZipFile",
    "PdfReadError",
    "PDFSyntaxError",
    "UnicodeDecodeError",
}


def failure_reason(exc: BaseException) -> str:
    if isinstance(exc, NoTextFound):
        return NO_TEXT
    if isinstance(exc, IndexOutdated):
        return INDEX_OUTDATED
    if isinstance(exc, UnreadableFile):
        return UNREADABLE
    if isinstance(exc, OcrFailed):
        return TIMED_OUT if str(exc) == "timed out" else UNREADABLE
    if type(exc).__name__ in _UNREADABLE_ERRORS:
        return UNREADABLE
    return UNEXPECTED

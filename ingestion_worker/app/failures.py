"""Turns an indexing failure into a sentence a lawyer can act on.

The raw exception (paths, library internals) goes to the worker's log only; the
person sees one of these. Kept free of heavy imports so it can be tested alone.
"""


class NoTextFound(Exception):
    """The file was read but contained no text (typically a scan or a photo)."""


NO_TEXT = (
    "No text could be found in this file. If it is a scan or a photo of a document, "
    "it needs text recognition (OCR), which is not available yet."
)
UNREADABLE = (
    "This file could not be read. It may be damaged, protected by a password, "
    "or in a format that is not supported."
)
TIMED_OUT = "Processing this file took too long and was stopped. You can try again."
UNEXPECTED = (
    "Something went wrong while processing this file. Try again, and if it keeps "
    "failing, tell your administrator."
)

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
    if type(exc).__name__ in _UNREADABLE_ERRORS:
        return UNREADABLE
    return UNEXPECTED

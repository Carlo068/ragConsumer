"""Turns an indexing failure into a sentence a lawyer can act on.

The raw exception (paths, library internals) goes to the worker's log only; the
person sees one of these. Kept free of heavy imports so it can be tested alone.
"""


class NoTextFound(Exception):
    """The file was read but contained no text (typically a scan or a photo)."""


class UnreadableFile(Exception):
    """The file is damaged, protected, or not really the format it claims."""


class IndexOutdated(Exception):
    """A matter's index was built with different search models than the ones
    this worker uses, so adding to it would corrupt it."""


class OcrFailed(Exception):
    """Text recognition could not process the file (or ran out of time)."""


NO_TEXT = (
    "No text could be found in this file. If it is a scan or a photo of a document, "
    "it may be too faint, blurry or crooked to read. Try a clearer scan."
)
UNREADABLE = (
    "This file could not be read. It may be damaged, protected by a password, "
    "or in a format that is not supported."
)
TIMED_OUT = "Processing this file took too long and was stopped. You can try again."
INDEX_OUTDATED = (
    "The search index for this matter was built with an older search method and has to be "
    "rebuilt before new files can be added. Tell your administrator."
)
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
    if isinstance(exc, IndexOutdated):
        return INDEX_OUTDATED
    if isinstance(exc, UnreadableFile):
        return UNREADABLE
    if isinstance(exc, OcrFailed):
        return TIMED_OUT if str(exc) == "timed out" else UNREADABLE
    if type(exc).__name__ in _UNREADABLE_ERRORS:
        return UNREADABLE
    return UNEXPECTED

"""Converters for files MarkItDown does not handle: legacy Word (.doc) and
email (.eml, .msg). Law firms keep a lot of their record in email and in old
Word files, so these have to be searchable.

Emails become a small markdown document: the headers a lawyer would search for
(from, to, date, subject) followed by the body. Attachments are listed by name
but their contents are not indexed.
"""

import os
import subprocess
import tempfile
from email import policy
from email.parser import BytesParser

from app.failures import UnreadableFile

DOC_TIMEOUT_SECONDS = 120


def format_email(
    *,
    subject: str | None,
    sender: str | None,
    to: str | None,
    cc: str | None,
    date: str | None,
    attachments: list[str],
    body: str,
) -> str:
    lines = [f"# {subject.strip() or 'Correo sin asunto'}" if subject else "# Correo sin asunto", ""]
    for label, value in (("De", sender), ("Para", to), ("Cc", cc), ("Fecha", date), ("Asunto", subject)):
        if value and value.strip():
            lines.append(f"**{label}:** {value.strip()}  ")
    if attachments:
        lines.append(f"**Adjuntos:** {', '.join(attachments)}  ")
    lines += ["", body.strip()]
    return "\n".join(lines).strip() + "\n"


def _html_to_text(html: str, convert_html) -> str:
    # Emails with only an HTML body: reuse the document converter for HTML.
    fd, path = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        return convert_html(path)
    finally:
        os.remove(path)


def eml_to_text(path: str, convert_html) -> str:
    with open(path, "rb") as f:
        message = BytesParser(policy=policy.default).parse(f)

    body_part = message.get_body(preferencelist=("plain", "html"))
    body = ""
    if body_part is not None:
        content = body_part.get_content()
        body = _html_to_text(content, convert_html) if body_part.get_content_type() == "text/html" else content

    attachments = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
    return format_email(
        subject=str(message["subject"]) if message["subject"] else None,
        sender=str(message["from"]) if message["from"] else None,
        to=str(message["to"]) if message["to"] else None,
        cc=str(message["cc"]) if message["cc"] else None,
        date=str(message["date"]) if message["date"] else None,
        attachments=attachments,
        body=body,
    )


def msg_to_text(path: str, convert_html, open_msg=None) -> str:
    """Outlook .msg. `open_msg` lets tests supply a stand-in for extract_msg."""
    if open_msg is None:
        import extract_msg

        open_msg = extract_msg.openMsg
    try:
        message = open_msg(path)
    except Exception as exc:  # noqa: BLE001 - any parse failure means "can't read it"
        raise UnreadableFile(f"could not open .msg: {exc}") from exc
    try:
        body = message.body or ""
        if not body.strip() and getattr(message, "htmlBody", None):
            html = message.htmlBody
            body = _html_to_text(html.decode("utf-8", "replace") if isinstance(html, bytes) else html, convert_html)
        attachments = [a.longFilename or a.shortFilename for a in message.attachments if (a.longFilename or a.shortFilename)]
        return format_email(
            subject=message.subject,
            sender=message.sender,
            to=message.to,
            cc=message.cc,
            date=str(message.date) if message.date else None,
            attachments=attachments,
            body=body,
        )
    finally:
        close = getattr(message, "close", None)
        if close:
            close()


def doc_to_text(path: str) -> str:
    """Legacy Word (.doc, Word 97-2003) through antiword, as UTF-8."""
    try:
        result = subprocess.run(
            ["antiword", "-m", "UTF-8.txt", path],
            capture_output=True,
            timeout=DOC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise UnreadableFile("antiword timed out") from exc
    if result.returncode != 0:
        # Encrypted or not really a Word 97-2003 file (e.g. a .docx renamed .doc).
        raise UnreadableFile(result.stderr.decode(errors="replace")[-300:])
    return result.stdout.decode("utf-8", "replace")

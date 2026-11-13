import pathlib
import shutil
import subprocess

import pytest

from app import formats
from app.failures import UNREADABLE, UnreadableFile, failure_reason
from app.formats import doc_to_text, eml_to_text, format_email, msg_to_text

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def plain_html(path: str) -> str:
    """Stand-in for the HTML converter: strips tags crudely."""
    import re

    return re.sub(r"<[^>]+>", " ", pathlib.Path(path).read_text(encoding="utf-8"))


# ---- .eml ----

def test_an_email_is_indexed_with_the_headers_a_lawyer_would_search_for():
    text = eml_to_text(str(FIXTURES / "recordatorio.eml"), plain_html)
    assert text.startswith("# Recordatorio: audiencia del expediente 482/2025")
    assert "**De:** Ana Gómez <ana.gomez@despacho.mx>" in text
    assert "**Para:** Luis Pérez <luis.perez@cliente.mx>" in text
    assert "**Cc:** archivo@despacho.mx" in text
    assert "**Fecha:** Fri, 13 Mar 2026 10:15:00 -0600" in text
    assert "audiencia de conciliación se celebrará el próximo lunes" in text


def test_attachments_are_listed_by_name_but_not_indexed():
    text = eml_to_text(str(FIXTURES / "recordatorio.eml"), plain_html)
    assert "**Adjuntos:** citatorio.pdf" in text
    assert "%PDF" not in text


def test_an_html_only_email_in_latin1_keeps_its_accents():
    text = eml_to_text(str(FIXTURES / "notificacion.eml"), plain_html)
    assert "**De:** notificaciones@juzgado.gob.mx" in text
    assert "Notificación de sentencia" in text
    assert "sentencia definitiva" in text and "día quince" in text
    assert "<b>" not in text


def test_an_email_without_a_subject_still_gets_a_title():
    text = format_email(subject=None, sender="a@b.mx", to=None, cc=None, date=None, attachments=[], body="hola")
    assert text.startswith("# Correo sin asunto") and "hola" in text
    assert "**Para:**" not in text  # empty headers are left out


# ---- .msg ----

class FakeAttachment:
    longFilename = "contrato.docx"
    shortFilename = "CONTRA~1.DOC"


class FakeMsg:
    subject = "Revisión de contrato"
    sender = "Ana Gómez <ana@despacho.mx>"
    to = "Luis <luis@cliente.mx>"
    cc = None
    date = "2026-03-13 10:15:00"
    body = "Adjunto el contrato para su revisión."
    htmlBody = None
    attachments = [FakeAttachment()]
    closed = False

    def close(self):
        FakeMsg.closed = True


def test_an_outlook_message_is_indexed_like_an_email():
    text = msg_to_text("x.msg", plain_html, open_msg=lambda path: FakeMsg())
    assert text.startswith("# Revisión de contrato")
    assert "**De:** Ana Gómez <ana@despacho.mx>" in text
    assert "**Adjuntos:** contrato.docx" in text
    assert "Adjunto el contrato para su revisión." in text
    assert FakeMsg.closed


def test_an_outlook_message_with_only_an_html_body_is_converted():
    class HtmlOnly(FakeMsg):
        body = ""
        htmlBody = b"<p>Hola <b>mundo</b></p>"

    text = msg_to_text("x.msg", plain_html, open_msg=lambda path: HtmlOnly())
    assert "Hola" in text and "mundo" in text and "<p>" not in text


def test_a_broken_msg_is_reported_as_unreadable():
    def boom(path):
        raise ValueError("not an OLE file")

    with pytest.raises(UnreadableFile) as error:
        msg_to_text("x.msg", plain_html, open_msg=boom)
    assert failure_reason(error.value) == UNREADABLE


# ---- .doc ----

@pytest.mark.skipif(shutil.which("antiword") is None, reason="antiword is only in the worker image")
def test_a_real_word_97_document_is_read_with_its_accents():
    text = doc_to_text(str(FIXTURES / "convenio.doc"))
    assert "CONVENIO DE CONFIDENCIALIDAD" in text
    assert "información intercambiada" in text
    assert "CLÁUSULA SEGUNDA" in text


@pytest.mark.skipif(shutil.which("antiword") is None, reason="antiword is only in the worker image")
def test_something_that_is_not_a_doc_is_reported_as_unreadable(tmp_path):
    fake = tmp_path / "falso.doc"
    fake.write_bytes(b"this is not a word document at all")
    with pytest.raises(UnreadableFile) as error:
        doc_to_text(str(fake))
    assert failure_reason(error.value) == UNREADABLE


def test_a_hung_antiword_is_stopped_and_reported(monkeypatch):
    def hang(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(formats.subprocess, "run", hang)
    with pytest.raises(UnreadableFile):
        doc_to_text("x.doc")

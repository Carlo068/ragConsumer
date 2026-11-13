from app.chunking import chunk_markdown


def test_sections_are_split_on_headings_and_keep_their_heading():
    text = "# Contrato\n\nIntro del contrato.\n\n## Cláusula primera\n\nLa renta es mensual.\n\n## Cláusula segunda\n\nEl depósito es de dos meses."
    chunks = chunk_markdown(text)
    assert any(c.startswith("# Contrato") for c in chunks)
    assert any("## Cláusula primera" in c and "La renta es mensual." in c for c in chunks)
    assert not any("renta" in c and "depósito" in c for c in chunks)  # sections stay apart


def test_a_long_section_is_split_into_overlapping_pieces_of_at_most_1000_characters():
    text = "# Título\n\n" + " ".join(f"palabra{i}" for i in range(600))
    chunks = chunk_markdown(text)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)


def test_text_without_any_heading_is_still_chunked():
    assert chunk_markdown("Un párrafo sin encabezados.") == ["Un párrafo sin encabezados."]


def test_empty_text_gives_no_chunks():
    assert chunk_markdown("   \n\n  ") == []

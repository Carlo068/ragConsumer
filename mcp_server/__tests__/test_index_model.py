from app.index_model import fingerprint, is_compatible


def test_the_fingerprint_matches_what_the_worker_writes():
    # Must stay identical to ingestion_worker/app/index_model.py.
    assert fingerprint("jinaai/jina-embeddings-v2-base-es", "spanish") == (
        "jinaai/jina-embeddings-v2-base-es|bm25:spanish|idf"
    )


def test_only_a_collection_with_the_same_fingerprint_is_queried():
    fp = fingerprint("m", "spanish")
    assert is_compatible({"embedding": fp}, fp)
    assert not is_compatible({"embedding": fingerprint("m", "english")}, fp)
    assert not is_compatible(None, fp)


def test_the_two_services_share_one_copy_of_the_rule():
    import pathlib

    here = pathlib.Path(__file__).resolve()
    root = here.parents[2]
    worker = (root / "ingestion_worker" / "app" / "index_model.py")
    if worker.exists():  # only visible from the host, not inside a single service image
        assert worker.read_text(encoding="utf-8") == (root / "mcp_server" / "app" / "index_model.py").read_text(encoding="utf-8")

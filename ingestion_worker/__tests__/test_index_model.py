from app.failures import INDEX_OUTDATED, IndexOutdated, failure_reason
from app.index_model import fingerprint, is_compatible


def test_the_fingerprint_names_both_models_and_the_bm25_mode():
    assert fingerprint("jinaai/jina-embeddings-v2-base-es", "spanish") == (
        "jinaai/jina-embeddings-v2-base-es|bm25:spanish|idf"
    )


def test_a_collection_built_with_the_same_models_is_compatible():
    fp = fingerprint("m", "spanish")
    assert is_compatible({"embedding": fp}, fp)


def test_a_collection_built_with_other_models_is_not():
    assert not is_compatible({"embedding": fingerprint("old-model", "english")}, fingerprint("m", "spanish"))


def test_a_collection_with_no_fingerprint_is_not():
    # Collections made before the fingerprint existed used the old English model.
    assert not is_compatible(None, fingerprint("m", "spanish"))
    assert not is_compatible({}, fingerprint("m", "spanish"))


def test_an_outdated_index_gets_a_plain_language_reason():
    assert failure_reason(IndexOutdated("matter_x")) == INDEX_OUTDATED
    assert "rebuilt" in INDEX_OUTDATED

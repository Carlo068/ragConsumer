# Retrieval evaluation

Measures how well a search setup (embedding model + BM25 settings) finds the right
document for realistic Spanish legal questions. Data is in `spanish_legal/`
(fictional documents and 97 queries; see its README).

Run it in the ingestion-worker image, which has the same libraries and chunking as
production. It uses an in-memory Qdrant and never touches the real database,
storage or vectors:

```bash
docker compose run --rm --no-deps -v ./eval:/eval:ro --entrypoint python ingestion-worker \
  /eval/run_eval.py --dense BAAI/bge-small-en-v1.5 --bm25-language english
```

Options: `--dense <fastembed model>`, `--bm25-language <language>`, `--no-stemmer`, `--json`.

It reports recall@1/3/5 and MRR for dense-only, BM25-only and the hybrid (RRF) the
product uses, by query kind, plus cost: load and index time, query time, peak memory.

Caveat: the corpus is small (18 documents), so well-written keyword and detail
queries are easy for every setup. The differences that matter show up in the
paraphrase and question kinds, and in memory and speed. Add real, anonymised
firm questions here as they become available.

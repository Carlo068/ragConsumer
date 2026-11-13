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

## Results that decided KAN-79 (97 queries, hybrid = what the product uses)

| Dense model | BM25 | recall@1 | recall@3 | MRR | paraphrase r@1 | peak memory |
|---|---|---|---|---|---|---|
| bge-small-en-v1.5 (previous) | English | 0.90 | 0.96 | 0.93 | 0.68 | 1.5 GB |
| bge-small-en-v1.5 | Spanish | 0.88 | 0.95 | 0.92 | 0.63 | 1.5 GB |
| paraphrase-multilingual-MiniLM-L12-v2 | Spanish | 0.86 | 0.98 | 0.92 | 0.74 | 1.3 GB |
| paraphrase-multilingual-mpnet-base-v2 | Spanish | 0.84 | 0.97 | 0.91 | 0.58 | 3.4 GB |
| multilingual-e5-large | Spanish | 0.94 | 1.00 | 0.97 | 0.79 | 3.9 GB |
| **jina-embeddings-v2-base-es** | Spanish | **0.96** | **1.00** | **0.98** | **0.84** | 2.9 GB |

BM25 variants with jina-embeddings-v2-base-es: English 0.93/0.99; Spanish without
stemming 0.93/0.99; Spanish with stemming 0.96/1.00; **Spanish with stemming and
Qdrant's IDF modifier 0.97/0.99 (chosen: best recall@1 and sparse-only MRR 0.95)**.
Peak memory is the whole evaluation process (both models plus the in-memory index).

### Could indexing be faster? (KAN-99)

Measured on the 12-vCPU development VM, 256 chunks of about 800 characters with
jina-embeddings-v2-base-es (see `docs/indexing-speed.md`):

| Change | chunks/s | Hybrid recall@1 / @3 / MRR (97 queries) |
|---|---|---|
| as shipped | 3.6 | 0.97 / 0.99 / 0.97 |
| more threads (4, 8, 12) or batch size (16 to 128) | 3.1 to 3.9 | unchanged |
| 2 or 3 worker processes at once | 3.6 in total | unchanged |
| int8-quantized model (onnxruntime dynamic quantization) | 5.4 | **0.91** / 0.99 / 0.95, paraphrase r@1 0.74 |

Nothing safe was faster: the machine's CPU is already the limit, and the only change
that helped (int8, 1.5x) cost six points of recall@1, which is not worth it for legal
search. Not adopted.


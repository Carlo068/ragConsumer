"""Compares retrieval setups on the Spanish legal evaluation set (KAN-43).

Runs inside the ingestion-worker image, which already has the embedding
libraries and the worker's own chunking:

    docker compose run --rm --no-deps -v ./eval:/eval --entrypoint python \
        ingestion-worker /eval/run_eval.py --dense BAAI/bge-small-en-v1.5 --bm25-language english

Everything happens in memory (an in-process Qdrant): it never touches the real
database, storage or vectors. Measured at the document level: a query counts as
answered at rank N if a passage from a relevant document is in the first N
distinct documents returned.

Report: recall@1, recall@3, recall@5 and MRR for dense-only, BM25-only and the
hybrid (RRF) the product uses, broken down by query kind, plus the cost side:
model download size, indexing time, query time and peak memory.
"""

import argparse
import json
import pathlib
import resource
import statistics
import sys
import time
from collections import defaultdict

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

sys.path.insert(0, "/app")
from app.chunking import chunk_markdown  # noqa: E402  (the worker's own chunking)

DATA = pathlib.Path(__file__).parent / "spanish_legal"
TOP_CHUNKS = 30  # chunks retrieved per query before collapsing to documents


def load_corpus():
    chunks = []  # (slug, chunk_index, text)
    for path in sorted((DATA / "corpus").glob("*.md")):
        for index, text in enumerate(chunk_markdown(path.read_text(encoding="utf-8"))):
            chunks.append((path.stem, index, text))
    return chunks


def embed_passages(model, texts):
    method = getattr(model, "passage_embed", None) or model.embed
    return [v.tolist() for v in method(texts)]


def embed_query(model, text):
    method = getattr(model, "query_embed", None) or model.embed
    return next(iter(method([text]))).tolist()


def first_relevant_rank(ranked_slugs, relevant):
    seen = []
    for slug in ranked_slugs:
        if slug not in seen:
            seen.append(slug)
    for rank, slug in enumerate(seen, start=1):
        if slug in relevant:
            return rank
    return None


def metrics(ranks):
    n = len(ranks)
    return {
        "r@1": sum(1 for r in ranks if r and r <= 1) / n,
        "r@3": sum(1 for r in ranks if r and r <= 3) / n,
        "r@5": sum(1 for r in ranks if r and r <= 5) / n,
        "mrr": sum(1 / r for r in ranks if r) / n,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--bm25-language", default="english")
    parser.add_argument("--no-stemmer", action="store_true")
    parser.add_argument("--idf", action="store_true", help="enable Qdrant's IDF modifier on the sparse vector")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args()

    corpus = load_corpus()
    queries = json.loads((DATA / "queries.json").read_text(encoding="utf-8"))
    texts = [c[2] for c in corpus]

    started = time.time()
    dense = TextEmbedding(model_name=args.dense)
    sparse = SparseTextEmbedding(
        model_name="Qdrant/bm25", language=args.bm25_language, disable_stemmer=args.no_stemmer
    )
    load_seconds = time.time() - started

    started = time.time()
    dense_vectors = embed_passages(dense, texts)
    sparse_vectors = list(sparse.passage_embed(texts)) if hasattr(sparse, "passage_embed") else list(sparse.embed(texts))
    index_seconds = time.time() - started

    client = QdrantClient(":memory:")
    client.create_collection(
        "eval",
        vectors_config={"dense": models.VectorParams(size=len(dense_vectors[0]), distance=models.Distance.COSINE)},
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF if args.idf else None)
        },
    )
    client.upsert(
        "eval",
        [
            models.PointStruct(
                id=i,
                vector={
                    "dense": dense_vectors[i],
                    "sparse": models.SparseVector(
                        indices=sparse_vectors[i].indices.tolist(), values=sparse_vectors[i].values.tolist()
                    ),
                },
                payload={"slug": corpus[i][0]},
            )
            for i in range(len(corpus))
        ],
    )

    ranks = {mode: [] for mode in ("dense", "sparse", "hybrid")}
    by_kind = defaultdict(lambda: {mode: [] for mode in ("dense", "sparse", "hybrid")})
    misses = []
    query_times = []
    for q in queries:
        t0 = time.time()
        dvec = embed_query(dense, q["query"])
        svec = next(iter(sparse.query_embed(q["query"])))
        sparse_query = models.SparseVector(indices=svec.indices.tolist(), values=svec.values.tolist())
        results = {
            "dense": client.query_points("eval", query=dvec, using="dense", limit=TOP_CHUNKS, with_payload=True),
            "sparse": client.query_points("eval", query=sparse_query, using="sparse", limit=TOP_CHUNKS, with_payload=True),
            "hybrid": client.query_points(
                "eval",
                prefetch=[
                    models.Prefetch(query=dvec, using="dense", limit=20),
                    models.Prefetch(query=sparse_query, using="sparse", limit=20),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=TOP_CHUNKS,
                with_payload=True,
            ),
        }
        query_times.append(time.time() - t0)
        for mode, result in results.items():
            rank = first_relevant_rank([p.payload["slug"] for p in result.points], set(q["relevant"]))
            ranks[mode].append(rank)
            by_kind[q["kind"]][mode].append(rank)
            if mode == "hybrid" and (rank is None or rank > 3):
                misses.append((q["id"], q["kind"], q["query"], rank))

    report = {
        "dense": args.dense,
        "bm25_language": args.bm25_language,
        "stemmer": not args.no_stemmer,
        "idf": args.idf,
        "chunks": len(corpus),
        "queries": len(queries),
        "overall": {mode: metrics(r) for mode, r in ranks.items()},
        "by_kind_hybrid": {kind: metrics(v["hybrid"]) | {"n": len(v["hybrid"])} for kind, v in sorted(by_kind.items())},
        "cost": {
            "model_load_s": round(load_seconds, 1),
            "index_s": round(index_seconds, 1),
            "query_ms_median": round(statistics.median(query_times) * 1000),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        },
        "hybrid_misses_beyond_rank_3": misses,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return

    print(f"\n{args.dense}  |  BM25: {args.bm25_language}{'' if not args.no_stemmer else ' (no stemmer)'}")
    print(f"{len(corpus)} chunks from {len({c[0] for c in corpus})} documents, {len(queries)} queries")
    print(f"{'mode':8} {'r@1':>6} {'r@3':>6} {'r@5':>6} {'mrr':>6}")
    for mode, m in report["overall"].items():
        print(f"{mode:8} {m['r@1']:6.2f} {m['r@3']:6.2f} {m['r@5']:6.2f} {m['mrr']:6.2f}")
    print("hybrid by kind:")
    for kind, m in report["by_kind_hybrid"].items():
        print(f"  {kind:11} n={m['n']:3}  r@1 {m['r@1']:.2f}  r@3 {m['r@3']:.2f}  mrr {m['mrr']:.2f}")
    c = report["cost"]
    print(f"cost: load {c['model_load_s']}s, index {c['index_s']}s, query {c['query_ms_median']}ms, peak {c['peak_rss_mb']}MB")
    if misses:
        print("hybrid misses (rank>3):")
        for qid, kind, query, rank in misses:
            print(f"  {qid} [{kind}] rank={rank}: {query}")


if __name__ == "__main__":
    main()

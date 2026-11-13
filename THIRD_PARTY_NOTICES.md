# Third-party components

ragConsumer is built from the components below. They keep their own licenses;
the project's own license (`LICENSE`) does not apply to them. This list was
compiled from the installed packages' own metadata and the well-known licenses of
the container images; re-check it when dependencies change.

## Services run as separate containers (unmodified)

| Component | License | Note |
|---|---|---|
| PostgreSQL 16 | PostgreSQL License | |
| MinIO | **AGPL-3.0** | Used unmodified, as a separate network service. The AGPL's source-offer duty applies to MinIO itself and to anyone who *modifies* it; do not patch the MinIO image without reading the license. |
| Qdrant | Apache-2.0 | |
| Caddy | Apache-2.0 | |
| nginx (web app image) | BSD-2-Clause | |

## Python dependencies that need attention

Almost everything is MIT, BSD or Apache-2.0. Items with copyleft or
file-level terms:

| Package | Where | License | What it means here |
|---|---|---|---|
| `extract-msg`, `pcodedmp` | ingestion worker (reading Outlook `.msg`) | **GPL-3.0** | Fine for running the system privately. **Distributing the worker container image (or a copy of the installed packages) to others requires offering the corresponding source under the GPL for those packages.** If the worker image is ever shared outside the firm, either comply or drop `.msg` support. |
| `antiword` (system tool, reads `.doc`) | ingestion worker image | GPL-2.0 | Run as a separate program; same distribution note as above. |
| Ghostscript (system tool, used by OCR) | ingestion worker image | **AGPL-3.0** | Run as a separate program on the server's own files; same distribution note as above. |
| `psycopg`, `psycopg-binary` | backend, worker, MCP server | LGPL-3.0 | Used unmodified as a library: allowed. |
| `fpdf2`, `img2pdf`, `RTFDE` | ingestion worker | LGPL-3.0 | Used unmodified as libraries: allowed. |
| `ocrmypdf`, `pikepdf`, `certifi`, `tqdm`, `orjson` | various | MPL-2.0 (some dual-licensed) | File-level copyleft; used unmodified: allowed. |

Running the system for one firm on that firm's own server (no copy of the
software given to anyone else) triggers none of the distribution duties above.

## Models (downloaded when the worker and MCP server first start)

| Model | License |
|---|---|
| `jinaai/jina-embeddings-v2-base-es` (dense embeddings) | Apache-2.0 |
| `Qdrant/bm25` (sparse/keyword) and its Spanish stemmer data | Apache-2.0 |
| Tesseract language data `spa`, `eng` (OCR) | Apache-2.0 |

## Web app (direct dependencies)

MIT (React, Tailwind, Base UI, fflate, clsx and others), ISC (lucide-react),
Apache-2.0 (class-variance-authority) and the Geist font under the SIL Open Font
License 1.1. Transitive dependencies of the web app were not audited
individually.

# How fast documents become searchable

Turning an uploaded file into something the AI can search means reading its text (and
OCR for scans), cutting it into fragments, and computing a meaning-vector for each. The
last step dominates, and it is limited by the server's CPU.

## What to expect

Measured on a 12-vCPU machine (the largest numbers we have; expect the same or lower on a
4 to 8 vCPU server):

| Work | Time |
|---|---|
| Computing vectors | about **3.6 fragments per second** (a fragment is roughly a paragraph, 800 characters) |
| A typical contract or letter (10 to 40 fragments) | seconds |
| A 100-page text PDF (about 600 fragments) | about 3 minutes |
| A dense 1,300-page PDF (3.2 MB, about 7,800 fragments) | about 35 minutes |
| A 4,000-page, 10 MB PDF (about 30,000 fragments) | about 19 minutes to read, then about 2 hours to index |
| Scanned pages (OCR) | add roughly a few seconds per page before indexing |

Memory stays bounded whatever the size (about 2 GB peak); only time grows.

## Planning a large first upload

- Do the bulk load **before** people start relying on the system, or at night: the worker
  processes documents one after another, so a big batch delays small documents queued
  behind it.
- The upload screen shows each file's state ("En espera", "Leyendo…", "Listo para
  buscar"); a lawyer can start working with the files that are already ready.
- 10,000 fragments take about 45 minutes; a firm archive of 1,000 ordinary documents
  (about 25,000 fragments) takes about 2 hours.

## Why it is not faster (measured, KAN-99)

| Tried | Result |
|---|---|
| More processing threads, or larger batches | No change (3.1 to 3.9 fragments/s): the CPU is already fully used |
| Two or three worker processes at once | The same total (3.6/s split between them): adding workers does not help on one server |
| An int8-quantized version of the model | 1.5 times faster (5.4/s) but hybrid recall@1 falls from 0.97 to 0.91: **rejected**, retrieval quality matters more than speed here |

What would help: a server with faster (not just more) cores, or a GPU, at a cost the
firm would decide on; or accepting a smaller model at the price of recall (the evaluation
set in `eval/` measures that trade-off in minutes). Changing the model means re-indexing
every document (`backend/scripts/reindex_all.py`).

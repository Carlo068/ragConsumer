# Spanish legal retrieval evaluation set

This folder holds a small Spanish-language legal retrieval benchmark modeled on the documents a Mexican law firm in Chihuahua would store.

- All data is fictional: every person, company, address, case number, amount and date was invented. Any resemblance to real people or proceedings is accidental. Statute references are for realism only and are not legal advice.
- `corpus/` has 18 markdown documents (300-600 words each), one per document type. Several are deliberate near-pairs (the two leases, demanda vs. laudo for dismissal, demanda de amparo directo vs. informe justificado, the NDA vs. the loan contract) so retrieval must separate them by details such as parties, amounts and dates.
- The document id is the file name without `.md`, for example `contrato-arrendamiento-local-comercial`.
- `queries.json` is a JSON array of objects `{"id", "query", "relevant", "kind"}`. `relevant` lists the document id(s) that answer the query; each fact was checked against the corpus text and appears only in the listed document(s).
- Query kinds: `paraphrase` (different wording than the document, such as "alquiler" for "arrendamiento"), `detail` (a specific amount, date, name or clause, often distinguishing similar documents), `keyword` (short keyword-style search), `no-accents` (lowercase, accents omitted, like a rushed lawyer), and `question` (a full natural-language question).
- Suggested metrics: hit rate / recall@k and MRR at document level, reported per query kind.
- Purpose: compare embedding models and BM25 settings (accent folding, stemming, stop words, hybrid weights) for the Spanish document search, tracked in KAN-43 / KAN-79.
- Documents are chunked by the retrieval system under test, so chunk hits must be mapped back to their source document before scoring.

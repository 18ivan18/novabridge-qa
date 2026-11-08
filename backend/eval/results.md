# Retrieval evaluation

Embedder: `BAAI/bge-small-en-v1.5`. Overlap: 60 tokens. Candidates per retriever: 20. RRF k: 60. Filings indexed: 6. Questions: 45 answerable, 8 unanswerable. Unfiltered searches over all filings; a question counts as found only in the filing it names.

## Recall and MRR

MRR counts ranks up to 10.

| Chunk tokens | Chunks | Mode | Questions | R@1 | R@3 | R@6 | R@8 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|---|---|---|---|
| 200 | 2363 | hybrid | HTM filings (24) | 0.62 | 0.75 | 0.83 | 0.92 | 0.92 | 0.96 | 0.710 |
| 200 | 2363 | hybrid | TXT filings (21) | 0.24 | 0.67 | 0.81 | 0.86 | 0.90 | 0.95 | 0.480 |
| 200 | 2363 | dense | HTM filings (24) | 0.46 | 0.67 | 0.88 | 0.96 | 0.96 | 0.96 | 0.608 |
| 200 | 2363 | dense | TXT filings (21) | 0.33 | 0.62 | 0.86 | 0.86 | 0.86 | 0.95 | 0.513 |
| 200 | 2363 | sparse | HTM filings (24) | 0.42 | 0.62 | 0.67 | 0.67 | 0.67 | 0.88 | 0.515 |
| 200 | 2363 | sparse | TXT filings (21) | 0.19 | 0.33 | 0.57 | 0.67 | 0.71 | 0.71 | 0.336 |
| 300 | 1434 | hybrid | HTM filings (24) | 0.54 | 0.83 | 0.88 | 0.88 | 0.88 | 0.96 | 0.684 |
| 300 | 1434 | hybrid | TXT filings (21) | 0.38 | 0.67 | 0.86 | 0.86 | 0.86 | 0.90 | 0.552 |
| 300 | 1434 | dense | HTM filings (24) | 0.46 | 0.83 | 0.92 | 0.96 | 0.96 | 0.96 | 0.664 |
| 300 | 1434 | dense | TXT filings (21) | 0.43 | 0.62 | 0.71 | 0.81 | 0.81 | 0.90 | 0.548 |
| 300 | 1434 | sparse | HTM filings (24) | 0.25 | 0.58 | 0.79 | 0.79 | 0.79 | 0.79 | 0.446 |
| 300 | 1434 | sparse | TXT filings (21) | 0.29 | 0.43 | 0.57 | 0.67 | 0.76 | 0.81 | 0.390 |
| 400 | 1028 | hybrid | HTM filings (24) | 0.58 | 0.79 | 0.83 | 0.83 | 0.83 | 0.92 | 0.684 |
| 400 | 1028 | hybrid | TXT filings (21) | 0.33 | 0.62 | 0.76 | 0.81 | 0.81 | 0.81 | 0.496 |
| 400 | 1028 | dense | HTM filings (24) | 0.54 | 0.71 | 0.75 | 0.79 | 0.88 | 0.92 | 0.642 |
| 400 | 1028 | dense | TXT filings (21) | 0.33 | 0.57 | 0.71 | 0.71 | 0.76 | 0.81 | 0.484 |
| 400 | 1028 | sparse | HTM filings (24) | 0.29 | 0.71 | 0.75 | 0.75 | 0.79 | 0.83 | 0.487 |
| 400 | 1028 | sparse | TXT filings (21) | 0.24 | 0.38 | 0.52 | 0.62 | 0.71 | 0.90 | 0.361 |

## Candidates before fusion

Each retriever passes its top 20 passages to RRF. *Either* is the share found by at least one of them: the most hybrid search can return. *Lost by fusion* lists questions found by a retriever but not in the fused top 6.

| Chunk tokens | Questions | Dense R@20 | BM25 R@20 | Either R@20 | Hybrid R@6 | Only dense | Only BM25 | Lost by fusion |
|---|---|---|---|---|---|---|---|---|
| 200 | HTM filings (24) | 0.96 | 0.88 | 0.96 | 0.83 | a25, n24 | none | a23, m25, n24 |
| 200 | TXT filings (21) | 0.95 | 0.71 | 0.95 | 0.81 | a01, a02, m01, m04, m07 | none | a02, m07, n01 |
| 300 | HTM filings (24) | 0.96 | 0.79 | 0.96 | 0.88 | a25, a27, m25, n24 | none | m25, n24 |
| 300 | TXT filings (21) | 0.90 | 0.81 | 0.95 | 0.86 | a01, m01, m07 | m02 | a01, m02 |
| 400 | HTM filings (24) | 0.92 | 0.83 | 0.96 | 0.83 | a25, a27, n24 | m28 | a25, m28, n24 |
| 400 | TXT filings (21) | 0.81 | 0.90 | 0.90 | 0.76 | none | m01, m02 | m01, m02, n02 |

## Questions not found within top 6

A rank of None means the passage was not in the top 20.

| Chunk tokens | Mode | Question | Rank |
|---|---|---|---|
| 200 | hybrid | a02 | 11 |
| 200 | hybrid | m07 | 9 |
| 200 | hybrid | n01 | 7 |
| 200 | hybrid | n04 | None |
| 200 | hybrid | a23 | 7 |
| 200 | hybrid | m25 | 14 |
| 200 | hybrid | m28 | None |
| 200 | hybrid | n24 | 8 |
| 200 | dense | m06 | 18 |
| 200 | dense | n01 | 18 |
| 200 | dense | n04 | None |
| 200 | dense | a23 | 8 |
| 200 | dense | m25 | 7 |
| 200 | dense | m28 | None |
| 200 | sparse | a01 | None |
| 200 | sparse | a02 | None |
| 200 | sparse | a03 | 9 |
| 200 | sparse | m01 | None |
| 200 | sparse | m04 | None |
| 200 | sparse | m07 | None |
| 200 | sparse | n02 | 8 |
| 200 | sparse | n04 | None |
| 200 | sparse | n06 | 7 |
| 200 | sparse | a22 | 11 |
| 200 | sparse | a23 | 11 |
| 200 | sparse | a25 | None |
| 200 | sparse | a27 | 16 |
| 200 | sparse | m25 | 20 |
| 200 | sparse | m28 | None |
| 200 | sparse | n23 | 19 |
| 200 | sparse | n24 | None |
| 300 | hybrid | a01 | None |
| 300 | hybrid | m02 | 15 |
| 300 | hybrid | n04 | None |
| 300 | hybrid | m25 | 14 |
| 300 | hybrid | m28 | None |
| 300 | hybrid | n24 | 12 |
| 300 | dense | a01 | 17 |
| 300 | dense | m02 | None |
| 300 | dense | m04 | 14 |
| 300 | dense | m06 | 7 |
| 300 | dense | n01 | 8 |
| 300 | dense | n04 | None |
| 300 | dense | m25 | 7 |
| 300 | dense | m28 | None |
| 300 | sparse | a01 | None |
| 300 | sparse | a03 | 8 |
| 300 | sparse | a07 | 7 |
| 300 | sparse | m01 | None |
| 300 | sparse | m02 | 9 |
| 300 | sparse | m04 | 12 |
| 300 | sparse | m07 | None |
| 300 | sparse | n04 | None |
| 300 | sparse | n06 | 9 |
| 300 | sparse | a25 | None |
| 300 | sparse | a27 | None |
| 300 | sparse | m25 | None |
| 300 | sparse | m28 | None |
| 300 | sparse | n24 | None |
| 400 | hybrid | a01 | None |
| 400 | hybrid | m01 | None |
| 400 | hybrid | m02 | None |
| 400 | hybrid | n02 | 7 |
| 400 | hybrid | n04 | None |
| 400 | hybrid | a25 | 18 |
| 400 | hybrid | m25 | None |
| 400 | hybrid | m28 | None |
| 400 | hybrid | n24 | 16 |
| 400 | dense | a01 | None |
| 400 | dense | m01 | None |
| 400 | dense | m02 | None |
| 400 | dense | m06 | 10 |
| 400 | dense | n01 | 15 |
| 400 | dense | n04 | None |
| 400 | dense | a21 | 17 |
| 400 | dense | a25 | 9 |
| 400 | dense | m25 | None |
| 400 | dense | m28 | None |
| 400 | dense | n23 | 7 |
| 400 | dense | n24 | 9 |
| 400 | sparse | a01 | None |
| 400 | sparse | a03 | 10 |
| 400 | sparse | a07 | 8 |
| 400 | sparse | m01 | 12 |
| 400 | sparse | m02 | 12 |
| 400 | sparse | m03 | 7 |
| 400 | sparse | m04 | 16 |
| 400 | sparse | m07 | 16 |
| 400 | sparse | n04 | None |
| 400 | sparse | n06 | 10 |
| 400 | sparse | a25 | None |
| 400 | sparse | a27 | None |
| 400 | sparse | m25 | None |
| 400 | sparse | m28 | 13 |
| 400 | sparse | n23 | 10 |
| 400 | sparse | n24 | None |

## Relevance gate (MIN_RELEVANCE)

### 200 tokens

Best dense similarity: answerable min 0.667, median 0.783; off-topic max 0.543; in-domain unanswerable max 0.719.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 45/45 | 2/3 | 0/5 |
| 0.55 | 45/45 | 3/3 | 0/5 |
| 0.60 | 45/45 | 3/3 | 0/5 |
| 0.65 | 45/45 | 3/3 | 0/5 |
| 0.70 | 43/45 | 3/3 | 3/5 |
| 0.75 | 39/45 | 3/3 | 5/5 |

### 300 tokens

Best dense similarity: answerable min 0.658, median 0.776; off-topic max 0.535; in-domain unanswerable max 0.704.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 45/45 | 2/3 | 0/5 |
| 0.55 | 45/45 | 3/3 | 0/5 |
| 0.60 | 45/45 | 3/3 | 0/5 |
| 0.65 | 45/45 | 3/3 | 1/5 |
| 0.70 | 43/45 | 3/3 | 4/5 |
| 0.75 | 36/45 | 3/3 | 5/5 |

### 400 tokens

Best dense similarity: answerable min 0.665, median 0.771; off-topic max 0.528; in-domain unanswerable max 0.716.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 45/45 | 2/3 | 0/5 |
| 0.55 | 45/45 | 3/3 | 0/5 |
| 0.60 | 45/45 | 3/3 | 0/5 |
| 0.65 | 45/45 | 3/3 | 0/5 |
| 0.70 | 43/45 | 3/3 | 3/5 |
| 0.75 | 32/45 | 3/3 | 5/5 |

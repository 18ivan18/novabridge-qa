# Retrieval evaluation

Embedder: `BAAI/bge-small-en-v1.5`. Overlap: 60 tokens. Candidates per retriever: 20. RRF k: 60. Questions: 21 answerable, 8 unanswerable. Unfiltered searches.

## Recall and MRR

| Chunk tokens | Chunks | Mode | R@1 | R@3 | R@6 | R@8 | R@10 | MRR |
|---|---|---|---|---|---|---|---|---|
| 200 | 1005 | hybrid | 0.38 | 0.81 | 0.86 | 0.90 | 0.90 | 0.596 |
| 200 | 1005 | dense | 0.48 | 0.81 | 0.90 | 0.90 | 0.95 | 0.648 |
| 200 | 1005 | sparse | 0.24 | 0.52 | 0.67 | 0.71 | 0.76 | 0.413 |
| 300 | 613 | hybrid | 0.57 | 0.81 | 0.81 | 0.86 | 0.86 | 0.689 |
| 300 | 613 | dense | 0.52 | 0.62 | 0.81 | 0.81 | 0.86 | 0.604 |
| 300 | 613 | sparse | 0.33 | 0.62 | 0.67 | 0.76 | 0.86 | 0.491 |
| 400 | 438 | hybrid | 0.52 | 0.71 | 0.86 | 0.86 | 0.86 | 0.647 |
| 400 | 438 | dense | 0.38 | 0.67 | 0.76 | 0.81 | 0.81 | 0.535 |
| 400 | 438 | sparse | 0.29 | 0.57 | 0.76 | 0.90 | 0.90 | 0.470 |

## Questions not found within top 6

A rank of None means the passage was not in the top 10.

| Chunk tokens | Mode | Question | Rank |
|---|---|---|---|
| 200 | hybrid | a02 | None |
| 200 | hybrid | n02 | 7 |
| 200 | hybrid | n04 | None |
| 200 | dense | n01 | 10 |
| 200 | dense | n04 | None |
| 200 | sparse | a01 | None |
| 200 | sparse | a02 | None |
| 200 | sparse | a03 | 10 |
| 200 | sparse | m01 | None |
| 200 | sparse | m04 | 8 |
| 200 | sparse | m07 | None |
| 200 | sparse | n04 | None |
| 300 | hybrid | a01 | None |
| 300 | hybrid | m02 | None |
| 300 | hybrid | n02 | 7 |
| 300 | hybrid | n04 | None |
| 300 | dense | a01 | None |
| 300 | dense | m02 | None |
| 300 | dense | m04 | 10 |
| 300 | dense | n04 | None |
| 300 | sparse | a01 | None |
| 300 | sparse | a03 | 8 |
| 300 | sparse | m01 | None |
| 300 | sparse | m02 | 7 |
| 300 | sparse | m07 | 9 |
| 300 | sparse | n04 | None |
| 300 | sparse | n06 | 10 |
| 400 | hybrid | a01 | None |
| 400 | hybrid | m02 | None |
| 400 | hybrid | n04 | None |
| 400 | dense | a01 | None |
| 400 | dense | m01 | None |
| 400 | dense | m02 | None |
| 400 | dense | n01 | 8 |
| 400 | dense | n04 | None |
| 400 | sparse | a01 | None |
| 400 | sparse | a03 | 8 |
| 400 | sparse | m02 | 8 |
| 400 | sparse | n04 | None |
| 400 | sparse | n06 | 7 |

## Relevance gate (MIN_RELEVANCE)

### 200 tokens

Best dense similarity: answerable min 0.667, median 0.763; off-topic max 0.486; in-domain unanswerable max 0.753.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 21/21 | 3/3 | 0/5 |
| 0.55 | 21/21 | 3/3 | 0/5 |
| 0.60 | 21/21 | 3/3 | 0/5 |
| 0.65 | 21/21 | 3/3 | 0/5 |
| 0.70 | 20/21 | 3/3 | 1/5 |
| 0.75 | 14/21 | 3/3 | 4/5 |

### 300 tokens

Best dense similarity: answerable min 0.660, median 0.751; off-topic max 0.478; in-domain unanswerable max 0.769.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 21/21 | 3/3 | 0/5 |
| 0.55 | 21/21 | 3/3 | 0/5 |
| 0.60 | 21/21 | 3/3 | 0/5 |
| 0.65 | 21/21 | 3/3 | 0/5 |
| 0.70 | 19/21 | 3/3 | 1/5 |
| 0.75 | 12/21 | 3/3 | 4/5 |

### 400 tokens

Best dense similarity: answerable min 0.661, median 0.747; off-topic max 0.491; in-domain unanswerable max 0.777.

| Threshold | Answerable kept | Off-topic blocked | In-domain unanswerable blocked |
|---|---|---|---|
| 0.50 | 21/21 | 3/3 | 0/5 |
| 0.55 | 21/21 | 3/3 | 0/5 |
| 0.60 | 21/21 | 3/3 | 0/5 |
| 0.65 | 21/21 | 3/3 | 0/5 |
| 0.70 | 19/21 | 3/3 | 1/5 |
| 0.75 | 9/21 | 3/3 | 4/5 |

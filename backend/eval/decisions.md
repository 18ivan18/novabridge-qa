# Tuning decisions

Results are in `results.md`, produced by `run_eval.py` with `bge-small-en-v1.5`.

**Read these numbers with care.** There are 21 answerable questions, so one question moves recall
by 0.048, and most gaps between settings are one or two questions. The questions and evidence
patterns are also the ones used to decide on the indexing header below, so scores are optimistic.

| Setting | Value | Why |
|---|---|---|
| Retrieval mode | hybrid | Best MRR at 300 and 400 tokens, and it does not depend on one retriever. At 200 tokens dense scored higher, so this is a judgment call, not a clear win. |
| `CHUNK_TOKENS` | 400 (unchanged) | Ties for the best hybrid recall@6 (0.86). 300 ranks the answer higher (MRR 0.689 against 0.647) but has lower recall@6 (0.81). No setting wins clearly, so the default stays. |
| `TOP_K` | 6 (unchanged) | Hybrid recall at 400 tokens stays at 0.86 from k=6 to k=10, so more passages would only add noise to the prompt. |
| `MIN_RELEVANCE` | 0.58 | Roughly halfway between the highest off-topic score (0.491) and the lowest answerable score (0.661). The earlier 0.35 suited a different model and would block nothing here. |

## Indexing header

Filings say "the Company" rather than the company's name, so chunks had no link to the company a
question names. Title and section are now added to the text that is embedded and indexed for BM25.
Stored and cited text is unchanged.

| Hybrid, 400 tokens | R@1 | R@3 | R@6 | R@10 | MRR |
|---|---|---|---|---|---|
| Without header | 0.52 | 0.62 | 0.76 | 0.90 | 0.604 |
| With header | 0.52 | 0.71 | 0.86 | 0.86 | 0.647 |

## What the relevance gate cannot do

The gate blocks off-topic questions only. In-domain unanswerable questions, such as Apple's iPhone
revenue, score up to 0.777, above the median answerable question (0.747), so no threshold separates
them. Those rely on the second layer: the model replying `INSUFFICIENT_EVIDENCE`.

## Known misses at the chosen settings

`a01`, `m02` and `n04` are not found in the top 10. `n04` describes 3dfx without naming it, so
neither retriever can connect them.

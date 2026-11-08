# Answer evaluation

Run `2026-11-08-openai-gpt-oss-120b`: model `openai/gpt-oss-120b` (openai_compatible), embedder `BAAI/bge-small-en-v1.5`, top_k 6, min_relevance 0.58, chunk_tokens 400, index of 1028 chunks, commit `323773e`. Raw answers: `eval/answer_runs/2026-11-08-openai-gpt-oss-120b.jsonl`.

**Correct** means the answer states every expected fact of the question. **Evidence cited** means a cited passage from the filing the question names contains its evidence. **Cited only the other filing** counts answers whose sources from that company all come from its other generation of filings. The figure check (task 3) is not available yet.

## Answerable questions

| Questions | Answered | Correct | Evidence cited | Cited only the other filing | Refused: gate / model / no citations | Errors | Not asked |
|---|---|---|---|---|---|---|---|
| HTM filings (24) | 23/24 | 23/24 | 22/24 | 0/24 | 0 / 1 / 0 | 0 | 0 |
| TXT filings (21) | 19/21 | 17/21 | 16/21 | 1/21 | 0 / 2 / 0 | 0 | 0 |

## Unanswerable questions

| Questions | Refused | By the gate | By the model | No valid citations | Answered | Errors | Not asked |
|---|---|---|---|---|---|---|---|
| Off-topic (3) | 3/3 | 3 | 0 | 0 | 0 | 0 | 0 |
| In-domain unanswerable (5) | 5/5 | 0 | 5 | 0 | 0 | 0 | 0 |

## Cost

- LLM calls: 50 (the gate answered 3 without one).
- Latency per question with an LLM call: median 1483 ms, 95th percentile 1894 ms.
- Tokens: 137,219 in, 9,549 out.

## Per question

| Question | Set | Outcome | Correct | Evidence cited | Cited filings | Missing facts | ms | Tokens |
|---|---|---|---|---|---|---|---|---|
| a21 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1179 | 2,929 |
| a22 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1822 | 2,979 |
| a23 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1095 | 2,926 |
| a24 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1132 | 2,554 |
| a25 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1585 | 2,968 |
| a26 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1566 | 2,708 |
| a27 | HTM filings (24) | answered | yes | yes | AAPL 2000-09-30, AAPL 2026-09-26 | — | 1240 | 2,853 |
| a28 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1498 | 2,960 |
| m21 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1133 | 3,064 |
| m22 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1409 | 3,038 |
| m23 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1509 | 3,082 |
| m24 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1605 | 2,692 |
| m25 | HTM filings (24) | refused (model) | **no** | **no** | — | `133,749\|133\.7\d* ?billion` | 1387 | 2,803 |
| m26 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1192 | 2,979 |
| m27 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1140 | 2,790 |
| m28 | HTM filings (24) | answered | yes | **no** | MSFT 2026-06-30 | — | 1296 | 2,877 |
| n21 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1198 | 2,749 |
| n22 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1173 | 2,709 |
| n23 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1895 | 3,080 |
| n24 | HTM filings (24) | answered | yes | yes | NVDA 2001-01-28, NVDA 2026-01-25 | — | 1706 | 3,120 |
| n25 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25, NVDA 2001-01-28 | — | 1490 | 3,013 |
| n26 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1628 | 3,117 |
| n27 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1508 | 2,909 |
| n28 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1425 | 2,979 |
| a01 | TXT filings (21) | refused (model) | **no** | **no** | — | `8,568` | 1353 | 2,785 |
| a02 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1278 | 2,621 |
| a03 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1509 | 2,641 |
| a04 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1693 | 3,016 |
| a05 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1894 | 3,189 |
| a06 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1365 | 2,760 |
| a07 | TXT filings (21) | answered | yes | **no** | AAPL 2000-09-30 | — | 1476 | 2,563 |
| a08 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1254 | 2,984 |
| m01 | TXT filings (21) | answered | **no** | **no** | MSFT 2026-06-30 | `47,600` | 1553 | 2,850 |
| m02 | TXT filings (21) | answered | yes | **no** | MSFT 2001-06-30 | — | 1534 | 3,558 |
| m03 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 2011 | 3,326 |
| m04 | TXT filings (21) | answered | **no** | yes | MSFT 2026-06-30, MSFT 2001-06-30 | `has not paid cash dividends\|not paid any cash dividends\|no cash dividends\|never paid` | 1604 | 3,084 |
| m05 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 1791 | 3,529 |
| m06 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 1254 | 3,041 |
| m07 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 1351 | 2,520 |
| n01 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1775 | 3,059 |
| n02 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1491 | 2,897 |
| n03 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1530 | 3,043 |
| n04 | TXT filings (21) | refused (model) | **no** | **no** | — | `3dfx` | 1210 | 3,051 |
| n05 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1809 | 3,092 |
| n06 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1554 | 3,243 |
| u01 | Off-topic (3) | refused (gate) | — | — | — | — | 789 | — |
| u02 | Off-topic (3) | refused (gate) | — | — | — | — | 733 | — |
| u03 | Off-topic (3) | refused (gate) | — | — | — | — | 539 | — |
| u04 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 1281 | 2,660 |
| u08 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 1208 | 2,920 |
| u09 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 1212 | 3,061 |
| u10 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 1535 | 2,648 |
| u11 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 1228 | 2,749 |

## Answers

**a21.** How many full-time equivalent employees did Apple have at the end of fiscal 2026?

> Apple reported that, as of September 26 2026 (the end of its fiscal 2026 year), it had approximately 167,000 full‑time equivalent employees[1].

**a22.** What were Apple's total net sales in fiscal 2026?

> Apple reported total net sales of $478,834 million for fiscal 2026 [1][2][3].

**a23.** How much revenue did Apple earn from the iPhone in 2026?

> Apple reported iPhone net sales of $254,098 million for the fiscal year ended September 26, 2026 [1][2]. This figure represents the revenue generated from iPhone products in that year.

**a24.** What was Apple's effective tax rate in 2026?

> Apple’s effective tax rate for 2026 was 17.0%[1][2]

**a25.** How many of its own shares did Apple buy back in 2026, and for how much?

> Apple repurchased ≈ 297 million of its own shares in 2026, spending about $85.8 billion on the buy‑back [1]. The same $85.8 billion figure is confirmed in the discussion of 2026 capital returns [2].

**a26.** Where are Apple's manufacturing partners located?

> Apple’s manufacturing partners are primarily located in Asia, with the bulk of outsourcing partners based in China mainland, India, Japan, South Korea, Taiwan and Vietnam, and additional sourcing from partners and facilities in the United States[1][2]. The company also relies on partners in Asia for the final assembly of essentially all of its hardware products[1]. These locations reflect the company’s extensive use of overseas outsourcing partners for component and product manufacturing.

**a27.** How many shareholders of record did Apple have?

> Apple reported 24,998 shareholders of record as of December 1, 2000 [1]. More recently, the company disclosed 21,458 shareholders of record as of October 23, 2026 [2].

**a28.** How much did Apple's net sales in Greater China grow in 2026?

> Apple’s Greater China net sales rose from $64,377 million in 2025 to $82,378 million in 2026, an increase of $18,001 million, or about a 28 % year‑over‑year growth[1].

**m21.** How many people did Microsoft employ at the end of fiscal 2026?

> Microsoft employed approximately 223,000 full‑time people as of June 30, 2026, the end of fiscal 2026[1]. This total includes about 121,000 employees in the United States and 102,000 employees internationally.

**m22.** How fast did Microsoft's Azure revenue grow in fiscal 2026?

> Microsoft’s Azure and other cloud services revenue grew 41% in fiscal 2026 [1].

**m23.** What was Microsoft Cloud revenue in fiscal 2026?

> Microsoft’s Cloud revenue for fiscal year 2026 was $214.4 billion [1][2].

**m24.** What was Microsoft's effective tax rate for fiscal 2026?

> Microsoft’s effective tax rate for fiscal year 2026 was 19% [1].

**m25.** What was Microsoft's net income in fiscal 2026?

> *Refused (model).*

**m26.** How much did Microsoft pay for Activision Blizzard?

> Microsoft’s acquisition of Activision Blizzard was completed for a total purchase price of $75.4 billion[1][2].

**m27.** How many registered holders of Microsoft common stock were there in 2026?

> Microsoft reported that on July 23, 2026 there were 74,199 registered holders of record of its common stock [1].

**m28.** What cash dividends per share did Microsoft declare in fiscal 2026?

> Microsoft’s Board of Directors declared a cash dividend of $0.91 per share for each of the four quarterly dividends paid in fiscal 2026, including the June 10, 2026 declaration [1][2]. All of the dividend entries for fiscal 2026 list the same per‑share amount of $0.91 [1].

**n21.** How many employees did NVIDIA have at the end of fiscal 2026?

> NVIDIA reported having approximately 42,000 employees at the end of fiscal 2026[1].

**n22.** What was NVIDIA's revenue for fiscal year 2026?

> NVIDIA reported revenue of $215.9 billion for fiscal year 2026[1][2]

**n23.** How much revenue did NVIDIA's Data Center market generate in fiscal 2026?

> NVIDIA’s Data Center segment generated $193,737 million in revenue for fiscal year 2026 (the year ended January 25, 2026)[1].

**n24.** How dependent is NVIDIA on a few large customers?

> NVIDIA’s revenue is heavily concentrated among a small number of customers. In fiscal 2001, its two largest customers together accounted for about 36 % of total revenue, with one alone representing 25 % and another 11 % [1]. More recently, for fiscal 2026 a single direct customer contributed 22 % of total revenue and a second contributed 14 % [2]. The company also notes that several indirect customers each represent 10 % or more of revenue, underscoring its reliance on a limited set of large buyers [3][4].

**n25.** Which foundries produce NVIDIA's semiconductor wafers?

> NVIDIA’s semiconductor wafers are produced by third‑party foundries, specifically Taiwan Semiconductor Manufacturing Company Limited (TSMC) and Samsung Electronics Co., Ltd. [1][2]

**n26.** How many shares did NVIDIA repurchase in fiscal 2026?

> NVIDIA repurchased 282 million shares of its common stock during fiscal 2026 [1][2][3][4].

**n27.** How much did NVIDIA spend on research and development in fiscal 2026?

> NVIDIA reported research and development expenses of $18,497 million for the fiscal year ended January 25, 2026[1]. This represents a 43 % increase over the prior year’s R&D spend. The increase was driven by higher compensation and benefits, including stock‑based compensation, and larger compute and infrastructure costs[1][2].

**n28.** What did the acquisition of Mellanox add to NVIDIA's business?

> NVIDIA’s 2020 acquisition of Mellanox broadened the company’s portfolio by adding networking technology to its offerings, which allowed its platforms to scale to data‑center size and gave rise to a new class of processors called data processing units (DPUs)[1]. This expansion complemented NVIDIA’s existing GPU and AI hardware and software businesses.

**a01.** How many people worked at Apple at the end of fiscal 2000?

> *Refused (model).*

**a02.** What were Apple's total net sales in fiscal 2000?

> Apple reported total net sales of $7.983 billion for fiscal 2000[1][2].

**a03.** How much did Apple spend on research and development in 2000?

> Apple’s research and development expenditures were $380 million for the year 2000[1][2].

**a04.** What happens to Apple if a key component only available from one vendor is delayed?

> If a key component that Apple obtains from a single vendor is delayed, the company may be unable to ship the related products in the quantities or timing it expects, which can hurt its business and financial performance. The delay could also impair Apple’s results of operations and overall financial condition until sufficient supply is secured from the original source or an alternative supplier is found. [1][2]

**a05.** What is the technical foundation of Apple's next operating system?

> Apple’s upcoming operating system, Mac OS X, is built on an open‑source UNIX foundation that combines the Mach 2.5 microkernel with the BSD 4.4 operating system kernel [1][2].

**a06.** What special bonus did Steve Jobs receive for serving as interim CEO?

> Steve Jobs was awarded a special executive bonus for his interim‑CEO service in the form of a Gulfstream V aircraft whose total cost to Apple was about $90 million[1]. The board described the bonus as an aircraft valued at roughly $90 million, with the charge split between the plane itself and associated taxes and costs[2].

**a07.** What was Apple's effective tax rate for 2000?

> Apple’s effective tax rate for the year 2000 was 28%[1][2]

**a08.** Which internet service provider did Apple partner with to offer access to Macintosh users?

> Apple partnered with EarthLink Network Inc., an Internet service provider, to deliver ISP service to Macintosh users in the United States[1][2].

**m01.** How many employees did Microsoft have?

> Microsoft reported that it employed approximately 223,000 full‑time people as of June 30, 2026 [1].

**m02.** How much did Microsoft spend on research and development in 2001?

> Microsoft reported research and development expenses of $4,379 million for the fiscal year ended June 30, 2001 (≈ $4.38 billion) [1]. This figure appears in the company’s consolidated financial statements for that year.

**m03.** What is the status of the US government's antitrust case against Microsoft?

> The antitrust case remains unresolved: after a trial that produced a June 7, 2000 judgment ordering Microsoft’s breakup, the U.S. Court of Appeals for the D.C. Circuit in June 2001 vacated that judgment, affirmed some Section 2 findings, reversed others, and remanded the matter for a new trial on one Section 1 claim and for a new judgment consistent with its ruling[1]. The plaintiffs subsequently said they will no longer seek a breakup and will pursue conduct‑remedy relief, while Microsoft has petitioned the Supreme Court for review of the appellate decision[1]. The Department of Justice and several state attorneys general continue to request information from Microsoft, indicating the investigation is still active[1].

**m04.** Does Microsoft return cash to shareholders through dividends?

> Yes. In fiscal years 2025 and 2026 Microsoft’s Board of Directors declared cash dividends of $24.7 billion and $27.0 billion, respectively, and the company states it will continue returning capital to shareholders in the form of dividends[1]. Earlier filings noted that Microsoft had not paid cash dividends on its common stock at that time, but the more recent 2026 filing confirms dividend payments are now being made[2].

**m05.** How much revenue came from Desktop Applications at Microsoft?

> Microsoft reported Desktop Applications revenue of $9.54 billion for fiscal 2001 [1]. In the prior two years, the segment generated $9.30 billion in 2000 and $7.77 billion in 1999 [1]. These figures represent the revenue earned from products such as Microsoft Office, Project, Visio and related client‑access licenses.

**m06.** When is Windows XP expected to reach customers?

> Windows XP is slated for widespread availability in October 2001, when it is expected to reach customers. [1]

**m07.** How many registered shareholders did Microsoft have?

> Microsoft reported that, as of July 31 2001, it had 112,001 registered holders of record of its common stock[1].

**n01.** Who are NVIDIA's largest customers?

> NVIDIA’s two biggest customers in fiscal 2001 were Edom, which accounted for about 25 % of the company’s revenue, and Celestica, which contributed roughly 11 % of revenue, together representing about 36 % of total sales that year[1][2].

**n02.** Which foundry manufactures NVIDIA's chips?

> NVIDIA’s graphics processors are fabricated by TSMC [1].

**n03.** How much money did Microsoft prepay NVIDIA for the game console chips?

> Microsoft advanced NVIDIA $200 million as a prepayment for graphics chips intended for the Xbox video‑game console [1][2][3][4][5].

**n04.** What did NVIDIA buy from its former graphics rival?

> *Refused (model).*

**n05.** How many engineers did NVIDIA employ in research and development?

> NVIDIA reported that the number of employees engaged in research and development activities rose to **458** as of January 28 2001, up from **214** on January 30 2000[1]. These figures reflect the headcount of staff working on R&D at those dates.

**n06.** What interest rate do NVIDIA's convertible notes pay?

> NVIDIA’s convertible subordinated notes carry a fixed interest rate of 4 ¾ percent per year (4.75% annually) [1][2]. The interest is payable semi‑annually in arrears. This rate applies to the notes issued in October 2000 that mature in October 2007.

**u01.** What was the weather like in Paris last summer?

> *Refused (gate).*

**u02.** What is a good recipe for chocolate cake?

> *Refused (gate).*

**u03.** Who won the football World Cup in 2018?

> *Refused (gate).*

**u04.** How many retail stores does Apple operate?

> *Refused (model).*

**u08.** What was Tesla's revenue last year?

> *Refused (model).*

**u09.** How many Xbox Series X consoles did Microsoft sell in fiscal 2026?

> *Refused (model).*

**u10.** How many daily active users does Microsoft Teams have?

> *Refused (model).*

**u11.** How many apps are available on Apple's App Store?

> *Refused (model).*

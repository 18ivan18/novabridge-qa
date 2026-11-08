# Answer evaluation

Run `2026-11-07-openai-gpt-oss-120b`: model `openai/gpt-oss-120b` (openai_compatible), embedder `BAAI/bge-small-en-v1.5`, top_k 6, min_relevance 0.58, chunk_tokens 400, index of 1028 chunks, commit `a263510`. Raw answers: `eval/answer_runs/2026-11-07-openai-gpt-oss-120b.jsonl`.

**Correct** means the answer states every expected fact of the question. **Evidence cited** means a cited passage from the filing the question names contains its evidence. **Cited only the other filing** counts answers whose sources from that company all come from its other generation of filings. The figure check (task 3) is not available yet.

## Answerable questions

| Questions | Answered | Correct | Evidence cited | Cited only the other filing | Refused: gate / model / no citations | Errors | Not asked |
|---|---|---|---|---|---|---|---|
| HTM filings (24) | 23/24 | 21/24 | 20/24 | 1/24 | 0 / 1 / 0 | 0 | 0 |
| TXT filings (21) | 17/21 | 15/21 | 15/21 | 2/21 | 0 / 4 / 0 | 0 | 0 |

## Unanswerable questions

| Questions | Refused | By the gate | By the model | No valid citations | Answered | Errors | Not asked |
|---|---|---|---|---|---|---|---|
| Off-topic (3) | 3/3 | 3 | 0 | 0 | 0 | 0 | 0 |
| In-domain unanswerable (5) | 5/5 | 0 | 5 | 0 | 0 | 0 | 0 |

## Cost

- LLM calls: 50 (the gate answered 3 without one).
- Latency per question with an LLM call: median 814 ms, 95th percentile 1384 ms.
- Tokens: 138,744 in, 10,162 out.

## Per question

| Question | Set | Outcome | Correct | Evidence cited | Cited filings | Missing facts | ms | Tokens |
|---|---|---|---|---|---|---|---|---|
| a21 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 632 | 2,831 |
| a22 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 822 | 2,925 |
| a23 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 676 | 3,036 |
| a24 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 810 | 2,536 |
| a25 | HTM filings (24) | answered | **no** | **no** | AAPL 2026-09-26 | `297 million`, `85\.8 billion` | 1384 | 3,282 |
| a26 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 828 | 2,608 |
| a27 | HTM filings (24) | answered | yes | yes | AAPL 2000-09-30, AAPL 2026-09-26 | — | 1094 | 2,892 |
| a28 | HTM filings (24) | answered | yes | yes | AAPL 2026-09-26 | — | 1174 | 2,971 |
| m21 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 828 | 2,989 |
| m22 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 607 | 3,025 |
| m23 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 512 | 3,012 |
| m24 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1342 | 2,716 |
| m25 | HTM filings (24) | refused (model) | **no** | **no** | — | `133,749\|133\.7\d* ?billion` | 1917 | 2,925 |
| m26 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 1013 | 3,108 |
| m27 | HTM filings (24) | answered | yes | yes | MSFT 2026-06-30 | — | 769 | 3,130 |
| m28 | HTM filings (24) | answered | yes | **no** | MSFT 2026-06-30 | — | 809 | 2,952 |
| n21 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 555 | 2,758 |
| n22 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 640 | 2,994 |
| n23 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 689 | 3,114 |
| n24 | HTM filings (24) | answered | **no** | **no** | NVDA 2001-01-28 | `22 ?(?:%\|percent)`, `14 ?(?:%\|percent)` | 921 | 3,058 |
| n25 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25, NVDA 2001-01-28 | — | 693 | 3,030 |
| n26 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 1321 | 3,200 |
| n27 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 719 | 3,160 |
| n28 | HTM filings (24) | answered | yes | yes | NVDA 2026-01-25 | — | 920 | 2,868 |
| a01 | TXT filings (21) | refused (model) | **no** | **no** | — | `8,568` | 975 | 3,014 |
| a02 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 610 | 2,981 |
| a03 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 859 | 2,779 |
| a04 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1022 | 3,044 |
| a05 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 928 | 3,043 |
| a06 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 1127 | 3,106 |
| a07 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 921 | 2,838 |
| a08 | TXT filings (21) | answered | yes | yes | AAPL 2000-09-30 | — | 506 | 2,884 |
| m01 | TXT filings (21) | answered | **no** | **no** | MSFT 2026-06-30 | `47,600` | 818 | 2,500 |
| m02 | TXT filings (21) | refused (model) | **no** | **no** | — | `4\.38 billion` | 714 | 3,272 |
| m03 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 1267 | 3,251 |
| m04 | TXT filings (21) | answered | **no** | **no** | MSFT 2026-06-30 | `has not paid cash dividends\|not paid any cash dividends\|no cash dividends\|never paid` | 1318 | 3,047 |
| m05 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 1282 | 3,577 |
| m06 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 749 | 2,919 |
| m07 | TXT filings (21) | answered | yes | yes | MSFT 2001-06-30 | — | 800 | 2,654 |
| n01 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1156 | 3,153 |
| n02 | TXT filings (21) | refused (model) | **no** | **no** | — | `TSMC\|Taiwan Semiconductor` | 650 | 2,838 |
| n03 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 968 | 3,101 |
| n04 | TXT filings (21) | refused (model) | **no** | **no** | — | `3dfx` | 632 | 3,014 |
| n05 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 1511 | 2,950 |
| n06 | TXT filings (21) | answered | yes | yes | NVDA 2001-01-28 | — | 764 | 3,344 |
| u01 | Off-topic (3) | refused (gate) | — | — | — | — | 19 | — |
| u02 | Off-topic (3) | refused (gate) | — | — | — | — | 13 | — |
| u03 | Off-topic (3) | refused (gate) | — | — | — | — | 10 | — |
| u04 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 565 | 2,914 |
| u08 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 512 | 2,973 |
| u09 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 619 | 3,019 |
| u10 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 458 | 2,815 |
| u11 | In-domain unanswerable (5) | refused (model) | — | — | — | — | 757 | 2,756 |

## Answers

**a21.** How many full-time equivalent employees did Apple have at the end of fiscal 2026?

> Apple reported that, as of September 26 2026 (the end of its fiscal 2026 year), it had approximately 167,000 full‑time equivalent employees[1].

**a22.** What were Apple's total net sales in fiscal 2026?

> Apple’s total net sales for fiscal 2026 were $478,834 million [1][2][3].

**a23.** How much revenue did Apple earn from the iPhone in 2026?

> Apple’s iPhone net sales were $254,098 million in fiscal 2026[1][2].

**a24.** What was Apple's effective tax rate in 2026?

> Apple’s effective tax rate for 2026 was 17.0%[1][2]

**a25.** How many of its own shares did Apple buy back in 2026, and for how much?

> Apple repurchased roughly 81.8 million of its own shares in 2026, at an aggregate cost of about $114 billion (the total shown for the three‑month period ending September 26, 2026)[1].

**a26.** Where are Apple's manufacturing partners located?

> Apple’s manufacturing is largely carried out by outsourcing partners based in Asia – chiefly China mainland, India, Japan, South Korea, Taiwan and Vietnam – with additional sourcing from partners and facilities in the United States and single‑source partners in Europe as well as the U.S. [1][2]

**a27.** How many shareholders of record did Apple have?

> Apple reported 24,998 shareholders of record as of December 1, 2000 [1]. More recently, the company reported 21,458 shareholders of record as of October 23, 2026 [2].

**a28.** How much did Apple's net sales in Greater China grow in 2026?

> Apple’s Greater China segment saw net‑sales rise 28% in 2026, increasing from $64,377 million in 2025 to $82,378 million in 2026 – a dollar increase of about $18,001 million[1]. This growth was driven primarily by higher iPhone and Mac sales[1].

**m21.** How many people did Microsoft employ at the end of fiscal 2026?

> Microsoft employed approximately 223,000 people on a full‑time basis as of June 30, 2026, the end of fiscal 2026[1].

**m22.** How fast did Microsoft's Azure revenue grow in fiscal 2026?

> Microsoft’s Azure (combined with other cloud services) revenue grew about 41 percent in fiscal 2026[1][2].

**m23.** What was Microsoft Cloud revenue in fiscal 2026?

> Microsoft Cloud revenue was $214.4 billion in fiscal 2026[1][2].

**m24.** What was Microsoft's effective tax rate for fiscal 2026?

> Microsoft reported an effective tax rate of roughly 19 % for fiscal 2026 [1]. In the detailed tax‑rate reconciliation presented under the new ASU 2023‑09 disclosure, the effective rate is shown as 19.4 % for the year ended June 30, 2026 [2].

**m25.** What was Microsoft's net income in fiscal 2026?

> *Refused (model).*

**m26.** How much did Microsoft pay for Activision Blizzard?

> Microsoft completed its acquisition of Activision Blizzard on October 13, 2023 for a total purchase price of $75.4 billion, paid primarily in cash[1]. This amount is reflected in the purchase‑price allocation disclosed in the filing[2].

**m27.** How many registered holders of Microsoft common stock were there in 2026?

> There were 74,199 registered holders of Microsoft’s common stock on July 23, 2026[1].

**m28.** What cash dividends per share did Microsoft declare in fiscal 2026?

> Microsoft’s Board of Directors declared a cash dividend of $0.91 per share for each of the four quarterly dividends paid in fiscal 2026 [1]. All of the dividend entries for fiscal 2026 list the same per‑share amount of $0.91 [1].

**n21.** How many employees did NVIDIA have at the end of fiscal 2026?

> NVIDIA reported having approximately 42,000 employees at the end of fiscal 2026[1].

**n22.** What was NVIDIA's revenue for fiscal year 2026?

> NVIDIA reported revenue of $215.9 billion for fiscal year 2026[1][2].

**n23.** How much revenue did NVIDIA's Data Center market generate in fiscal 2026?

> NVIDIA’s Data Center market generated $193,737 million in revenue for fiscal year 2026 (ended January 25, 2026)[1]. This figure is presented in the “Revenue by End Market” table of the company’s 10‑K filing.

**n24.** How dependent is NVIDIA on a few large customers?

> NVIDIA’s business is highly concentrated among a limited set of customers.  Its sales are “highly concentrated” and it relies primarily on a small number of add‑in board manufacturers, motherboard makers, CEMs and, indirectly, a few PC OEMs, which together account for a substantial portion of its revenue [1].  Consequently, the company is “dependent on a small number of customers” and could be harmed by the loss of business from any of these key partners [1].

**n25.** Which foundries produce NVIDIA's semiconductor wafers?

> NVIDIA’s semiconductor wafers are fabricated by third‑party foundries, specifically Taiwan Semiconductor Manufacturing Company Limited (TSMC) and Samsung Electronics Co., Ltd. [1][2]

**n26.** How many shares did NVIDIA repurchase in fiscal 2026?

> NVIDIA repurchased 282 million shares of its common stock during fiscal year 2026 [1][2][3][4].

**n27.** How much did NVIDIA spend on research and development in fiscal 2026?

> NVIDIA’s research and development expense for fiscal 2026 was $18,497 million (approximately $18.5 billion)[1]. This amount reflects a 43 % increase over the prior year’s R&D spending.

**n28.** What did the acquisition of Mellanox add to NVIDIA's business?

> NVIDIA’s 2020 purchase of Mellanox broadened its portfolio to include networking technology, allowing its platforms to scale to data‑center size and giving rise to a new class of products called data‑processing units (DPUs) [1]. The acquisition therefore added a networking‑focused capability that complements its GPU‑centric compute offerings.

**a01.** How many people worked at Apple at the end of fiscal 2000?

> *Refused (model).*

**a02.** What were Apple's total net sales in fiscal 2000?

> Apple’s total net sales for fiscal 2000 were $7.983 billion [1][2].

**a03.** How much did Apple spend on research and development in 2000?

> Apple’s research and development expenditures were $380 million for the fiscal year 2000[1][2]. This amount reflects a 21% increase over the prior year.

**a04.** What happens to Apple if a key component only available from one vendor is delayed?

> If a key component that Apple obtains from a single or limited source is delayed or curtailed, the company’s ability to ship the related products in the desired quantities and on schedule can be harmed. Such a supply disruption may also negatively affect Apple’s business and financial performance, as the time needed to obtain sufficient quantities from the original source—or to find an alternative source—could impair its operating results and financial condition. These risks are noted in the company’s discussion of supply‑chain concentration and potential impacts of component delays[1][2].

**a05.** What is the technical foundation of Apple's next operating system?

> Apple’s upcoming client operating system, Mac OS X, is built on an open‑source UNIX foundation, incorporating the Mach microkernel and BSD‑based components as the core of its architecture[1][2]. This foundation supports features such as memory protection, pre‑emptive multitasking, and symmetric multiprocessing.

**a06.** What special bonus did Steve Jobs receive for serving as interim CEO?

> Steve Jobs was awarded a special executive bonus for his interim‑CEO service in the form of an aircraft—a Gulfstream V airplane—valued at roughly $90 million to the Company[1][2].

**a07.** What was Apple's effective tax rate for 2000?

> Apple’s effective tax rate for the fiscal year ended September 30, 2000 was 28 %[1][2]. This rate reflects the difference between the statutory 35 % federal rate and the company’s actual tax provision after accounting for valuation allowance changes and foreign earnings.

**a08.** Which internet service provider did Apple partner with to offer access to Macintosh users?

> Apple partnered with EarthLink Network Inc. (EarthLink) to provide ISP service to Macintosh users in the United States[1].

**m01.** How many employees did Microsoft have?

> Microsoft reported that, as of June 30 2026, it employed approximately 223,000 people on a full‑time basis worldwide[1]. This total includes about 121,000 employees in the United States and 102,000 internationally.

**m02.** How much did Microsoft spend on research and development in 2001?

> *Refused (model).*

**m03.** What is the status of the US government's antitrust case against Microsoft?

> The U.S. Department of Justice and a coalition of eighteen state attorneys general sued Microsoft for Sherman Act violations, and the District Court originally entered a judgment ordering a breakup in June 2000 [1]. That judgment was stayed pending appeal, and on June 28 2001 the D.C. Circuit Court of Appeals vacated the judgment, affirmed some findings, and remanded the case for a new trial on one Section 1 claim and for a new judgment [1]. After the remand, the plaintiffs announced they would no longer seek a breakup, instead pursuing conduct‑remedy relief and not retrying the remaining claim [1]. Microsoft has also petitioned the Supreme Court for review of the appellate decision [1][2].

**m04.** Does Microsoft return cash to shareholders through dividends?

> Yes. Microsoft’s Board of Directors declared cash dividends of $27.0 billion for fiscal 2026 (and $24.7 billion for fiscal 2025) and continues to return capital to shareholders through dividends [1]. In the fourth quarter of fiscal 2026 the company paid a dividend of $0.91 per share, amounting to $6.759 billion [2][3].

**m05.** How much revenue came from Desktop Applications at Microsoft?

> Microsoft’s Desktop Applications segment generated $7.77 billion in fiscal 1999, $9.30 billion in fiscal 2000, and $9.54 billion in fiscal 2001 [1]. The same amounts are reported as $7,590 million, $9,013 million, and $9,580 million for those years in the segment‑level tables [2].

**m06.** When is Windows XP expected to reach customers?

> Windows XP was slated for widespread availability in October 2001, indicating that customers were expected to receive the product at that time[1].

**m07.** How many registered shareholders did Microsoft have?

> Microsoft reported that, as of July 31 2001, there were 112,001 registered holders of record of its common stock[1].

**n01.** Who are NVIDIA's largest customers?

> NVIDIA’s two largest customers in fiscal 2001 were Edom, which accounted for about 25 % of revenue, and Celestica, which contributed roughly 11 % of revenue[1]. Other notable customers at that time included Creative Technology (≈17 % of revenue), Diamond Multimedia (≈15 %) and ASUSteK (≈10 %)[1].

**n02.** Which foundry manufactures NVIDIA's chips?

> *Refused (model).*

**n03.** How much money did Microsoft prepay NVIDIA for the game console chips?

> Microsoft prepaid NVIDIA $200 million as an advance against the graphics chips for the Xbox console [1][2].

**n04.** What did NVIDIA buy from its former graphics rival?

> *Refused (model).*

**n05.** How many engineers did NVIDIA employ in research and development?

> NVIDIA reported that the number of employees engaged in research and development activities rose to **458** as of January 28 2001, up from **214** on January 30 2000[1].

**n06.** What interest rate do NVIDIA's convertible notes pay?

> NVIDIA’s convertible subordinated notes carry interest at a rate of 4 ¾ percent per year (approximately 4.75% annual). This rate is applied to the notes issued in October 2000 and is payable semi‑annually. [1][2]

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

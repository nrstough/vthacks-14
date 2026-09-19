# Dataset sources for Overdraft Guard

Research date: September 19, 2026. Scope: consumer transaction histories for forecasting the next 14 days of ordinary spending from at least 56 days of prior observations. This is source research, not a completed dataset audit. No transaction archives were downloaded, accounts created, access terms accepted, or new training started.

## Recommendation

**Inspect the Nedbank dataset on Zindi first.** Its combination of real histories, many customers, and an explicit data license makes it the strongest newly identified candidate. Use MoneyData as a small independent real-history case study. Keep IBM TabFormer as the synthetic fallback and controlled development source.

This improves on the previous plan, which identified only the older CTU dataset as a public real-data candidate. None is yet validated for our residual-spending target. Published record counts below are source claims, not our own counts from the files.

| Priority | Source | Role in our project | Main constraint |
|---|---|---|---|
| 1 | Nedbank / Zindi | Main real-history training and evaluation candidate | Account access; inspect actual schema and coverage first |
| 2 | MoneyData / MoneyVis | Independent real-history case study | One customer cannot establish population accuracy |
| 3 | IBM TabFormer | Larger synthetic experiments and fallback | Card purchases are not a complete checking ledger |
| 4 | CTU Financial / Berka | Historical external benchmark | Old domain and unresolved data-license details |
| Later | Consenting users' bank exports or bank-link integration | Direct validation in the intended population | Permission, adequate history, and representativeness |

## 1. Nedbank: best first candidate

The [Zindi data page](https://zindi.world/competitions/june-study-jam-series-transaction-volume-forecasting-challenge/data) lists 11,944 customers, up to 34 months from December 2012 through October 2015, and 18 million real transaction records. `transactions_features.zip` is listed as 280.8 MB; it includes amount, type, balance, and debit/credit indicators, joined by `UniqueID`. Negative amounts represent debits.

Acquire `VariableDefinitions.csv` (3.6 KB), `README.txt`, and the transaction archive first. Demographic and monthly-financial tables are optional for our initial forecast. The public page shows sign-in and acceptance controls; authenticated download was not tested.

The original target is future three-month **transaction count**, not spending. We need to create our own daily outflow labels from the historical transactions. Its supplied Train/Test division and target are not our evaluation protocol.

The [challenge's rules](https://zindi.world/competitions/june-study-jam-series-transaction-volume-forecasting-challenge) explicitly list **CC BY-SA 4.0**. [Zindi's general rules](https://zindi.world/rules), section 3.7.1, allow reuse of open challenge data for research, education, and commercial or noncommercial purposes under that license. Retain the attribution and license alongside derived datasets. We are sourcing data, not entering this separate competition or seeking its prizes.

Before training, inspect date precision, currency/units, whether `UniqueID` aggregates several accounts, reversals, missing periods, and usable merchant/category fields. A customer-level spending series may be valid while a customer-level balance is not: balances from separate accounts cannot be treated as one continuous ledger. The initial feature set should not require demographic attributes.

**Decision:** strongest acquisition candidate, conditional on file inspection. A South African history from this period is useful real evidence, but does not by itself establish current US student performance.

## 2. MoneyData: useful real-world case study

The author's [Mendeley dataset](https://data.mendeley.com/datasets/dnxtg6n4rv/1), DOI `10.17632/dnxtg6n4rv.1`, was published January 14, 2026 and lists **CC BY 4.0**. It describes more than 6,500 transactions across seven years starting July 2015, including dates, descriptions, transaction types, debit/credit amounts, and remaining balance. This is an explicit dataset license, rather than an inference from the paper's license.

The [MoneyVis paper](https://people.cs.nott.ac.uk/blaramee/research/financeVis/firat23moneyVis.pdf) explains that this is one anonymized retail customer's history. It also documents a material timing artifact: weekend transactions appear on the following Monday, and intraday timestamps are absent. A [public author-linked sheet](https://docs.google.com/spreadsheets/d/1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0/edit?gid=2010330240) provides another access route.

The sheet was accessible for viewing. Mendeley's indexed primary record supplied the license and download listing, but direct page retrieval timed out; its file download still needs testing.

**Decision:** valuable for end-to-end extraction and a chronological case study. Choose a clearly defined target—posted outflows or purchase activity—and respect the difference. Evaluate a frozen model on it, or reserve a later period if adapting to this customer. Thousands of overlapping windows from one person remain one person's evidence.

## 3. IBM TabFormer: strongest synthetic fallback

[IBM's repository](https://github.com/IBM/TabFormer) provides roughly 24 million simulated card transactions. The [author's dataset listing](https://www.kaggle.com/datasets/ealtman2019/credit-card-transactions) describes 2,000 simulated consumers, multiple cards, decades of purchases, and an **Apache 2.0** license in the dataset description. It is explicitly a virtual-world simulation, not anonymized real consumers.

Get `transactions.tgz` through [IBM's data directory](https://github.com/IBM/TabFormer/tree/main/data/credit_card) or the linked [IBM Box fallback](https://ibm.box.com/v/tabformer-data). Git LFS is used; downloading the raw pointer file alone does not retrieve the archive. The pointer lists 278,576,638 bytes, about 266 MiB compressed; successful full download was not tested.

The [official loader](https://github.com/IBM/TabFormer/blob/main/dataset/card.py) references user/card IDs, calendar date/time, amount, merchant fields, MCC, error and fraud fields. Its fraud-model preprocessing clips/logs and quantizes amounts. **Parse the raw CSV ourselves** so forecast targets retain their actual amounts and dates.

Aggregate cards by consumer where the intended target is person-level card spending. Do not treat credit-card purchases as immediate checking withdrawals or invent a real paycheck/starting-balance history. A combined Nessie demo may add synthetic bills and payroll, but that additional layer must stay labeled synthetic.

**Decision:** useful for scalable neural experiments and testing transfer from a different simulator. It cannot replace real-data evaluation.

## 4. CTU Financial / Berka: historical benchmark

The [CTU repository](https://relational.fel.cvut.cz/dataset/Financial) provides the PKDD'99 Financial database through public MariaDB access and documents eight tables totaling 1,090,086 rows. That is not the number of customers. The original benchmark targets loan outcomes; its transaction history is the part relevant to us. The site explicitly warns about temporal leakage in derived financial features.

Follow the site's database-export instructions and inspect the transaction and account tables. The documented direct service is `relational.fel.cvut.cz:3306`, database `financial`; guest credentials are published on that page. This session did not test the connection or export.

**Decision:** a secondary historical test after checking the original provenance and data terms. The primary page reviewed does not clearly establish a modern dataset license; do not inherit a license from an unrelated GitHub mirror. Older Czech banking activity is a different domain from modern US discretionary purchases.

The [original dictionary](https://web.archive.org/web/20180506035658/http://lisp.vse.cz/pkdd99/Challenge/berka.htm) lists 4,500 accounts and 1,056,320 transaction records, with account ID, date, amount, direction, operation, and balance. Account holders and authorized users can link multiple accounts: keep those relationships together when creating holdouts.

## Longer-term: authorized histories from the intended users

An export from a consenting user can test the actual bank format and spending behavior without building a new bank-link integration. Aim for months of continuous records, not a handful of transactions. It can validate that person's experience, not everyone else's.

[Plaid's Transactions documentation](https://plaid.com/docs/transactions/) describes an initial default of 90 days and a requested maximum of 730, subject to what the institution supplies. This is a mechanism for retrieving an authorized user's history, not a public training corpus. Use of a connection does not automatically authorize pooling histories for model training. No personal export or bank-linked data was accessed for this research.

## Sources that look relevant but do not solve this task

| Source | Why it is not our main forecasting dataset |
|---|---|
| [BLS Consumer Expenditure diaries](https://www.bls.gov/cex/pumd-getting-started-guide.htm) | Real household spending, but each household's diary covers only two weeks; exact purchase dates are not released. Useful population statistics, insufficient for 56 prior days plus 14 future days for the same household. |
| [Transaction Categorization on Hugging Face](https://huggingface.co/datasets/mitulshah/transaction-categorization) | 4.5M+ descriptions with category/country/currency. The published schema lacks dates, amounts, and person IDs. Potential categorizer data; no longitudinal forecast labels. It also has an access gate. |
| [IBM AML-Data](https://github.com/IBM/AML-Data) | Synthetic money-laundering data with a different modeling purpose. Its data license is CDLA-Sharing-1.0 even though the code repository is Apache 2.0. Do not confuse it with TabFormer. |
| [ComputingVictor / often called CaixaBank transactions](https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets) | The current original dataset description/license could not be retrieved reliably. Its name is not proof of real bank-customer provenance. Prefer the original IBM release's clearer source trail. |
| [FreeFinancialTransactions50M](https://huggingface.co/datasets/ziadatalabs/FreeFinancialTransactions50M) | Fully synthetic, roughly 1.59 GB, CC BY-NC 4.0. Many rows and a balance column do not demonstrate learnable personal spending patterns. Generator realism and account-level temporal consistency were not independently audited. Lower priority than the documented sources above. |
| Nessie or another banking sandbox | Useful API integration data. Does not establish representative real transaction histories or a ready-made supervised forecast task. |

Avoid treating a popular fraud-detection file, question-answer corpus, or merchant-description classifier dataset as spending history. A model needs repeated observations of the same underlying person/account over time.

## Acquisition and evaluation plan

1. **Nedbank first:** retrieve the small dictionary and README; confirm the target can be derived before downloading and processing the archive. If access delays the work, use MoneyData for a small real-data pipeline check and IBM for broader synthetic development.
2. Preserve each source independently with its version, download URL, date, file hash, license/attribution, currency, time convention, and real/synthetic status. Do not concatenate raw amounts from different currencies or domains.
3. Start with a fixed selection of a few hundred customers, keeping whole histories. Count eligible customers with at least 70 consecutive days of trustworthy coverage; use longer history when possible. Do not randomly sample transaction rows, which destroys daily totals.
4. Normalize signs, dates, duplicates, corrections, account relationships, and transfers. Test balance reconciliation when a genuine account ledger exists. Distinguish missing coverage from observed zero-spend days. Keep refunds and card settlements from creating double counting.
5. Freeze held-out customers and future date periods before model selection. Fit recurrence detection and normalization only using history available at each forecast origin. Reserve a final untouched test set. Cover all forecast start weekdays—the first pilot did not.
6. Define the residual target precisely. Removing known recurring bills is part of the pipeline and needs its own validation; subtracting a globally detected future bill pattern can leak information. Do not use a future balance as an input feature.
7. Compare the neural model with the weekday average, recent average, and a regularized linear baseline. Measure daily error, 7-/14-day total error, underprediction, and eventually actual downstream plan failures. Resample whole customers when estimating uncertainty.

For a small network, download/cleaning/evaluation will likely dominate training time. No claim about the runtime or accuracy of these datasets is justified until the first actual sample is audited. The previous synthetic pilot and its test results remain unchanged.

The next concrete action is **acquire and audit the Nedbank dictionary and histories**, then decide whether they support residual spending, total posted outflow, or a narrower target. Our recommendation to use the dataset is an engineering judgment based on its published documentation; it is not a finding that it has already passed those checks.

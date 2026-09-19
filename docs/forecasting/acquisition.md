# Public-source acquisition and integrity

Acquired September 19, 2026 in the isolated forecasting worktree. No login, account creation, click-through terms acceptance, or private bank export was used. The raw sources are retained unchanged under `forecasting/data/raw/`; checksums, source URLs, attribution and observed schema evidence are committed in [`source-manifest.json`](source-manifest.json). The acquisition manifest is evidence of identity and provenance, not a claim that a dataset is appropriate for production forecasting.

## Acquired sources

| Source | Actual asset | Bytes | Provenance and license | Intended role |
|---|---|---:|---|---|
| IBM TabFormer | `ibm-transactions.tgz` | 278,576,638 | Synthetic credit-card consumers; Apache-2.0 | Multi-consumer synthetic benchmark |
| MoneyData, author-linked sheet | `moneydata-author-sheet.csv` | 466,479 | One real anonymized bank customer; CC BY 4.0 dataset | Separate chronological case study |
| MoneyData, Mendeley V1 | `laramee26openBankTransactionData.xlsx` | 507,389 | Same underlying anonymized records; CC BY 4.0 | Retained for provenance comparison; excluded from modeling due to date discrepancy |

IBM source revision: `ebb7cd68ee1897599568107740bc452104bbbaf8`. Its [official repository](https://github.com/IBM/TabFormer) identifies the data as simulated and publishes the LFS pointer and repository license. The actual gzip came from GitHub's media endpoint at that exact commit. The archive's SHA-256 matches the official LFS object:

```text
e9f589a0958f40d60f81b1a2e8428db86e00c05755caf44fb055827976c0efa2
```

Measured IBM download time was 245.9 seconds. The first archive member is `card_transaction.v1.csv` (2,354,626,737 uncompressed bytes); the source was sampled and later processing can stream it without extracting the full CSV. Attribution: IBM; Padhi et al., *Tabular Transformers for Modeling Multivariate Time Series*, ICASSP 2021.

MoneyData's [Mendeley record](https://data.mendeley.com/datasets/dnxtg6n4rv/1) is DOI `10.17632/dnxtg6n4rv.1`, published January 14, 2026 by Robert Laramee, explicitly licensed CC BY 4.0. The retained HTML and parsed metadata establish the dataset license. Its public file listing is accessible without login at `/public-api/datasets/dnxtg6n4rv/files?folder_id=root&version=1`. The workbook hash matches the listing's published checksum:

```text
716eaf9ad4a3cf60dc9c9c8a20ed9a917c545a1b5f139f40ed91d2104faa3ff7
```

The [author-linked Google Sheet](https://docs.google.com/spreadsheets/d/1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0/edit?gid=2010330240) was exported as untouched CSV. The sheet is mutable, so this work freezes the downloaded snapshot and rejects a new download that differs from this hash:

```text
8e9fba7059145342afa7f765165068e699fd75fe1468a9b299e59e58aa2b3c72
```

MoneyData attribution: Robert Laramee, *Bank Transactions Dataset*, Mendeley Data V1, DOI `10.17632/dnxtg6n4rv.1`; Firat et al., *MoneyVis: Open Bank Transaction Data for Visualization and Beyond*, EuroVis 2023, DOI `10.2312/evs.20231052`. The [paper](https://people.cs.nott.ac.uk/blaramee/research/financeVis/firat23moneyVis.pdf) links the public data and explains the single-customer provenance and posting-date limitations. If derived data is shared, retain attribution, the [CC BY 4.0 link](https://creativecommons.org/licenses/by/4.0/), and a statement describing transformations. No endorsement is implied.

## Source discrepancy: use the author sheet's dates

Both MoneyData sources contain 6,567 nonempty transaction records. Comparing every record in original order found that all nondate fields match, with numeric debit/credit/balance rounded to their displayed cents to account for Excel floating-point serialization.

The workbook contains 2,816 numeric Excel date cells and other dates stored as text. After converting the numeric dates using Excel's 1900 epoch, **2,621 date values disagree with the author sheet; every disagreement is an exact day/month swap**. For example, the sheet's July 12, 2022 becomes December 7, 2022 in the workbook. Those dates conflict with the sheet's posting chronology and the paper's weekday-only posting description.

We preserve both originals, exclude the workbook from the benchmark, and use the CSV snapshot's explicit `dd/mm/yyyy` dates. This is a source-selection decision, not a silent repair of a published raw file. Reproduce the comparison with `python -m forecasting.acquire compare_moneydata`. It produces `moneydata-version-comparison.json` containing aggregate evidence, without printing individual transaction descriptions.

## Observed schema and sample evidence

### IBM

The actual CSV has 15 columns (the repository's general description says 12):

```text
User, Card, Year, Month, Day, Time, Amount, Use Chip, Merchant Name,
Merchant City, Merchant State, Zip, MCC, Errors?, Is Fraud?
```

`User` is the person-group key; `Card` is local to that user. Calendar components are separate integers, `Time` is an `HH:MM` string, and amounts carry `$` with signed decimal values. This is synthetic card activity, not a complete checking-account ledger, paycheck history, or record of immediate checking withdrawals. Currency is represented by the source's dollar-denominated simulation; do not mix it with MoneyData's monetary units or assume conversion.

The first 100,000 rows cover only six users and 21 user/card pairs because rows are grouped. In this initial sample, 2,581 amounts are negative, 1,707 rows have nonempty `Errors?`, and 126 rows are marked fraud. Sample findings are not whole-corpus proportions. Error text includes failed-attempt conditions such as insufficient balance and bad PIN. The preprocessing audit must record the actual corpus counts and exclusions and must not count failed attempts as successful spending. Retain the refund/fraud distinction and disclose the resulting gross-spending target.

### MoneyData

The author CSV has these columns:

```text
Transaction Number, Transaction Date, Transaction Type,
Transaction Description, Debit Amount, Credit Amount, Balance,
Category, Location City, Location Country
```

The actual 6,567 records span July 27, 2015 to July 25, 2022. Transaction numbers and whole rows have no duplicates. There are 6,122 debit rows and 445 credit rows, no row has both, and no negative debit/credit values were observed. Debit/credit blanks denote the other side of the transaction; do not automatically treat arbitrary missing measurements as zero. Transaction type is missing for 61 rows; category for 24, city for 672 and country for 686. These attributes are not necessary for the planned total-posted-outflow target.

All recorded dates are weekdays: Monday 2,162, Tuesday 1,307, Wednesday 1,039, Thursday 952 and Friday 1,107. The author paper says weekend activity is posted the following Monday and intraday timestamps are absent. Weekend zeros in this benchmark therefore concern **posted outflow**, not absence of purchase activity. The dataset supplies no independent coverage flags; treating internal date gaps as observed zero activity requires a stated continuous-ledger assumption, and periods beyond the source endpoints are unavailable.

Account-identifying columns have been removed; the paper establishes the single-customer provenance. The numerical fields do not explicitly identify currency. UK-bank provenance and non-GBP fee descriptions strongly suggest GBP, but that is an inference, not a verified currency field. Report source monetary units or disclose the GBP assumption; never relabel the values as USD. The target includes bills, transfers and other debits unless a separately validated exclusion process is applied. It is not already residual everyday spending.

## Reproduction and retention

From the worktree root, all acquisition and integrity checks use Python's standard library:

```sh
python3 -m forecasting.acquire ibm
python3 -m forecasting.acquire moneydata
python3 -m forecasting.acquire moneydata_mendeley
python3 -m forecasting.acquire metadata
python3 -m forecasting.acquire compare_moneydata
python3 -m unittest forecasting.tests.test_acquire -v
```

Use `--raw-dir /absolute/local/path` to choose another download directory. The module uses HTTPS, bounds download sizes, retains `.part` files on failure, and only promotes a download after size/hash verification. A successful Range response must confirm the exact resume offset; a server ignoring Range restarts the file. Mutable snapshots without a known checksum restart instead of combining versions. IBM and the frozen MoneyData assets have checksums baked into the acquisition configuration; the author sheet changing is an explicit reproducibility failure, not permission to substitute new rows. Existing files are checked before reuse and their original acquisition metadata is retained.

Twelve acquisition tests pass, covering checksum mismatch, retained-file corruption, partial recovery, range acceptance/rejection, servers ignoring Range, size limits, truncated bodies, mutable snapshots, manifest locking and HTTPS enforcement. Full data suitability and chronology tests belong to preprocessing and evaluation; these download tests do not establish training validity.

Raw files, source license texts, the original IBM README, Mendeley metadata and inspection reports remain in `forecasting/data/raw/`, which is ignored by git. The committed source manifest preserves exact hashes. Do not clean this directory until a verified artifact archive exists. A future machine must redownload the same hashes or obtain the retained artifact archive. The frozen author-sheet snapshot may no longer be retrievable at its mutable URL if the publisher changes it.

Nedbank access and the decision to use fallback data are recorded by the parent forecasting workstream. Neither synthetic multi-consumer evidence nor this single real person's history establishes population validation or production promotion.

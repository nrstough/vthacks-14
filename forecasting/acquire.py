"""Acquire untouched, licensed public forecast sources using only the stdlib.

Run ``python -m forecasting.acquire ibm`` or ``python -m forecasting.acquire
moneydata``. Existing verified files are retained; interrupted downloads are
resumed only when the server confirms the requested byte offset. No extraction,
login, cookie store, preprocessing, or terms acceptance occurs here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

IBM_REVISION = "ebb7cd68ee1897599568107740bc452104bbbaf8"
IBM_SHA256 = "e9f589a0958f40d60f81b1a2e8428db86e00c05755caf44fb055827976c0efa2"
IBM_BYTES = 278_576_638
SHEET_ID = "1pYTMqRhEI48hv_zNWZriHW_0vRSrA9ZSQ31aLT4Vbk0"
SOURCES = {
    "ibm": {
        "filename": "ibm-transactions.tgz",
        "url": f"https://media.githubusercontent.com/media/IBM/TabFormer/{IBM_REVISION}/data/credit_card/transactions.tgz",
        "sha256": IBM_SHA256,
        "bytes": IBM_BYTES,
        "max_bytes": IBM_BYTES,
        "source_page": "https://github.com/IBM/TabFormer",
        "version": IBM_REVISION,
        "provenance": "synthetic; simulated credit-card consumers, not real people",
        "license": "Apache-2.0",
        "license_url": f"https://raw.githubusercontent.com/IBM/TabFormer/{IBM_REVISION}/LICENSE",
        "attribution": "IBM; Padhi et al., Tabular Transformers for Modeling Multivariate Time Series, ICASSP 2021",
    },
    "moneydata": {
        "filename": "moneydata-author-sheet.csv",
        "url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=2010330240",
        "sha256": "8e9fba7059145342afa7f765165068e699fd75fe1468a9b299e59e58aa2b3c72",
        "bytes": 466479,
        "max_bytes": 10_000_000,
        "source_page": "https://data.mendeley.com/datasets/dnxtg6n4rv/1",
        "version": "author-linked Google Sheet snapshot; related Mendeley record DOI 10.17632/dnxtg6n4rv.1",
        "provenance": "real anonymized retail bank transactions from one customer; author-linked sheet snapshot",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Robert Laramee, Bank Transactions Dataset, Mendeley Data V1, DOI 10.17632/dnxtg6n4rv.1; Firat et al., MoneyVis, EuroVis 2023, DOI 10.2312/evs.20231052",
    },
    "moneydata_mendeley": {
        "filename": "laramee26openBankTransactionData.xlsx",
        "url": "https://data.mendeley.com/public-files/datasets/dnxtg6n4rv/files/36b3d359-2491-4282-850f-3f03e00fbfe3/file_downloaded",
        "sha256": "716eaf9ad4a3cf60dc9c9c8a20ed9a917c545a1b5f139f40ed91d2104faa3ff7",
        "bytes": 507389,
        "max_bytes": 507389,
        "source_page": "https://data.mendeley.com/datasets/dnxtg6n4rv/1",
        "version": "10.17632/dnxtg6n4rv.1; published 2026-01-14",
        "provenance": "real anonymized retail bank transactions from one customer; Mendeley V1 workbook",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Robert Laramee, Bank Transactions Dataset, Mendeley Data V1, DOI 10.17632/dnxtg6n4rv.1; Firat et al., MoneyVis, EuroVis 2023, DOI 10.2312/evs.20231052",
    },
}

METADATA_SOURCES = {
    "ibm-LICENSE.txt": f"https://raw.githubusercontent.com/IBM/TabFormer/{IBM_REVISION}/LICENSE",
    "ibm-README.md": f"https://raw.githubusercontent.com/IBM/TabFormer/{IBM_REVISION}/README.md",
    "ibm-repository.json": f"https://api.github.com/repos/IBM/TabFormer/commits/{IBM_REVISION}",
    "mendeley-record.html": "https://data.mendeley.com/datasets/dnxtg6n4rv/1",
    "mendeley-file-list.json": "https://data.mendeley.com/public-api/datasets/dnxtg6n4rv/files?folder_id=root&version=1",
    "moneydata-CC-BY-4.0.txt": "https://creativecommons.org/licenses/by/4.0/legalcode.txt",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected_sha256: str | None, expected_size: int | None) -> dict:
    size = path.stat().st_size
    if expected_size is not None and size != expected_size:
        raise ValueError(f"Size mismatch for {path}: {size} != {expected_size}")
    digest = sha256_file(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {path}")
    return {"bytes": size, "sha256": digest}


def download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
    max_bytes: int = 300_000_000,
    timeout: float = 45,
) -> dict:
    """Bounded resumable GET; only publish a complete, verified destination.

    For immutable public files the caller supplies the source checksum. For a
    mutable snapshot, callers persist the first returned checksum in a manifest
    and supply it on later runs. A server ignoring Range causes a full restart,
    never concatenation. On any exception the .part is retained for inspection.
    """
    if not url.startswith("https://"):
        raise ValueError("Public source downloads must use HTTPS")
    destination = Path(destination)
    if destination.exists():
        existing = verify(destination, expected_sha256, expected_size)
        if existing["bytes"] > max_bytes:
            raise ValueError("Existing file exceeds the configured size limit")
        return {**existing, "status": "retained", "url": url}
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > max_bytes:
        raise ValueError("Partial download exceeds the configured size limit")
    # A mutable snapshot without a known digest might have changed between GETs.
    # Restart it rather than combining byte ranges from different versions.
    if expected_sha256 is None:
        offset = 0
    if expected_size is not None and offset == expected_size:
        result = verify(partial, expected_sha256, expected_size)
        partial.replace(destination)
        return {**result, "status": "recovered_verified_partial", "url": url}
    headers = {"User-Agent": "OverdraftGuardForecastResearch/1.0", "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    started = time.perf_counter()
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:
        status = response.status
        if status == 206:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", ""))
            if not match or int(match.group(1)) != offset:
                raise ValueError("Server did not confirm the requested resume offset")
            if int(match.group(2)) < offset:
                raise ValueError("Invalid byte range")
            total = None if match.group(3) == "*" else int(match.group(3))
        elif status == 200:
            offset = 0
            total = response.headers.get("Content-Length")
            total = int(total) if total is not None else None
        else:
            raise ValueError(f"Unexpected HTTP status {status}")
        if total is not None and total > max_bytes:
            raise ValueError("Download exceeds the configured size limit")
        count = offset
        with partial.open("ab" if offset else "wb") as stream:
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > max_bytes:
                    raise ValueError("Download exceeded the configured size limit")
                stream.write(chunk)
        if total is not None and count != total:
            raise ValueError(f"Incomplete download: received {count} of {total} bytes")
        details = {
            "resolved_url": response.url,
            "content_type": response.headers.get("Content-Type"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "resumed_from": offset,
        }
    result = verify(partial, expected_sha256, expected_size)
    partial.replace(destination)
    return {**result, **details, "url": url, "status": "downloaded", "elapsed_seconds": time.perf_counter() - started}


def acquire(source: str, raw_dir: Path) -> dict:
    spec = SOURCES[source]
    raw_dir = Path(raw_dir)
    destination = raw_dir / spec["filename"]
    manifest_path = raw_dir / f"{source}-source.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    locked_hash = previous["download"]["sha256"] if previous else spec["sha256"]
    locked_size = previous["download"]["bytes"] if previous else spec["bytes"]
    result = download(spec["url"], destination, expected_sha256=locked_hash, expected_size=locked_size, max_bytes=spec["max_bytes"])
    if previous and result["status"] == "retained":
        return previous
    manifest = {
        "schema_version": 1,
        "source": source,
        "acquired_utc": datetime.now(timezone.utc).isoformat(),
        "source_description": dict(spec),
        "raw_relative_path": destination.name,
        "modifications": "none; raw response retained untouched",
        "download": result,
        "scope_limit": "Acquisition verifies identity/integrity only, not model suitability or complete observation coverage.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def compare_moneydata_sources(raw_dir: Path) -> dict:
    """Reproduce the observed date-format discrepancy without repairing raw data."""
    for source in ("moneydata", "moneydata_mendeley"):
        spec = SOURCES[source]
        verify(raw_dir / spec["filename"], spec["sha256"], spec["bytes"])
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    records = []
    with ZipFile(raw_dir / SOURCES["moneydata_mendeley"]["filename"]) as archive:
        strings = ["".join(s.itertext()) for s in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        for row in sheet.findall(".//x:sheetData/x:row", ns)[1:]:
            cells = {}
            for cell in row:
                value_element = cell.find("x:v", ns)
                value = value_element.text if value_element is not None else ""
                if cell.get("t") == "s":
                    value = strings[int(value)]
                cells[re.sub(r"\d+", "", cell.attrib["r"])] = value
            if cells.get("A", "").strip():
                records.append([cells.get(column, "") for column in "ABCDEFGHIJ"])
    with (raw_dir / SOURCES["moneydata"]["filename"]).open(newline="", encoding="utf-8-sig") as stream:
        sheet_rows = list(csv.reader(stream))[1:]
    report = {
        "mendeley_nonempty_record_count": len(records),
        "sheet_record_count": len(sheet_rows),
        "matching_normalized_records": 0,
        "different_field_counts": {},
        "exact_day_month_swap_count": 0,
        "workbook_excel_serial_date_count": 0,
        "normalization": "Workbook dates: text dd/mm/yyyy or Excel1900-system serial; amounts/balance: Decimal quantization to .01 to remove binary float serialization; other cells exact match. No raw file changes.",
        "currency": "Not explicitly encoded; GBP strongly indicated by UK-bank provenance and NON-GBP fee labels, but not independently verified.",
        "decision": "Use the author-linked CSV snapshot; preserve but exclude the workbook from forecasting because of inconsistent dates.",
    }
    for workbook_row, sheet_row in zip(records, sheet_rows):
        differences = []
        for index, (left, right) in enumerate(zip(workbook_row, sheet_row)):
            if index == 1:
                is_serial = "/" not in left
                report["workbook_excel_serial_date_count"] += int(is_serial)
                workbook_date = datetime(1899, 12, 30) + timedelta(days=float(left)) if is_serial else datetime.strptime(left, "%d/%m/%Y")
                sheet_date = datetime.strptime(right, "%d/%m/%Y")
                same = workbook_date == sheet_date
                if not same and (workbook_date.year, workbook_date.month, workbook_date.day) == (sheet_date.year, sheet_date.day, sheet_date.month):
                    report["exact_day_month_swap_count"] += 1
            elif index in (4, 5, 6) and left and right:
                same = Decimal(left).quantize(Decimal(".01")) == Decimal(right).quantize(Decimal(".01"))
            else:
                same = left == right
            if not same:
                differences.append(index)
                key = str(index)
                report["different_field_counts"][key] = report["different_field_counts"].get(key, 0) + 1
        if not differences:
            report["matching_normalized_records"] += 1
    (raw_dir / "moneydata-version-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(SOURCES) + ["metadata", "compare_moneydata"])
    parser.add_argument("--raw-dir", type=Path, default=Path(__file__).parent / "data" / "raw")
    args = parser.parse_args()
    if args.source == "metadata":
        result = {name: download(url, args.raw_dir / name, max_bytes=5_000_000) for name, url in METADATA_SOURCES.items()}
        args.raw_dir.mkdir(parents=True, exist_ok=True)
        (args.raw_dir / "metadata-source.json").write_text(json.dumps(result, indent=2) + "\n")
    elif args.source == "compare_moneydata":
        result = compare_moneydata_sources(args.raw_dir)
    else:
        result = acquire(args.source, args.raw_dir)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Fetch public data, keep source bytes and record provenance."""

import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import INDICATORS, OECD_URL, RAW


def fetch(item):
    filename, url = item
    session = requests.Session()
    session.headers.update({"User-Agent": "HealthValueAtlas/1.0 public research"})
    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504]
            )
        ),
    )
    response = session.get(url, timeout=120)
    response.raise_for_status()
    payload = response.content
    if filename.endswith(".json.gz"):
        data = response.json()
        if (
            not isinstance(data, list)
            or len(data) != 2
            or not isinstance(data[1], list)
        ):
            raise ValueError(f"Unexpected World Bank response: {filename}")
        if data[0]["pages"] != 1:
            raise ValueError(f"Pagination required: {filename}")
    stored = gzip.compress(payload, mtime=0) if filename.endswith(".gz") else payload
    (RAW / filename).write_bytes(stored)
    print(f"Saved {filename}: {len(payload):,} source bytes", flush=True)
    return {
        "file": filename,
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(stored).hexdigest(),
        "source_bytes": len(payload),
        "source_last_updated": data[0].get("lastupdated")
        if filename.endswith(".json.gz")
        else response.headers.get("Last-Modified"),
    }


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    tasks = [
        ("oecd_mortality.csv.gz", OECD_URL),
        (
            "countries.json.gz",
            "https://api.worldbank.org/v2/country?format=json&per_page=400",
        ),
    ]
    tasks += [
        (
            f"{code}.json.gz",
            f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&date=2009:2023&per_page=10000&source=2",
        )
        for code in INDICATORS
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        manifest = list(pool.map(fetch, tasks))
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

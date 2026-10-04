"""Read-only API and local dashboard. Run with python -m healthvalue serve."""

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .config import WEB

app = FastAPI(
    title="HealthValue Atlas",
    version="1.0.0",
    description="Country-level health economics, associations and temporal forecasting",
)


@lru_cache(maxsize=1)
def dataset():
    return json.loads((WEB / "data" / "atlas.json").read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok", "countries": dataset()["quality"]["countries"]}


@app.get("/api/countries")
def countries():
    return sorted(
        {
            r["iso3"]: {"iso3": r["iso3"], "country": r["country"]}
            for r in dataset()["panel"]
        }.values(),
        key=lambda r: r["country"],
    )


@app.get("/api/panel")
def panel(
    year: int | None = Query(default=None, ge=2010, le=2023),
    iso3: str | None = Query(default=None, min_length=3, max_length=3),
):
    rows = dataset()["panel"]
    if iso3 is not None:
        iso3 = iso3.upper()
        if iso3 not in {r["iso3"] for r in rows}:
            raise HTTPException(404, "Country is not in this research sample")
        rows = [r for r in rows if r["iso3"] == iso3]
    return [r for r in rows if year is None or r["year"] == year]


@app.get("/api/models")
def models():
    return {
        "associations": dataset()["associations"],
        "forecast": dataset()["forecast"],
    }


@app.get("/api/scenario")
def scenario(change_pct: float = Query(default=10, ge=-20, le=20)):
    main = dataset()["associations"]["main"]
    ratio = 1 + change_pct / 100
    low, high = sorted([100 * (ratio ** main[k] - 1) for k in ["ci_low", "ci_high"]])
    return {
        "spend_change_pct": change_pct,
        "mortality_change_pct": 100 * (ratio ** main["coefficient"] - 1),
        "ci95_low": low,
        "ci95_high": high,
        "causal": False,
        "interval_type": "Coefficient confidence interval, not a prediction interval",
    }


app.mount("/", StaticFiles(directory=WEB, html=True), name="dashboard")

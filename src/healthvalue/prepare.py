"""Build a country-year panel. Never interpolate outcomes or bridge year gaps."""

import gzip
import hashlib
import json
import sqlite3

import numpy as np
import pandas as pd

from .config import END_YEAR, INDICATORS, PROCESSED, RAW, REPORTS, ROOT, START_YEAR


def read_json(name):
    with gzip.open(RAW / name, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def verify_snapshot():
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest:
        actual = hashlib.sha256((RAW / entry["file"]).read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"Source checksum mismatch: {entry['file']}")
    return manifest


def validate_panel(panel):
    if panel.duplicated(["iso3", "year"]).any():
        raise ValueError("Duplicate country-year keys")
    for col in [
        "treatable",
        "preventable",
        "avoidable",
        "spend_ppp",
        "gdp_ppp_constant",
        "population",
    ]:
        if (panel[col].dropna() <= 0).any():
            raise ValueError(f"Nonpositive {col}")
    for col in [
        "health_gdp_pct",
        "public_share",
        "oop_share",
        "age65_pct",
        "urban_pct",
    ]:
        if not panel[col].dropna().between(0, 100).all():
            raise ValueError(f"Out-of-range percentage: {col}")
    comparable = panel.dropna(subset=["avoidable", "treatable", "preventable"])
    if (
        (comparable.avoidable - comparable.treatable - comparable.preventable).abs() > 2
    ).any():
        raise ValueError("Mortality components do not add up within rounding tolerance")


def add_lags(panel):
    panel = panel.sort_values(["iso3", "year"]).copy()
    columns = [
        "treatable",
        "preventable",
        "spend_real_proxy",
        "gdp_ppp_constant",
        "age65_pct",
        "oop_share",
        "public_share",
        "urban_pct",
    ]
    previous_year = panel.groupby("iso3").year.shift()
    continuous = panel.year.eq(previous_year + 1)
    for col in columns:
        panel[f"lag_{col}"] = panel.groupby("iso3")[col].shift().where(continuous)
    for col in ["treatable", "spend_real_proxy", "gdp_ppp_constant"]:
        panel[f"log_{col}"] = np.log(panel[col])
        panel[f"log_lag_{col}"] = np.log(panel[f"lag_{col}"])
    return panel


def main():
    manifest = verify_snapshot()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    mortality = pd.read_csv(RAW / "oecd_mortality.csv.gz")
    selected = mortality.loc[
        mortality.SEX.eq("_T")
        & mortality.AGE.eq("_T")
        & mortality.UNIT_MEASURE.eq("DT_10P5HB")
        & mortality.CALC_METHODOLOGY.eq("STANDARD")
    ].copy()
    if selected.duplicated(["REF_AREA", "TIME_PERIOD", "MEASURE"]).any():
        raise ValueError("OECD dimensions are not unique after selection")
    wide = selected.pivot(
        index=["REF_AREA", "TIME_PERIOD"], columns="MEASURE", values="OBS_VALUE"
    ).reset_index()
    wide = wide.rename(
        columns={
            "REF_AREA": "iso3",
            "TIME_PERIOD": "year",
            "TRTM": "treatable",
            "PREVM": "preventable",
            "AVM": "avoidable",
        }
    )
    countries = pd.DataFrame(
        [
            {
                "iso3": x["id"],
                "country": x["name"],
                "region": x["region"]["value"],
                "income_group": x["incomeLevel"]["value"],
            }
            for x in read_json("countries.json.gz")[1]
            if x["region"]["id"] != "NA"
        ]
    )
    included = sorted(set(wide.iso3) & set(countries.iso3))
    grid = pd.MultiIndex.from_product(
        [included, range(START_YEAR - 1, END_YEAR + 1)], names=["iso3", "year"]
    ).to_frame(index=False)
    panel = grid.merge(countries, on="iso3", validate="many_to_one").merge(
        wide, on=["iso3", "year"], how="left", validate="one_to_one"
    )
    for code, column in INDICATORS.items():
        records = [
            {"iso3": x["countryiso3code"], "year": int(x["date"]), column: x["value"]}
            for x in read_json(f"{code}.json.gz")[1]
            if x["countryiso3code"] in included
        ]
        indicator = pd.DataFrame(records)
        panel = panel.merge(
            indicator, on=["iso3", "year"], how="left", validate="one_to_one"
        )
    # A macro-deflated spending proxy, not a health-sector price index.
    panel["spend_real_proxy"] = panel.health_gdp_pct / 100 * panel.gdp_ppp_constant
    validate_panel(panel)
    panel = add_lags(panel)
    panel = panel.loc[panel.year.between(START_YEAR, END_YEAR)].reset_index(drop=True)
    panel.to_csv(PROCESSED / "panel.csv", index=False, float_format="%.10g")
    audit = {
        "countries": len(included),
        "grid_rows": len(panel),
        "mortality_rows": int(panel.treatable.notna().sum()),
        "complete_cross_section_rows": int(
            panel[["spend_ppp", "treatable"]].notna().all(axis=1).sum()
        ),
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "missing_counts": {
            k: int(panel[k].isna().sum()) for k in ["treatable", *INDICATORS.values()]
        },
        "source_files": len(manifest),
        "source_sha256_verified": True,
        "income_groups_note": "Current World Bank classification, not historical classification",
        "excluded_oecd_codes": sorted(set(wide.iso3) - set(included)),
    }
    (REPORTS / "data_quality.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    with sqlite3.connect(ROOT / "data" / "atlas.sqlite") as con:
        panel.to_sql("panel", con, if_exists="replace", index=False)
        con.execute("CREATE UNIQUE INDEX panel_key ON panel(iso3, year)")
        con.executescript((ROOT / "sql" / "views.sql").read_text(encoding="utf-8"))
        pd.read_sql_query("SELECT * FROM annual_summary", con).to_csv(
            REPORTS / "annual_summary.csv", index=False
        )
    print(json.dumps(audit, indent=2), flush=True)
    return panel


if __name__ == "__main__":
    main()

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
WEB = ROOT / "web"
START_YEAR = 2010
END_YEAR = 2023
SEED = 42
INDICATORS = {
    "SH.XPD.CHEX.PP.CD": "spend_ppp",
    "SH.XPD.CHEX.GD.ZS": "health_gdp_pct",
    "SH.XPD.GHED.CH.ZS": "public_share",
    "SH.XPD.OOPC.CH.ZS": "oop_share",
    "NY.GDP.PCAP.PP.KD": "gdp_ppp_constant",
    "SP.POP.65UP.TO.ZS": "age65_pct",
    "SP.DYN.LE00.IN": "life_expectancy",
    "SP.POP.TOTL": "population",
    "SP.URB.TOTL.IN.ZS": "urban_pct",
}
OECD_URL = "https://sdmx.oecd.org/public/rest/v1/data/OECD.ELS.HD,DSD_HEALTH_STAT@DF_AM,1.1/?startPeriod=2010&endPeriod=2023&format=csvfile"

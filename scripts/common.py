"""Shared paths and settings."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
CHARTS = OUTPUTS / "charts"
DB_PATH = ROOT / "data" / "olist.sqlite"

# Months with full data. Sep 2016 to Dec 2016 is very sparse and Sep to Oct 2018 is cut off.
WINDOW_START = "2017-01-01"
WINDOW_END = "2018-08-31"

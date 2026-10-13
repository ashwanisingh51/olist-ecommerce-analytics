"""Run every query in sql/analysis_queries.sql against the SQLite database and print the results."""

import sqlite3

import pandas as pd

from common import DB_PATH, ROOT


def main() -> None:
    text = (ROOT / "sql" / "analysis_queries.sql").read_text(encoding="utf-8")
    blocks = [b.strip() for b in text.split(";") if "SELECT" in b.upper() or "WITH" in b.upper()]
    with sqlite3.connect(DB_PATH) as con:
        for i, block in enumerate(blocks, start=1):
            title = next((line[3:] for line in block.splitlines() if line[:3].strip().rstrip(".").isdigit() or line.startswith("-- ") and line[3:4].isdigit()), f"query {i}")
            result = pd.read_sql_query(block, con)
            print(f"\n[{i}] {title.strip()} -> {len(result)} rows")
            print(result.head(12).to_string(index=False))


if __name__ == "__main__":
    main()

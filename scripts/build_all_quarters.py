"""
Build a combined multi-quarter h1b_public_wage_fact and export to parquet.

Runs extract_h1b_lca_data.py for every available quarter, unions all the
resulting CSVs into single DuckDB tables (h1b_lca_cases, h1b_lca_worksites),
then materialises h1b_public_wage_fact and exports a single combined parquet
for the DuckDB-WASM live query tool.

Usage:
    python scripts/build_all_quarters.py
    python scripts/build_all_quarters.py --dry-run   # just print what would run
"""

import argparse
import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
WASM_DIR = ROOT / "data" / "wasm"
DB_PATH = ROOT / "database" / "immigration.duckdb"

# Quarters where we have at least the cases file
QUARTERS = [
    (2024, "Q4"),
    (2025, "Q1"),
    (2025, "Q2"),
    (2025, "Q3"),
    (2025, "Q4"),
    (2026, "Q1"),
]


def run_etl(fy: int, quarter: str, dry_run: bool = False) -> bool:
    """Run extract_h1b_lca_data for one quarter. Returns True on success."""
    import subprocess
    cmd = [sys.executable, str(ROOT / "scripts" / "extract_h1b_lca_data.py"),
           "--fy", str(fy), "--quarter", quarter, "--skip-download"]
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Running ETL: FY{fy} {quarter}")
    if dry_run:
        return True
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"  ERROR: ETL failed for FY{fy} {quarter}")
        return False
    return True


def union_csvs_into_duckdb(con: duckdb.DuckDBPyConnection) -> None:
    """Union all per-quarter case + worksite CSVs into single DuckDB tables."""
    print("\nUnioning CSVs into DuckDB...")

    case_csvs = sorted(PROCESSED_DIR.glob("h1b_lca_cases_fy*.csv"))
    worksite_csvs = sorted(PROCESSED_DIR.glob("h1b_lca_worksites_fy*.csv"))

    if not case_csvs:
        raise RuntimeError("No case CSVs found in data/processed/")

    print(f"  Found {len(case_csvs)} case files, {len(worksite_csvs)} worksite files")

    # Build UNION ALL query for cases
    case_union = " UNION ALL ".join(
        f"SELECT * FROM read_csv_auto('{p}', header=true, ignore_errors=true)"
        for p in case_csvs
    )
    con.execute("DROP TABLE IF EXISTS h1b_lca_cases")
    con.execute(f"CREATE TABLE h1b_lca_cases AS {case_union}")
    n_cases = con.execute("SELECT COUNT(*) FROM h1b_lca_cases").fetchone()[0]
    print(f"  h1b_lca_cases: {n_cases:,} rows")

    # Build UNION ALL query for worksites (skip empty files)
    non_empty_wsites = [
        p for p in worksite_csvs
        if p.stat().st_size > 200  # header-only files are ~150 bytes
    ]
    if non_empty_wsites:
        ws_union = " UNION ALL ".join(
            f"SELECT * FROM read_csv_auto('{p}', header=true, ignore_errors=true)"
            for p in non_empty_wsites
        )
        con.execute("DROP TABLE IF EXISTS h1b_lca_worksites")
        con.execute(f"CREATE TABLE h1b_lca_worksites AS {ws_union}")
    else:
        # All worksites missing — create empty table from first case CSV schema hint
        con.execute("DROP TABLE IF EXISTS h1b_lca_worksites")
        con.execute("""
            CREATE TABLE h1b_lca_worksites (
                case_number VARCHAR, worksite_sequence INTEGER,
                worksite_workers DOUBLE, worksite_city VARCHAR,
                worksite_county VARCHAR, worksite_state VARCHAR,
                worksite_postal_code VARCHAR, secondary_entity VARCHAR,
                secondary_entity_business_name VARCHAR,
                wage_rate_of_pay_from DOUBLE, wage_rate_of_pay_to DOUBLE,
                wage_unit_of_pay VARCHAR, prevailing_wage DOUBLE,
                pw_unit_of_pay VARCHAR, pw_wage_level_raw VARCHAR,
                wage_level VARCHAR, weighted_entries_per_worker DOUBLE,
                annual_wage_from DOUBLE, annual_wage_to DOUBLE,
                annual_prevailing_wage DOUBLE, wage_plausibility_flag VARCHAR,
                fiscal_year INTEGER, quarter VARCHAR, source_file VARCHAR
            )
        """)
    n_ws = con.execute("SELECT COUNT(*) FROM h1b_lca_worksites").fetchone()[0]
    print(f"  h1b_lca_worksites: {n_ws:,} rows ({len(non_empty_wsites)} files with data)")


def build_wage_fact(con: duckdb.DuckDBPyConnection) -> None:
    """Materialise h1b_public_wage_fact using the existing SQL in export_to_postgres."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_to_postgres import PUBLIC_WAGE_FACT_SQL

    # Worksite CSVs are all VARCHAR when read_csv_auto sees mixed quarters.
    # Re-cast numeric columns explicitly so the wage fact COALESCE doesn't fail.
    print("\nNormalising worksite column types...")
    con.execute("""
        CREATE OR REPLACE TABLE h1b_lca_worksites AS
        SELECT
            case_number,
            TRY_CAST(worksite_workers AS DOUBLE) AS worksite_workers,
            worksite_city, worksite_county, worksite_state, worksite_postal_code,
            secondary_entity, secondary_entity_business_name,
            TRY_CAST(wage_rate_of_pay_from AS DOUBLE) AS wage_rate_of_pay_from,
            TRY_CAST(wage_rate_of_pay_to AS DOUBLE) AS wage_rate_of_pay_to,
            wage_unit_of_pay,
            TRY_CAST(prevailing_wage AS DOUBLE) AS prevailing_wage,
            pw_unit_of_pay, pw_wage_level_raw, wage_level,
            TRY_CAST(weighted_entries_per_worker AS DOUBLE) AS weighted_entries_per_worker,
            TRY_CAST(annual_wage_from AS DOUBLE) AS annual_wage_from,
            TRY_CAST(annual_wage_to AS DOUBLE) AS annual_wage_to,
            TRY_CAST(annual_prevailing_wage AS DOUBLE) AS annual_prevailing_wage,
            wage_plausibility_flag,
            TRY_CAST(fiscal_year AS INTEGER) AS fiscal_year,
            quarter, source_file
        FROM h1b_lca_worksites
    """)

    print("Materialising h1b_public_wage_fact...")
    con.execute(PUBLIC_WAGE_FACT_SQL)
    n = con.execute("SELECT COUNT(*) FROM h1b_public_wage_fact").fetchone()[0]
    quarters = con.execute(
        "SELECT fiscal_year, quarter, COUNT(*) FROM h1b_public_wage_fact GROUP BY 1,2 ORDER BY 1,2"
    ).fetchall()
    print(f"  h1b_public_wage_fact: {n:,} total rows")
    for fy, q, cnt in quarters:
        print(f"    FY{fy} {q}: {cnt:,}")


def export_parquet(con: duckdb.DuckDBPyConnection) -> Path:
    """Export h1b_public_wage_fact to a single combined parquet file."""
    WASM_DIR.mkdir(parents=True, exist_ok=True)
    out = WASM_DIR / "h1b_lca_combined.parquet"
    print(f"\nExporting parquet → {out}")
    con.execute(f"""
        COPY (
            SELECT * FROM h1b_public_wage_fact
            WHERE case_status = 'Certified'
              AND wage_plausibility_flag = 'PLAUSIBLE'
              AND annual_wage_from IS NOT NULL
        ) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    mb = out.stat().st_size / 1024 / 1024
    print(f"  {mb:.1f} MB written")
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build combined multi-quarter H-1B parquet.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run without executing.")
    parser.add_argument("--skip-etl", action="store_true", help="Skip per-quarter ETL, just union existing CSVs.")
    args = parser.parse_args(argv)

    print("=" * 72)
    print("  H-1B Multi-Quarter Build")
    print("=" * 72)

    if not args.skip_etl:
        for fy, q in QUARTERS:
            suffix = f"FY{fy}_{q}"
            cases_raw = ROOT / "data" / "raw" / "dol_lca" / f"LCA_Disclosure_Data_{suffix}.xlsx"
            if not cases_raw.exists():
                print(f"\nSkipping FY{fy} {q} — no cases file found")
                continue
            run_etl(fy, q, dry_run=args.dry_run)

    if args.dry_run:
        print("\n[DRY RUN] Would union CSVs, build wage fact, export parquet.")
        return 0

    con = duckdb.connect(str(DB_PATH))
    union_csvs_into_duckdb(con)
    build_wage_fact(con)
    out = export_parquet(con)
    con.close()

    print(f"\nDone. Update h1b_query.html PARQUET_URL to point to:")
    print(f"  data/wasm/h1b_lca_combined.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

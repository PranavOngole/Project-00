"""
Extract refusal/workload data from State Department PDFs.
Source 1: NIV Workload by Visa Category FY2024 (applications/issued/refused by visa type)
Source 2: B-Visa Adjusted Refusal Rates FY2024 (refusal rate by nationality)
Outputs:
  - data/processed/niv_workload_fy2024.csv
  - data/processed/b_visa_refusal_rates.csv
  - Both loaded into database/immigration.duckdb
"""

import re
import pdfplumber
import pandas as pd
import duckdb
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "database" / "immigration.duckdb"


def extract_niv_workload():
    """Extract the NIV Workload table from the FY2024 PDF.

    Returns a DataFrame with columns: visa_category, issued, refused, total_applications, refusal_rate
    """
    pdf_path = BASE_DIR / "data" / "raw" / "pdf" / "niv_workload_fy2024.pdf"
    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Skip headers and title rows
                    if not row or not row[0]:
                        continue
                    if row[0] in ("Visa Category", "Worldwide NIV Workload by Visa Category FY 2024"):
                        continue
                    if row[0].startswith("The refused totals"):
                        continue

                    visa_cat = row[0].strip()
                    issued = _parse_int(row[1])
                    refused = _parse_int(row[2])
                    total_apps = _parse_int(row[3])

                    if issued is not None:
                        all_rows.append({
                            "visa_category": visa_cat,
                            "issued": issued,
                            "refused": refused,
                            "total_applications": total_apps,
                        })

    df = pd.DataFrame(all_rows)
    # Calculate refusal rate
    df["refusal_rate"] = (df["refused"] / df["total_applications"] * 100).round(2)
    df["fiscal_year"] = 2024

    out_path = BASE_DIR / "data" / "processed" / "niv_workload_fy2024.csv"
    df.to_csv(out_path, index=False)
    print(f"NIV Workload: {len(df)} visa categories extracted")
    print(f"  Total applications: {df['total_applications'].sum():,}")
    print(f"  Total issued: {df['issued'].sum():,}")
    print(f"  Total refused: {df['refused'].sum():,}")
    print(f"  Saved to {out_path}")
    return df


def extract_b_visa_refusals():
    """Extract the B-Visa adjusted refusal rates by nationality from FY2024 PDF.

    Returns a DataFrame with columns: nationality, adjusted_refusal_rate
    """
    pdf_path = BASE_DIR / "data" / "raw" / "pdf" / "b_visa_refusal_fy2024.pdf"
    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    if row[0].strip().upper() == "NATIONALITY":
                        continue
                    if "OVERALL" in (row[0] or "").upper() and "ADJUSTED" in (row[0] or "").upper():
                        continue

                    nationality = row[0].strip().title()
                    rate_str = row[1].strip() if row[1] else ""

                    # Parse percentage
                    rate_match = re.search(r"([\d.]+)%", rate_str)
                    if rate_match:
                        rate = float(rate_match.group(1))
                        all_rows.append({
                            "nationality": nationality,
                            "adjusted_refusal_rate": rate,
                        })

    df = pd.DataFrame(all_rows)
    df["fiscal_year"] = 2024

    out_path = BASE_DIR / "data" / "processed" / "b_visa_refusal_rates.csv"
    df.to_csv(out_path, index=False)
    print(f"\nB-Visa Refusals: {len(df)} nationalities extracted")
    print(f"  Highest refusal: {df.loc[df['adjusted_refusal_rate'].idxmax(), 'nationality']} ({df['adjusted_refusal_rate'].max():.1f}%)")
    print(f"  Lowest refusal: {df.loc[df['adjusted_refusal_rate'].idxmin(), 'nationality']} ({df['adjusted_refusal_rate'].min():.1f}%)")
    print(f"  Saved to {out_path}")
    return df


def load_into_duckdb(df_workload, df_refusals):
    """Load both DataFrames into DuckDB as new tables."""
    con = duckdb.connect(str(DB_PATH))

    # Drop if exists, then create
    con.execute("DROP TABLE IF EXISTS niv_workload")
    con.execute("CREATE TABLE niv_workload AS SELECT * FROM df_workload")

    con.execute("DROP TABLE IF EXISTS b_visa_refusals")
    con.execute("CREATE TABLE b_visa_refusals AS SELECT * FROM df_refusals")

    # Verify
    print("\n=== DuckDB Verification ===")
    tables = con.execute("SELECT table_name FROM information_schema.tables ORDER BY table_name").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")

    wl_count = con.execute("SELECT COUNT(*) FROM niv_workload").fetchone()[0]
    br_count = con.execute("SELECT COUNT(*) FROM b_visa_refusals").fetchone()[0]
    print(f"niv_workload: {wl_count} rows")
    print(f"b_visa_refusals: {br_count} rows")

    # Show top refused visa categories
    print("\nTop 10 visa categories by refusal rate:")
    rows = con.execute("""
        SELECT visa_category, issued, refused, total_applications, refusal_rate
        FROM niv_workload
        WHERE visa_category != 'Grand Total' AND total_applications >= 100
        ORDER BY refusal_rate DESC
        LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:10s}  issued={r[1]:>8,}  refused={r[2]:>8,}  apps={r[3]:>8,}  rate={r[4]:.1f}%")

    # Show top/bottom B-visa refusal countries
    print("\nB-Visa: Top 10 highest refusal rates:")
    rows = con.execute("""
        SELECT nationality, adjusted_refusal_rate
        FROM b_visa_refusals ORDER BY adjusted_refusal_rate DESC LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:30s}  {r[1]:.1f}%")

    print("\nB-Visa: Top 10 lowest refusal rates (excl. 0%):")
    rows = con.execute("""
        SELECT nationality, adjusted_refusal_rate
        FROM b_visa_refusals WHERE adjusted_refusal_rate > 0
        ORDER BY adjusted_refusal_rate ASC LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:30s}  {r[1]:.1f}%")

    con.close()


def _parse_int(val):
    """Parse a string like '10,969,936' into an integer."""
    if not val:
        return None
    cleaned = val.strip().replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None


def main():
    """Run the full extraction and load pipeline."""
    print("=" * 60)
    print("  Refusal Data ETL Pipeline")
    print("=" * 60)

    df_workload = extract_niv_workload()
    df_refusals = extract_b_visa_refusals()
    load_into_duckdb(df_workload, df_refusals)

    print("\nDone.")


if __name__ == "__main__":
    main()

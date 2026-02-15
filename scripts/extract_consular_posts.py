"""
Extract Table IV — Summary of Visas Issued by Issuing Office, FY2024.
Source: data/raw/annual_report/table_iv.pdf
Output: data/processed/visas_by_consular_post_fy2024.csv + DuckDB table
"""

import re
import pdfplumber
import pandas as pd
import duckdb
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "database" / "immigration.duckdb"
PDF_PATH = BASE_DIR / "data" / "raw" / "annual_report" / "table_iv.pdf"
OUT_PATH = BASE_DIR / "data" / "processed" / "visas_by_consular_post_fy2024.csv"


def parse_int(val):
    """Parse '10,969,936' -> 10969936, '-' -> 0."""
    if not val or val.strip() == '-':
        return 0
    cleaned = val.strip().replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return 0


def extract_consular_posts():
    """Extract visa issuances by consular post from Table IV."""
    all_rows = []
    current_region = None

    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # Skip headers
                if line.startswith('Table IV') or line.startswith('Summary of') or \
                   line.startswith('Fiscal Year') or line.startswith('____') or \
                   line.startswith('___') or line.startswith('Combination') or \
                   line.startswith('Visas and') or line.startswith('Issuing Office') or \
                   line.startswith('1 ') or line.startswith('2 ') or line.startswith('3 '):
                    continue

                # Check for region headers (standalone text, no numbers)
                regions = ['Africa', 'East Asia and Pacific', 'Europe and Eurasia',
                          'Near East', 'South and Central Asia', 'Western Hemisphere']
                if line in regions:
                    current_region = line
                    continue

                # Check for region totals
                if line.startswith('Region Total'):
                    match = re.search(r'Region Total.*?\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)$', line)
                    if match:
                        all_rows.append({
                            'region': current_region,
                            'issuing_office': f'Region Total: {current_region}',
                            'iv_issued': parse_int(match.group(1)),
                            'niv_issued': parse_int(match.group(2)),
                            'border_crossing_cards': parse_int(match.group(3)),
                            'is_total': True,
                        })
                    continue

                # Check for grand totals
                if line.startswith('Grand Total'):
                    match = re.search(r'Grand Total.*?\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)$', line)
                    if match:
                        all_rows.append({
                            'region': 'GRAND TOTAL',
                            'issuing_office': 'Grand Total',
                            'iv_issued': parse_int(match.group(1)),
                            'niv_issued': parse_int(match.group(2)),
                            'border_crossing_cards': parse_int(match.group(3)),
                            'is_total': True,
                        })
                    continue

                # Regular data row: "Office Name NUM NUM NUM" or "Office Name NUM NUM -"
                match = re.match(r'^(.+?)\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)$', line)
                if match:
                    office = match.group(1).strip()
                    iv = parse_int(match.group(2))
                    niv = parse_int(match.group(3))
                    bcc = parse_int(match.group(4))

                    all_rows.append({
                        'region': current_region,
                        'issuing_office': office,
                        'iv_issued': iv,
                        'niv_issued': niv,
                        'border_crossing_cards': bcc,
                        'is_total': False,
                    })

    df = pd.DataFrame(all_rows)
    df['fiscal_year'] = 2024
    return df


def main():
    print("=" * 60)
    print("  Table IV — Visas by Consular Post ETL")
    print("=" * 60)

    df = extract_consular_posts()

    # Save CSV
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    data_rows = df[~df['is_total']]
    total_row = df[df['issuing_office'] == 'Grand Total']

    print(f"\nExtracted {len(data_rows)} consular posts")
    print(f"Regions: {df['region'].nunique()}")

    if not total_row.empty:
        t = total_row.iloc[0]
        print(f"\nGrand Totals:")
        print(f"  IV Issued:  {t['iv_issued']:>12,}")
        print(f"  NIV Issued: {t['niv_issued']:>12,}")
        print(f"  BCC:        {t['border_crossing_cards']:>12,}")

    # Top 10 busiest posts
    print("\nTop 10 Busiest Posts (by NIV issued):")
    top = data_rows.nlargest(10, 'niv_issued')
    for _, r in top.iterrows():
        print(f"  {r['issuing_office']:45s}  NIV: {r['niv_issued']:>9,}  IV: {r['iv_issued']:>7,}")

    # Load to DuckDB
    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS visas_by_consular_post")
    con.execute("CREATE TABLE visas_by_consular_post AS SELECT * FROM df")
    count = con.execute("SELECT COUNT(*) FROM visas_by_consular_post").fetchone()[0]
    con.close()

    print(f"\nLoaded {count} rows into DuckDB table 'visas_by_consular_post'")
    print(f"Saved to {OUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()

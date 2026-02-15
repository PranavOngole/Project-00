"""
Extract Table XIX — Visa Ineligibility Grounds from State Department Annual Report FY2024.
Source: data/raw/annual_report/table_xix.pdf
Output: data/processed/visa_ineligibility_grounds_fy2024.csv + DuckDB table
"""

import re
import pdfplumber
import pandas as pd
import duckdb
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "database" / "immigration.duckdb"
PDF_PATH = BASE_DIR / "data" / "raw" / "annual_report" / "table_xix.pdf"
OUT_PATH = BASE_DIR / "data" / "processed" / "visa_ineligibility_grounds_fy2024.csv"


def parse_int(val):
    """Parse '3,010,544' -> 3010544, '-' -> 0."""
    if not val or val.strip() == '-':
        return 0
    cleaned = val.strip().replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return 0


def extract_refusal_grounds():
    """Extract visa ineligibility grounds from Table XIX PDF using text parsing."""
    all_rows = []

    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            for line in lines:
                # Skip headers, titles, footnotes
                if not line.strip():
                    continue
                if line.startswith('Table XIX'):
                    continue
                if line.startswith('Immigrant and Nonimmigrant'):
                    continue
                if line.startswith('(by Grounds'):
                    continue
                if line.startswith('Fiscal Year'):
                    continue
                if line.startswith('Immigrant'):
                    continue
                if line.startswith('Ineligibility'):
                    continue
                if line.startswith('Grounds for Refusal'):
                    continue
                if line.strip().startswith('1 ') or line.strip().startswith('2 '):
                    continue
                if 'does not necessarily' in line or 'ineligibility does not' in line:
                    continue
                if 'separately recorded' in line or 'evidence that' in line:
                    continue
                if 'during the listed' in line or 'visa may be' in line:
                    continue
                if 'because an application' in line:
                    continue

                # Try to match a line with an INA section code at the start and numbers at the end
                # Pattern: INA_SECTION DESCRIPTION NUM NUM NUM NUM
                # Numbers are at the end, separated by spaces, can be '-' or '1,234'
                match = re.match(
                    r'^(\S+(?:\s+\S+)?)\s+(.+?)\s+'
                    r'([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)\s+([\d,]+|-)$',
                    line.strip()
                )

                if match:
                    ina_raw = match.group(1)
                    desc = match.group(2).strip()
                    iv_find = parse_int(match.group(3))
                    iv_over = parse_int(match.group(4))
                    niv_find = parse_int(match.group(5))
                    niv_over = parse_int(match.group(6))

                    # Check if this is a continuation of previous row's INA section
                    # (some INA codes appear multiple times with different descriptions)
                    all_rows.append({
                        'ina_section': ina_raw,
                        'description': desc,
                        'iv_finding': iv_find,
                        'iv_overcome': iv_over,
                        'niv_finding': niv_find,
                        'niv_overcome': niv_over,
                    })
                else:
                    # This might be a continuation line (description wrapping)
                    # or a line with "Total Grounds of Ineligibility"
                    total_match = re.match(
                        r'^Total Grounds of Ineligibility:\s+'
                        r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)$',
                        line.strip()
                    )
                    if total_match:
                        all_rows.append({
                            'ina_section': 'TOTAL',
                            'description': 'Total Grounds of Ineligibility',
                            'iv_finding': parse_int(total_match.group(1)),
                            'iv_overcome': parse_int(total_match.group(2)),
                            'niv_finding': parse_int(total_match.group(3)),
                            'niv_overcome': parse_int(total_match.group(4)),
                        })
                    elif all_rows and not any(c.isdigit() for c in line.strip()[-5:]):
                        # Continuation of previous description
                        all_rows[-1]['description'] += ' ' + line.strip()

    df = pd.DataFrame(all_rows)
    df['fiscal_year'] = 2024

    # Clean up descriptions
    df['description'] = df['description'].str.strip()

    return df


def load_to_duckdb(df):
    """Load into DuckDB as visa_ineligibility_grounds table."""
    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS visa_ineligibility_grounds")
    con.execute("CREATE TABLE visa_ineligibility_grounds AS SELECT * FROM df")
    count = con.execute("SELECT COUNT(*) FROM visa_ineligibility_grounds").fetchone()[0]
    con.close()
    return count


def main():
    print("=" * 60)
    print("  Table XIX — Visa Ineligibility Grounds ETL")
    print("=" * 60)

    df = extract_refusal_grounds()

    # Save CSV
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nExtracted {len(df)} refusal grounds")
    print(f"Saved to {OUT_PATH}")

    # Validate against known totals
    total_row = df[df['ina_section'] == 'TOTAL']
    if not total_row.empty:
        t = total_row.iloc[0]
        print(f"\nTotal IV Findings:  {t['iv_finding']:>10,}")
        print(f"Total IV Overcome:  {t['iv_overcome']:>10,}")
        print(f"Total NIV Findings: {t['niv_finding']:>10,}")
        print(f"Total NIV Overcome: {t['niv_overcome']:>10,}")

    # Top NIV refusal grounds
    non_total = df[df['ina_section'] != 'TOTAL'].copy()
    print("\nTop 10 NIV Refusal Grounds:")
    top_niv = non_total.nlargest(10, 'niv_finding')
    for _, r in top_niv.iterrows():
        pct = r['niv_finding'] / 3891139 * 100 if 3891139 > 0 else 0
        print(f"  {r['ina_section']:30s}  {r['niv_finding']:>10,}  ({pct:5.1f}%)  {r['description'][:50]}")

    # Load to DuckDB
    count = load_to_duckdb(df)
    print(f"\nLoaded {count} rows into DuckDB table 'visa_ineligibility_grounds'")
    print("Done.")


if __name__ == "__main__":
    main()

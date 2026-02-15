"""
Merge 28 fiscal-year sheets from the State Department NIV detail workbook
into a single clean CSV.

Source : data/raw/state_dept_niv_detail_fy97-24.xlsx  (sheets FY97–FY24)
Output : data/processed/visa_issuances_fy97-24.csv
"""

from pathlib import Path
import pandas as pd
import re

# ── paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "state_dept_niv_detail_fy97-24.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "visa_issuances_fy97-24.csv"


# ── column-name normalization ────────────────────────────────────────────────
# FY22-FY24 dropped hyphens and changed a few names.  We map everything to
# the canonical hyphenated form used in FY97-FY21.

_EXPLICIT_RENAMES = {
    "B1/B2":  "B-1,2",
    "BBBCC":  "B-1,2/BCC",
    "BBBCV":  "B-1,2/BCV",
    "C1/D":   "C-1/D",
    "C4/D3":  "C-4/D-3",
}


def _normalize_visa_col(col: str) -> str:
    """Normalize a single visa-type column name to its canonical form.

    Rules applied in order:
      1. Explicit renames for irregular mappings (BBBCC → B-1,2/BCC, etc.)
      2. Insert a hyphen after the letter prefix for codes like A1 → A-1,
         H1B → H-1B, NATO1 → NATO-1, CW1 → CW-1, etc.

    Non-visa columns (country, fiscal_year, Grand Total, etc.) pass through
    unchanged.
    """
    if col in _EXPLICIT_RENAMES:
        return _EXPLICIT_RENAMES[col]

    # Pattern: one or more uppercase letters, then a digit (optionally more
    # alphanumeric chars).  Insert hyphen between the letter-prefix and the
    # first digit.  E.g. H1B → H-1B, NATO5 → NATO-5, E2C → E-2C
    normalized = re.sub(r"^([A-Z]+)(\d.*)$", r"\1-\2", col)
    return normalized


def normalize_columns(columns: list[str]) -> list[str]:
    """Apply normalization to every column in a header list."""
    return [_normalize_visa_col(c) for c in columns]


# ── fiscal-year extraction ───────────────────────────────────────────────────
def sheet_name_to_year(name: str) -> int:
    """Convert sheet name like 'FY97' or 'FY05' to a four-digit year."""
    suffix = int(name.replace("FY", ""))
    return 1900 + suffix if suffix >= 97 else 2000 + suffix


# ── row filtering ────────────────────────────────────────────────────────────
# Region headers, subtotals, grand totals, and blank rows are not country data.
_NON_COUNTRY_PATTERNS = re.compile(
    r"^(Africa|Asia|Europe|North America|Central America|"
    r"South America|Caribbean|Oceania|Unknown|"
    r"Totals for .+|Grand Totals?|Total)$",
    re.IGNORECASE,
)


def is_country_row(value) -> bool:
    """Return True if the first-column value represents a real country."""
    if pd.isna(value):
        return False
    return _NON_COUNTRY_PATTERNS.match(str(value).strip()) is None


# ── main ETL ─────────────────────────────────────────────────────────────────
def merge_niv_sheets() -> pd.DataFrame:
    """Read, clean, and merge all 28 NIV sheets into one DataFrame."""
    frames: list[pd.DataFrame] = []

    with pd.ExcelFile(RAW_FILE) as workbook:
        for sheet in workbook.sheet_names:
            df = pd.read_excel(workbook, sheet_name=sheet)

            # 1. Rename first column → country
            first_col = df.columns[0]
            df = df.rename(columns={first_col: "country"})

            # 2. Normalize visa column names
            df.columns = normalize_columns(list(df.columns))

            # 3. Drop trailing None/NaN columns (artifacts from Excel)
            df = df.loc[:, df.columns.notna()]
            none_cols = [c for c in df.columns if c is None or c == "None"]
            if none_cols:
                df = df.drop(columns=none_cols)

            # 4. Filter to country rows only
            df = df[df["country"].apply(is_country_row)].copy()

            # 5. Add fiscal_year
            df["fiscal_year"] = sheet_name_to_year(sheet)

            frames.append(df)
            print(f"  {sheet} → {sheet_name_to_year(sheet)}  "
                  f"({len(df)} countries, {len(df.columns)} cols)")

    # 6. Concatenate all sheets (outer join keeps every visa type)
    merged = pd.concat(frames, ignore_index=True)

    # 7. Move identifiers to the front
    id_cols = ["fiscal_year", "country"]
    visa_cols = [c for c in merged.columns if c not in id_cols]
    merged = merged[id_cols + visa_cols]

    # 8. Fill missing visa counts with 0 (missing = no issuances that year)
    for col in visa_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0).astype(int)

    # 9. Sort for reproducibility
    merged = merged.sort_values(["fiscal_year", "country"]).reset_index(drop=True)

    return merged


def main():
    """Entry point: merge sheets and write output CSV."""
    print(f"Reading {RAW_FILE.name} …")
    merged = merge_niv_sheets()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    print(f"\nDone — {len(merged):,} rows × {len(merged.columns)} columns")
    print(f"Fiscal years: {merged['fiscal_year'].min()}–{merged['fiscal_year'].max()}")
    print(f"Unique countries: {merged['country'].nunique()}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

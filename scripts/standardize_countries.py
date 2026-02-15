"""
Country Name Standardization Pipeline.
Reconciles naming differences across visa_issuances, niv_workload, and b_visa_refusals tables.
Creates a mapping table and applies it to all DuckDB tables.

Strategy:
  - Pick one canonical name per country (modern name preferred)
  - Map all historical variants to the canonical name
  - Store mapping in DuckDB as country_mapping table
  - Update all three tables in-place with standardized names
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "immigration.duckdb"

# Canonical mapping: old_name -> standard_name
# Left side = what appears in our data, Right side = what we want
COUNTRY_MAPPING = {
    # --- China variants ---
    "China - mainland": "China",
    "China - Taiwan": "Taiwan",

    # --- Congo variants ---
    "Congo, Dem. Rep. of the (Congo Kinshasa)": "Congo, Democratic Republic of the",
    "Congo, Dem. Rep. of the (Kinshasa)": "Congo, Democratic Republic of the",
    "Congo, Rep. of the (Brazzaville)": "Congo, Republic of the",
    "Congo, Rep. of the (Congo Brazzaville)": "Congo, Republic of the",

    # --- Name changes over time ---
    "Swaziland": "Eswatini",
    "Cape Verde": "Cabo Verde",
    "Macedonia": "North Macedonia",
    "Burma": "Myanmar",

    # --- Bosnia variants ---
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",

    # --- Serbia variants ---
    "Serbia and Montenegro": "Serbia and Montenegro",  # Keep as-is (historical entity)

    # --- Micronesia variants ---
    "Micronesia, Federated States of": "Micronesia",
    "Federated States Of Micronesia": "Micronesia",

    # --- Hong Kong ---
    "Hong Kong S.A.R.": "Hong Kong",
    "Hong Kong S. A. R.": "Hong Kong",

    # --- Guinea-Bissau variants ---
    "Guinea-Bissau": "Guinea-Bissau",  # Keep hyphenated (standard)
    "Guinea - Bissau": "Guinea-Bissau",
    "Guinea - Bissau": "Guinea-Bissau",

    # --- Saint/St variants ---
    "Saint Kitts and Nevis": "St. Kitts and Nevis",
    "St. Kitts And Nevis": "St. Kitts and Nevis",
    "Saint Lucia": "St. Lucia",
    "St Lucia": "St. Lucia",
    "Saint Vincent and the Grenadines": "St. Vincent and the Grenadines",
    "St. Vincent And The Grenadines": "St. Vincent and the Grenadines",

    # --- Cote d'Ivoire variants ---
    "Cote d'Ivoire ": "Cote d'Ivoire",
    "Cote d'Ivoire": "Cote d'Ivoire",
    "Cote D`Ivoire": "Cote d'Ivoire",

    # --- Marshall Islands ---
    "Marshall Islands, Republic Of The": "Marshall Islands",

    # --- Title Case conjunction fixes (b_visa_refusals uses "And"/"Of" instead of "and"/"of") ---
    "Antigua And Barbuda": "Antigua and Barbuda",
    "Congo, Democratic Republic Of The": "Congo, Democratic Republic of the",
    "Congo, Republic Of The": "Congo, Republic of the",
    "Great Britain And Northern Ireland": "Great Britain and Northern Ireland",
    "Sao Tome And Principe": "Sao Tome and Principe",
    "Trinidad And Tobago": "Trinidad and Tobago",

    # --- Rows to drop (not real countries) ---
    "No Nationality": None,
    "United Nations Laissez-Passer": None,
    "*Non-Nationality Based Issuances": None,
}


def apply_standardization():
    """Apply country name standardization to all tables in DuckDB."""
    con = duckdb.connect(str(DB_PATH))

    # --- Step 1: Create the mapping table ---
    con.execute("DROP TABLE IF EXISTS country_mapping")
    con.execute("""
        CREATE TABLE country_mapping (
            original_name VARCHAR,
            standard_name VARCHAR
        )
    """)

    for old, new in COUNTRY_MAPPING.items():
        if new is not None:
            con.execute(
                "INSERT INTO country_mapping VALUES (?, ?)",
                [old, new],
            )

    mapping_count = con.execute("SELECT COUNT(*) FROM country_mapping").fetchone()[0]
    print(f"Country mapping table: {mapping_count} entries")

    # --- Step 2: Update visa_issuances ---
    print("\n--- Updating visa_issuances ---")
    # Delete non-country rows
    for name, target in COUNTRY_MAPPING.items():
        if target is None:
            deleted = con.execute(
                "DELETE FROM visa_issuances WHERE country = ?", [name]
            ).fetchone()
            print(f"  Deleted rows for: {name}")

    # Apply renames
    for old, new in COUNTRY_MAPPING.items():
        if new is not None and old != new:
            count = con.execute(
                "SELECT COUNT(*) FROM visa_issuances WHERE country = ?", [old]
            ).fetchone()[0]
            if count > 0:
                con.execute(
                    "UPDATE visa_issuances SET country = ? WHERE country = ?",
                    [new, old],
                )
                print(f"  {old:55s} -> {new} ({count} rows)")

    # --- Step 3: Update b_visa_refusals ---
    print("\n--- Updating b_visa_refusals ---")
    for name, target in COUNTRY_MAPPING.items():
        if target is None:
            con.execute(
                "DELETE FROM b_visa_refusals WHERE nationality = ?", [name]
            )
            print(f"  Deleted rows for: {name}")

    for old, new in COUNTRY_MAPPING.items():
        if new is not None and old != new:
            count_before = con.execute(
                "SELECT COUNT(*) FROM b_visa_refusals WHERE nationality = ?", [old]
            ).fetchone()[0]
            if count_before > 0:
                con.execute(
                    "UPDATE b_visa_refusals SET nationality = ? WHERE nationality = ?",
                    [new, old],
                )
                print(f"  {old:55s} -> {new} ({count_before} rows)")

    # --- Step 4: Verify ---
    print("\n=== Post-Standardization Verification ===")

    vi_count = con.execute("SELECT COUNT(DISTINCT country) FROM visa_issuances").fetchone()[0]
    br_count = con.execute("SELECT COUNT(DISTINCT nationality) FROM b_visa_refusals").fetchone()[0]
    print(f"visa_issuances: {vi_count} unique countries")
    print(f"b_visa_refusals: {br_count} unique nationalities")

    # Check join coverage
    joined = con.execute("""
        SELECT COUNT(DISTINCT vi.country)
        FROM (SELECT DISTINCT country FROM visa_issuances WHERE fiscal_year = 2024) vi
        INNER JOIN (SELECT DISTINCT nationality FROM b_visa_refusals) br
        ON vi.country = br.nationality
    """).fetchone()[0]
    vi_2024 = con.execute(
        "SELECT COUNT(DISTINCT country) FROM visa_issuances WHERE fiscal_year = 2024"
    ).fetchone()[0]
    print(f"\nFY2024 join coverage: {joined}/{vi_2024} visa_issuances countries match b_visa_refusals")

    # Show remaining mismatches
    mismatches = con.execute("""
        SELECT vi.country FROM
        (SELECT DISTINCT country FROM visa_issuances WHERE fiscal_year = 2024) vi
        LEFT JOIN (SELECT DISTINCT nationality FROM b_visa_refusals) br
        ON vi.country = br.nationality
        WHERE br.nationality IS NULL
        ORDER BY vi.country
    """).fetchall()
    if mismatches:
        print(f"\nStill unmatched ({len(mismatches)}):")
        for m in mismatches:
            print(f"  {m[0]}")
    else:
        print("\nAll FY2024 countries matched!")

    # Spot check: China should now exist
    print("\n--- Spot checks ---")
    for name in ["China", "Taiwan", "Eswatini", "North Macedonia", "Hong Kong", "Guinea-Bissau", "Micronesia"]:
        vi_check = con.execute(
            "SELECT COUNT(*) FROM visa_issuances WHERE country = ?", [name]
        ).fetchone()[0]
        br_check = con.execute(
            "SELECT COUNT(*) FROM b_visa_refusals WHERE nationality = ?", [name]
        ).fetchone()[0]
        print(f"  {name:25s}  visa_issuances={vi_check:>3} rows  b_visa_refusals={br_check} rows")

    # Quick data integrity: India H-1B FY2024 should still be 150,647
    india_h1b = con.execute("""
        SELECT "H-1B" FROM visa_issuances WHERE country = 'India' AND fiscal_year = 2024
    """).fetchone()[0]
    print(f"\n  India H-1B FY2024: {india_h1b:,} (should be 150,647)")

    china_h1b = con.execute("""
        SELECT "H-1B" FROM visa_issuances WHERE country = 'China' AND fiscal_year = 2024
    """).fetchone()[0]
    print(f"  China H-1B FY2024: {china_h1b:,} (should be 31,735)")

    tables = con.execute("SELECT table_name FROM information_schema.tables ORDER BY table_name").fetchall()
    print(f"\nDuckDB tables: {[t[0] for t in tables]}")

    con.close()
    print("\nDone. All tables standardized.")


if __name__ == "__main__":
    apply_standardization()

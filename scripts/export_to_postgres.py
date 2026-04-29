"""
Export the DuckDB analytics warehouse into Postgres-ready artifacts.

Default behavior:
  - Materialize h1b_public_wage_fact in DuckDB.
  - Generate database/postgres_schema.sql from current DuckDB table schemas.
  - Export selected tables as CSV files under data/postgres_exports/.

Optional behavior:
  - If --dsn is provided and psycopg is installed, create the schema and load
    the exported CSVs into Postgres.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import duckdb


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "immigration.duckdb"
DEFAULT_SCHEMA_PATH = BASE_DIR / "database" / "postgres_schema.sql"
DEFAULT_EXPORT_DIR = BASE_DIR / "data" / "postgres_exports"
POSTGRES_SCHEMA = "immigration"

DEFAULT_TABLES = [
    "visa_issuances",
    "niv_workload",
    "b_visa_refusals",
    "country_mapping",
    "b_visa_workload_by_country",
    "niv_workload_by_country",
    "visa_ineligibility_grounds",
    "visas_by_consular_post",
    "h1b_lca_cases",
    "h1b_lca_worksites",
    "h1b_wage_summary",
    "h1b_cap_season_proxy",
    "h1b_public_wage_fact",
]

PUBLIC_WAGE_FACT_SQL = """
CREATE OR REPLACE TABLE h1b_public_wage_fact AS
WITH state_map AS (
    SELECT *
    FROM (VALUES
        ('ALABAMA', 'AL'), ('ALASKA', 'AK'), ('ARIZONA', 'AZ'), ('ARKANSAS', 'AR'),
        ('CALIFORNIA', 'CA'), ('COLORADO', 'CO'), ('CONNECTICUT', 'CT'), ('DELAWARE', 'DE'),
        ('DISTRICT OF COLUMBIA', 'DC'), ('FLORIDA', 'FL'), ('GEORGIA', 'GA'), ('HAWAII', 'HI'),
        ('IDAHO', 'ID'), ('ILLINOIS', 'IL'), ('INDIANA', 'IN'), ('IOWA', 'IA'),
        ('KANSAS', 'KS'), ('KENTUCKY', 'KY'), ('LOUISIANA', 'LA'), ('MAINE', 'ME'),
        ('MARYLAND', 'MD'), ('MASSACHUSETTS', 'MA'), ('MICHIGAN', 'MI'), ('MINNESOTA', 'MN'),
        ('MISSISSIPPI', 'MS'), ('MISSOURI', 'MO'), ('MONTANA', 'MT'), ('NEBRASKA', 'NE'),
        ('NEVADA', 'NV'), ('NEW HAMPSHIRE', 'NH'), ('NEW JERSEY', 'NJ'), ('NEW MEXICO', 'NM'),
        ('NEW YORK', 'NY'), ('NORTH CAROLINA', 'NC'), ('NORTH DAKOTA', 'ND'), ('OHIO', 'OH'),
        ('OKLAHOMA', 'OK'), ('OREGON', 'OR'), ('PENNSYLVANIA', 'PA'), ('PUERTO RICO', 'PR'),
        ('RHODE ISLAND', 'RI'), ('SOUTH CAROLINA', 'SC'), ('SOUTH DAKOTA', 'SD'),
        ('TENNESSEE', 'TN'), ('TEXAS', 'TX'), ('UTAH', 'UT'), ('VERMONT', 'VT'),
        ('VIRGINIA', 'VA'), ('WASHINGTON', 'WA'), ('WEST VIRGINIA', 'WV'),
        ('WISCONSIN', 'WI'), ('WYOMING', 'WY')
    ) AS states(state_name, state_code)
),
worksite AS (
    SELECT
        ROW_NUMBER() OVER (
            PARTITION BY case_number
            ORDER BY
                worksite_state,
                worksite_city,
                worksite_postal_code,
                wage_rate_of_pay_from,
                prevailing_wage
        ) AS worksite_sequence,
        *
    FROM h1b_lca_worksites
),
base_raw AS (
    SELECT
        c.fiscal_year,
        c.quarter,
        c.source_file AS case_source_file,
        w.source_file AS worksite_source_file,
        c.case_number,
        COALESCE(w.worksite_sequence, 1) AS worksite_sequence,
        c.case_status,
        c.received_date,
        c.decision_date,
        c.visa_class,
        c.begin_date,
        c.end_date,
        c.employer_name,
        c.trade_name_dba,
        c.employer_city,
        c.employer_state,
        c.employer_postal_code,
        c.employer_country,
        c.naics_code,
        c.job_title,
        c.soc_code,
        c.soc_title,
        c.full_time_position,
        c.total_worker_positions AS case_worker_positions,
        c.new_employment,
        c.continued_employment,
        c.change_previous_employment,
        c.new_concurrent_employment,
        c.change_employer,
        c.amended_petition,
        COALESCE(w.worksite_workers, c.worksite_workers, c.total_worker_positions) AS worker_positions,
        COALESCE(w.worksite_city, c.worksite_city) AS worksite_city,
        COALESCE(w.worksite_county, c.worksite_county) AS worksite_county,
        COALESCE(w.worksite_state, c.worksite_state) AS worksite_state_raw,
        COALESCE(w.worksite_postal_code, c.worksite_postal_code) AS worksite_postal_code,
        COALESCE(w.secondary_entity, CAST(c.secondary_entity AS VARCHAR)) AS secondary_entity,
        COALESCE(w.secondary_entity_business_name, c.secondary_entity_business_name) AS secondary_entity_business_name,
        COALESCE(w.wage_rate_of_pay_from, c.wage_rate_of_pay_from) AS wage_rate_of_pay_from,
        COALESCE(w.wage_rate_of_pay_to, c.wage_rate_of_pay_to) AS wage_rate_of_pay_to,
        COALESCE(w.wage_unit_of_pay, c.wage_unit_of_pay) AS wage_unit_of_pay,
        COALESCE(w.prevailing_wage, c.prevailing_wage) AS prevailing_wage,
        COALESCE(w.pw_unit_of_pay, c.pw_unit_of_pay) AS pw_unit_of_pay,
        COALESCE(NULLIF(w.pw_wage_level_raw, ''), c.pw_wage_level_raw) AS pw_wage_level_raw,
        COALESCE(NULLIF(w.wage_level, 'Unknown'), c.wage_level, 'Unknown') AS wage_level,
        COALESCE(w.weighted_entries_per_worker, c.weighted_entries_per_worker, 0) AS wage_weight,
        COALESCE(w.annual_wage_from, c.annual_wage_from) AS annual_wage_from,
        COALESCE(w.annual_wage_to, c.annual_wage_to) AS annual_wage_to,
        COALESCE(w.annual_prevailing_wage, c.annual_prevailing_wage) AS annual_prevailing_wage,
        COALESCE(w.wage_plausibility_flag, c.wage_plausibility_flag) AS wage_plausibility_flag,
        c.total_worksite_locations,
        c.h1b_dependent,
        c.willful_violator,
        c.support_h1b,
        c.statutory_basis
    FROM h1b_lca_cases c
    LEFT JOIN worksite w ON c.case_number = w.case_number
),
base AS (
    SELECT
        b.*,
        CASE
            WHEN LENGTH(TRIM(b.worksite_state_raw)) = 2 THEN UPPER(TRIM(b.worksite_state_raw))
            ELSE COALESCE(sm.state_code, b.worksite_state_raw)
        END AS worksite_state
    FROM base_raw b
    LEFT JOIN state_map sm ON UPPER(TRIM(b.worksite_state_raw)) = sm.state_name
),
features AS (
    SELECT
        *,
        worker_positions * wage_weight AS weighted_entries,
        CASE
            WHEN annual_prevailing_wage IS NULL OR annual_prevailing_wage = 0 THEN NULL
            ELSE ROUND((annual_wage_from - annual_prevailing_wage) / annual_prevailing_wage * 100, 2)
        END AS wage_premium_pct,
        CASE
            WHEN annual_wage_from IS NULL THEN 'Unknown'
            WHEN annual_wage_from < 50000 THEN '<$50K'
            WHEN annual_wage_from < 75000 THEN '$50K-$75K'
            WHEN annual_wage_from < 100000 THEN '$75K-$100K'
            WHEN annual_wage_from < 125000 THEN '$100K-$125K'
            WHEN annual_wage_from < 150000 THEN '$125K-$150K'
            WHEN annual_wage_from < 200000 THEN '$150K-$200K'
            WHEN annual_wage_from < 250000 THEN '$200K-$250K'
            WHEN annual_wage_from < 300000 THEN '$250K-$300K'
            ELSE '$300K+'
        END AS salary_band,
        CASE
            WHEN case_status = 'Certified'
             AND new_employment > 0
             AND begin_date >= DATE '2026-04-01'
             AND begin_date <= DATE '2026-12-31'
             AND wage_plausibility_flag = 'PLAUSIBLE'
            THEN true
            ELSE false
        END AS cap_season_proxy_flag
    FROM base
)
SELECT
    CONCAT(case_number, '-', LPAD(CAST(worksite_sequence AS VARCHAR), 3, '0')) AS wage_fact_id,
    *
FROM features
"""


def pg_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def validate_table_name(table: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"Unsafe table name: {table}")
    return table


def pg_type(duckdb_type: str) -> str:
    dtype = duckdb_type.upper()
    if dtype.startswith("VARCHAR") or dtype == "UUID":
        return "TEXT"
    if dtype in {"BIGINT", "INTEGER", "SMALLINT", "TINYINT", "UBIGINT", "UINTEGER"}:
        return "BIGINT" if "BIGINT" in dtype or dtype.startswith("U") else "INTEGER"
    if dtype in {"HUGEINT", "UHUGEINT"}:
        return "NUMERIC"
    if dtype in {"DOUBLE", "FLOAT", "REAL"}:
        return "DOUBLE PRECISION"
    if dtype.startswith("DECIMAL"):
        return dtype
    if dtype == "BOOLEAN":
        return "BOOLEAN"
    if dtype == "DATE":
        return "DATE"
    if "TIMESTAMP" in dtype:
        return "TIMESTAMP"
    return "TEXT"


def connect_duckdb() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH))


def table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table],
        ).fetchone()[0]
    )


def ensure_public_wage_fact(con: duckdb.DuckDBPyConnection) -> None:
    required = ["h1b_lca_cases", "h1b_lca_worksites"]
    missing = [table for table in required if not table_exists(con, table)]
    if missing:
        raise RuntimeError(f"Cannot build h1b_public_wage_fact; missing DuckDB tables: {', '.join(missing)}")
    con.execute(PUBLIC_WAGE_FACT_SQL)


def get_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    rows = con.execute(f"DESCRIBE {pg_ident(table)}").fetchall()
    return [(row[0], row[1]) for row in rows]


def available_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()
    ]


def build_schema_sql(con: duckdb.DuckDBPyConnection, tables: Sequence[str]) -> str:
    parts: list[str] = [
        "-- Auto-generated from database/immigration.duckdb by scripts/export_to_postgres.py",
        "-- Safe to rerun: tables are created if missing; indexes are created if missing.",
        "",
        f"CREATE SCHEMA IF NOT EXISTS {pg_ident(POSTGRES_SCHEMA)};",
        f"SET search_path TO {pg_ident(POSTGRES_SCHEMA)};",
        "",
    ]

    for table in tables:
        cols = get_columns(con, table)
        column_lines = [f"    {pg_ident(name)} {pg_type(dtype)}" for name, dtype in cols]
        parts.append(f"CREATE TABLE IF NOT EXISTS {pg_ident(POSTGRES_SCHEMA)}.{pg_ident(table)} (")
        parts.append(",\n".join(column_lines))
        parts.append(");")
        parts.append("")

    index_specs = [
        ("h1b_lca_cases", "case_number"),
        ("h1b_lca_cases", "employer_name"),
        ("h1b_lca_cases", "soc_code"),
        ("h1b_lca_cases", "worksite_state"),
        ("h1b_lca_worksites", "case_number"),
        ("h1b_public_wage_fact", "case_number"),
        ("h1b_public_wage_fact", "employer_name"),
        ("h1b_public_wage_fact", "soc_code"),
        ("h1b_public_wage_fact", "worksite_state"),
        ("h1b_public_wage_fact", "wage_level"),
        ("h1b_public_wage_fact", "cap_season_proxy_flag"),
        ("h1b_cap_season_proxy", "case_number"),
        ("h1b_wage_summary", "employer_name"),
        ("h1b_wage_summary", "soc_code"),
        ("visa_issuances", "country"),
        ("visa_issuances", "fiscal_year"),
    ]
    table_set = set(tables)
    for table, column in index_specs:
        if table in table_set:
            idx_name = f"idx_{table}_{column}"
            parts.append(
                f"CREATE INDEX IF NOT EXISTS {pg_ident(idx_name)} "
                f"ON {pg_ident(POSTGRES_SCHEMA)}.{pg_ident(table)} ({pg_ident(column)});"
            )

    parts.extend(
        [
            "",
            "-- Future v1.2 selection-odds tables. These are intentionally empty until",
            "-- scripts/model_h1b_selection_odds.py is implemented.",
            f"CREATE TABLE IF NOT EXISTS {pg_ident(POSTGRES_SCHEMA)}.{pg_ident('h1b_selection_parameters')} (",
            "    selection_fy INTEGER,",
            "    selection_round TEXT,",
            "    eligible_registrations BIGINT,",
            "    selected_registrations BIGINT,",
            "    selected_beneficiaries BIGINT,",
            "    regular_cap_slots BIGINT,",
            "    masters_cap_slots BIGINT,",
            "    registration_start_date DATE,",
            "    registration_end_date DATE,",
            "    selection_notice_date DATE,",
            "    filing_start_date DATE,",
            "    filing_end_date DATE,",
            "    source_url TEXT,",
            "    source_note TEXT,",
            "    as_of_date DATE",
            ");",
            "",
            f"CREATE TABLE IF NOT EXISTS {pg_ident(POSTGRES_SCHEMA)}.{pg_ident('h1b_profile_probability_index')} (",
            "    selection_fy INTEGER,",
            "    employer_name TEXT,",
            "    soc_code TEXT,",
            "    soc_title TEXT,",
            "    worksite_state TEXT,",
            "    worksite_city TEXT,",
            "    wage_level TEXT,",
            "    wage_weight INTEGER,",
            "    profile_bucket TEXT,",
            "    comparable_case_count BIGINT,",
            "    comparable_proxy_positions DOUBLE PRECISION,",
            "    comparable_weighted_entries DOUBLE PRECISION,",
            "    estimated_probability DOUBLE PRECISION,",
            "    p05_probability DOUBLE PRECISION,",
            "    p95_probability DOUBLE PRECISION,",
            "    confidence_score TEXT,",
            "    benchmark_probability DOUBLE PRECISION,",
            "    percentile_vs_comparable_wages DOUBLE PRECISION",
            ");",
            "",
        ]
    )
    return "\n".join(parts)


def export_table(con: duckdb.DuckDBPyConnection, table: str, export_dir: Path) -> tuple[Path, int]:
    validate_table_name(table)
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / f"{table}.csv"
    con.execute(
        f"COPY {pg_ident(table)} TO {sql_literal(out_path)} "
        "(HEADER, DELIMITER ',', NULL '')"
    )
    row_count = con.execute(f"SELECT COUNT(*) FROM {pg_ident(table)}").fetchone()[0]
    return out_path, row_count


def write_schema(path: Path, schema_sql: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schema_sql, encoding="utf-8")


def copy_to_postgres(dsn: str, schema_path: Path, export_dir: Path, con: duckdb.DuckDBPyConnection, tables: Sequence[str]) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Loading to Postgres requires psycopg. Install with: python3 -m pip install psycopg[binary]") from exc

    with psycopg.connect(dsn) as pg:
        with pg.cursor() as cur:
            cur.execute(schema_path.read_text(encoding="utf-8"))
            for table in tables:
                columns = [name for name, _ in get_columns(con, table)]
                column_list = ", ".join(pg_ident(col) for col in columns)
                cur.execute(f"TRUNCATE TABLE {pg_ident(POSTGRES_SCHEMA)}.{pg_ident(table)};")
                csv_path = export_dir / f"{table}.csv"
                copy_sql = (
                    f"COPY {pg_ident(POSTGRES_SCHEMA)}.{pg_ident(table)} ({column_list}) "
                    "FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
                )
                with csv_path.open("r", encoding="utf-8", newline="") as handle:
                    with cur.copy(copy_sql) as copy:
                        for chunk in iter(lambda: handle.read(1024 * 1024), ""):
                            copy.write(chunk)
        pg.commit()


def parse_tables(value: str | None, con: duckdb.DuckDBPyConnection) -> list[str]:
    if not value or value.lower() == "default":
        tables = DEFAULT_TABLES
    elif value.lower() == "all":
        tables = available_tables(con)
    else:
        tables = [item.strip() for item in value.split(",") if item.strip()]
    for table in tables:
        validate_table_name(table)
        if not table_exists(con, table):
            raise RuntimeError(f"DuckDB table does not exist: {table}")
    return tables


def summarize_exports(exports: Iterable[tuple[str, Path, int]]) -> None:
    print("\nExported CSVs:")
    for table, path, rows in exports:
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"  {table:32s} {rows:>10,} rows  {size_mb:>8.2f} MB  {path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export DuckDB tables into Postgres-ready schema and CSV files.")
    parser.add_argument("--tables", default="default", help="Comma-separated tables, 'default', or 'all'.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--schema-path", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN"), help="Optional Postgres DSN. Defaults to POSTGRES_DSN env var.")
    parser.add_argument("--skip-wage-fact", action="store_true", help="Do not rebuild h1b_public_wage_fact before export.")
    parser.add_argument("--no-load", action="store_true", help="Export files only, even if --dsn or POSTGRES_DSN is set.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    con = connect_duckdb()

    if not args.skip_wage_fact:
        print("Materializing h1b_public_wage_fact in DuckDB...")
        ensure_public_wage_fact(con)

    tables = parse_tables(args.tables, con)

    print(f"Writing Postgres schema to {args.schema_path}")
    write_schema(args.schema_path, build_schema_sql(con, tables))

    exports = []
    for table in tables:
        path, rows = export_table(con, table, args.export_dir)
        exports.append((table, path, rows))
    summarize_exports(exports)

    if args.dsn and not args.no_load:
        print("\nLoading exported CSVs into Postgres...")
        copy_to_postgres(args.dsn, args.schema_path, args.export_dir, con, tables)
        print("Postgres load complete.")
    elif args.dsn and args.no_load:
        print("\nPOSTGRES_DSN/--dsn provided, but --no-load was set. Skipped Postgres load.")
    else:
        print("\nNo Postgres DSN provided. Generated schema + CSV exports only.")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

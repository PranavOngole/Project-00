"""
Local H-1B wage dashboard backend.

Run from the project root:
  python -m wage_dashboard.app

Or:
  python scripts/wage_query_app.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import duckdb


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
DB_PATH = Path(os.environ.get("WAGE_DASHBOARD_DB", PROJECT_ROOT / "database" / "immigration.duckdb"))
TABLE = "h1b_public_wage_fact"

# Latest public aggregate selected-registration count currently documented on
# USCIS's H-1B electronic registration page for FY2026. The dashboard lets the
# user change this number because exact group-level selections are not public.
DEFAULT_SELECTED_REGISTRATIONS = 120_141
SELECTION_SOURCE_URL = "https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations/h-1b-electronic-registration-process"

SORT_COLUMNS = {
    "employer_name",
    "soc_title",
    "worksite_state",
    "worksite_city",
    "wage_level",
    "worker_positions",
    "annual_wage_from",
    "wage_premium_pct",
    "weighted_entries",
    "begin_date",
}

GROUP_DIMENSIONS = {
    "employer": ("employer_name", "Company"),
    "occupation": ("soc_title", "Job Type"),
    "soc": ("soc_code", "Occupation Code"),
    "location": ("worksite_city || ', ' || worksite_state", "City + State"),
    "state": ("worksite_state", "State"),
    "wage_level": ("wage_level", "Wage Level"),
    "salary_band": ("salary_band", "Salary Band"),
    "h1b_dependent": ("CAST(h1b_dependent AS VARCHAR)", "H-1B Dependent"),
}


def con_ro() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def first_value(params: dict[str, list[str]], key: str, default: str = "") -> str:
    value = params.get(key, [default])[0]
    return value.strip() if isinstance(value, str) else default


def bool_value(params: dict[str, list[str]], key: str, default: bool = False) -> bool:
    value = first_value(params, key, "true" if default else "false").lower()
    return value in {"1", "true", "yes", "on"}


def int_value(params: dict[str, list[str]], key: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(first_value(params, key, str(default)))
    except ValueError:
        value = default
    return max(min_value, min(max_value, value))


def float_or_none(params: dict[str, list[str]], key: str) -> float | None:
    value = first_value(params, key)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def selected_total(params: dict[str, list[str]]) -> int:
    return int_value(params, "selected_total", DEFAULT_SELECTED_REGISTRATIONS, 1, 5_000_000)


def build_where(params: dict[str, list[str]], include_search_filters: bool = True) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []

    if include_search_filters:
        for key, column in [
            ("employer", "employer_name"),
            ("occupation", "soc_title"),
            ("soc", "soc_code"),
            ("city", "worksite_city"),
            ("case_number", "case_number"),
        ]:
            value = first_value(params, key)
            if value:
                clauses.append(f"{column} ILIKE ?")
                values.append(f"%{value}%")

        state = first_value(params, "state").upper()
        if state:
            clauses.append("worksite_state = ?")
            values.append(state)

        wage_level = first_value(params, "wage_level")
        if wage_level:
            clauses.append("wage_level = ?")
            values.append(wage_level)

        salary_band = first_value(params, "salary_band")
        if salary_band:
            clauses.append("salary_band = ?")
            values.append(salary_band)

        min_wage = float_or_none(params, "min_wage")
        if min_wage is not None:
            clauses.append("annual_wage_from >= ?")
            values.append(min_wage)

        max_wage = float_or_none(params, "max_wage")
        if max_wage is not None:
            clauses.append("annual_wage_from <= ?")
            values.append(max_wage)

    case_status = first_value(params, "case_status", "Certified")
    if case_status:
        clauses.append("case_status = ?")
        values.append(case_status)

    if bool_value(params, "plausible", True):
        clauses.append("wage_plausibility_flag = 'PLAUSIBLE'")

    if bool_value(params, "cap_proxy", False):
        clauses.append("cap_season_proxy_flag = true")

    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return where, values


def universe_weighted_entries(params: dict[str, list[str]]) -> float:
    where, values = build_where(params, include_search_filters=False)
    with con_ro() as con:
        return float(con.execute(f"""
            SELECT COALESCE(SUM(weighted_entries), 0)
            FROM {TABLE}
            {where}
        """, values).fetchone()[0] or 0)


def expected_picks(weighted_entries: float | int | None, denominator: float, selected: int) -> float | None:
    if not weighted_entries or denominator <= 0:
        return None
    return float(selected) * float(weighted_entries) / denominator


def query_options() -> dict[str, Any]:
    with con_ro() as con:
        states = [row[0] for row in con.execute(f"""
            SELECT DISTINCT worksite_state
            FROM {TABLE}
            WHERE worksite_state IS NOT NULL
            ORDER BY worksite_state
        """).fetchall()]
        wage_levels = [row[0] for row in con.execute(f"""
            SELECT DISTINCT wage_level
            FROM {TABLE}
            WHERE wage_level IS NOT NULL
            ORDER BY CASE wage_level
                WHEN 'Level I' THEN 1
                WHEN 'Level II' THEN 2
                WHEN 'Level III' THEN 3
                WHEN 'Level IV' THEN 4
                ELSE 5
            END
        """).fetchall()]
        statuses = [row[0] for row in con.execute(f"""
            SELECT DISTINCT case_status
            FROM {TABLE}
            WHERE case_status IS NOT NULL
            ORDER BY case_status
        """).fetchall()]
        salary_bands = [row[0] for row in con.execute(f"""
            SELECT DISTINCT salary_band
            FROM {TABLE}
            WHERE salary_band IS NOT NULL
            ORDER BY CASE salary_band
                WHEN '<$50K' THEN 1
                WHEN '$50K-$75K' THEN 2
                WHEN '$75K-$100K' THEN 3
                WHEN '$100K-$125K' THEN 4
                WHEN '$125K-$150K' THEN 5
                WHEN '$150K-$200K' THEN 6
                WHEN '$200K-$250K' THEN 7
                WHEN '$250K-$300K' THEN 8
                WHEN '$300K+' THEN 9
                ELSE 10
            END
        """).fetchall()]
        total_rows = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    return {
        "states": states,
        "wage_levels": wage_levels,
        "statuses": statuses,
        "salary_bands": salary_bands,
        "total_rows": total_rows,
        "default_selected_registrations": DEFAULT_SELECTED_REGISTRATIONS,
        "selection_source_url": SELECTION_SOURCE_URL,
        "group_dimensions": [{"value": key, "label": label} for key, (_, label) in GROUP_DIMENSIONS.items()],
    }


def query_search(params: dict[str, list[str]]) -> dict[str, Any]:
    where, values = build_where(params)
    selected = selected_total(params)
    denominator = universe_weighted_entries(params)
    limit = int_value(params, "limit", 100, 10, 1000)
    offset = int_value(params, "offset", 0, 0, 1_000_000)
    sort = first_value(params, "sort", "worker_positions")
    if sort not in SORT_COLUMNS:
        sort = "worker_positions"
    direction = "ASC" if first_value(params, "dir", "desc").lower() == "asc" else "DESC"

    with con_ro() as con:
        summary = con.execute(f"""
            SELECT
                COUNT(*) AS public_wage_rows,
                COUNT(DISTINCT case_number) AS lca_filings,
                COALESCE(SUM(worker_positions), 0) AS jobs_requested,
                COALESCE(SUM(weighted_entries), 0) AS lottery_weight_points,
                MEDIAN(annual_wage_from) AS median_offer,
                AVG(wage_premium_pct) AS avg_offer_vs_required
            FROM {TABLE}
            {where}
        """, values).fetchone()

        rows = con.execute(f"""
            SELECT
                case_number,
                employer_name,
                soc_code,
                soc_title,
                worksite_city,
                worksite_state,
                wage_level,
                worker_positions,
                weighted_entries,
                annual_wage_from,
                annual_wage_to,
                annual_prevailing_wage,
                wage_premium_pct,
                salary_band,
                begin_date,
                cap_season_proxy_flag,
                h1b_dependent,
                secondary_entity_business_name
            FROM {TABLE}
            {where}
            ORDER BY {sort} {direction} NULLS LAST, employer_name ASC
            LIMIT ? OFFSET ?
        """, values + [limit, offset]).fetchall()

    weighted = summary[3] or 0
    estimated = expected_picks(weighted, denominator, selected)
    jobs_requested = summary[2] or 0
    estimated_rate = (estimated / jobs_requested * 100) if estimated is not None and jobs_requested else None
    columns = [
        "case_number",
        "employer_name",
        "soc_code",
        "soc_title",
        "worksite_city",
        "worksite_state",
        "wage_level",
        "worker_positions",
        "weighted_entries",
        "annual_wage_from",
        "annual_wage_to",
        "annual_prevailing_wage",
        "wage_premium_pct",
        "salary_band",
        "begin_date",
        "cap_season_proxy_flag",
        "h1b_dependent",
        "secondary_entity_business_name",
    ]
    return {
        "summary": {
            "public_wage_rows": summary[0] or 0,
            "lca_filings": summary[1] or 0,
            "jobs_requested": jobs_requested,
            "lottery_weight_points": weighted,
            "median_offer": summary[4],
            "avg_offer_vs_required": summary[5],
            "estimated_picked": estimated,
            "estimated_pick_rate": estimated_rate,
            "selected_total": selected,
            "universe_weighted_entries": denominator,
        },
        "rows": [dict(zip(columns, row)) for row in rows],
        "limit": limit,
        "offset": offset,
    }


def query_group(params: dict[str, list[str]]) -> dict[str, Any]:
    where, values = build_where(params)
    selected = selected_total(params)
    denominator = universe_weighted_entries(params)
    dimension = first_value(params, "dimension", "employer")
    expr, label = GROUP_DIMENSIONS.get(dimension, GROUP_DIMENSIONS["employer"])
    limit = int_value(params, "limit", 50, 10, 500)

    with con_ro() as con:
        rows = con.execute(f"""
            SELECT
                COALESCE(CAST({expr} AS VARCHAR), 'Unknown') AS group_label,
                COUNT(*) AS public_wage_rows,
                COUNT(DISTINCT case_number) AS lca_filings,
                COALESCE(SUM(worker_positions), 0) AS jobs_requested,
                COALESCE(SUM(weighted_entries), 0) AS lottery_weight_points,
                MEDIAN(annual_wage_from) AS median_offer,
                AVG(wage_premium_pct) AS avg_offer_vs_required,
                SUM(CASE WHEN cap_season_proxy_flag THEN worker_positions ELSE 0 END) AS cap_proxy_jobs
            FROM {TABLE}
            {where}
            GROUP BY 1
            ORDER BY jobs_requested DESC, public_wage_rows DESC
            LIMIT ?
        """, values + [limit]).fetchall()

    columns = [
        "group_label",
        "public_wage_rows",
        "lca_filings",
        "jobs_requested",
        "lottery_weight_points",
        "median_offer",
        "avg_offer_vs_required",
        "cap_proxy_jobs",
    ]
    result_rows = []
    for row in rows:
        entry = dict(zip(columns, row))
        estimated = expected_picks(entry["lottery_weight_points"], denominator, selected)
        entry["estimated_picked"] = estimated
        entry["estimated_pick_rate"] = (
            estimated / entry["jobs_requested"] * 100
            if estimated is not None and entry["jobs_requested"]
            else None
        )
        result_rows.append(entry)

    return {
        "dimension": dimension,
        "dimension_label": label,
        "selected_total": selected,
        "universe_weighted_entries": denominator,
        "rows": result_rows,
    }


def json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def read_static(path: str) -> tuple[bytes, str]:
    rel = "index.html" if path == "/" else path.lstrip("/")
    file_path = (STATIC_DIR / rel).resolve()
    if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
        raise FileNotFoundError(path)
    if file_path.is_dir():
        file_path = file_path / "index.html"
    body = file_path.read_bytes()
    suffix = file_path.suffix.lower()
    content_type = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }.get(suffix, "application/octet-stream")
    return body, content_type


class WageDashboardHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path: str) -> None:
        body, content_type = read_static(path)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/options":
                self.send_json(query_options())
            elif parsed.path == "/api/search":
                self.send_json(query_search(params))
            elif parsed.path == "/api/group":
                self.send_json(query_group(params))
            else:
                self.send_static(parsed.path)
        except FileNotFoundError:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local H-1B wage dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    server = ThreadingHTTPServer((args.host, args.port), WageDashboardHandler)
    print(f"H-1B wage dashboard running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

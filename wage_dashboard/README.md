# H-1B Wage Dashboard

Local browser dashboard for querying `h1b_public_wage_fact` without writing DuckDB SQL.

## Run

From the Project-00 repository root:

```bash
python -m wage_dashboard.app
```

Then open:

```text
http://127.0.0.1:8765
```

You can also use the compatibility launcher:

```bash
python scripts/wage_query_app.py
```

## What It Shows

- Filed jobs requested from public DOL LCA records.
- Estimated picked registrations allocated from a configurable USCIS aggregate selection count.
- LCA filings by company, job, occupation code, city, state, wage level, and salary band.
- Median offered salary.
- Offer premium above the required prevailing wage.
- Lottery weight points from wage level: Level I=1, II=2, III=3, IV=4.
- Cap-season proxy rows for likely new-employment filings.
- H-1B dependent and secondary/client-site signals where public.

## What It Does Not Show

USCIS does not publish selected beneficiaries by company, occupation, location, or wage level. Therefore, the dashboard does not claim exact picked workers. It shows an estimate:

```text
estimated_picked = selected_registrations * group_weighted_entries / universe_weighted_entries
```

The default selected-registration count is `120,141`, from USCIS's latest public FY2026 H-1B registration process update. The input is editable in the UI.

## Files

```text
wage_dashboard/
├── app.py              # Python DuckDB API + static file server
├── static/
│   ├── index.html      # Frontend markup
│   ├── styles.css      # Visual design
│   └── app.js          # Client-side behavior
├── METHODOLOGY.md      # Data and model explanation
├── DESIGN.md           # UX/design notes
└── requirements.txt    # Runtime dependency
```

## Data Dependency

By default the app reads:

```text
database/immigration.duckdb
```

Override with:

```bash
WAGE_DASHBOARD_DB=/path/to/immigration.duckdb python -m wage_dashboard.app
```

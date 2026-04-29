# US Immigration Data Platform

Every year, millions of people apply for U.S. visas. Some get approved. Many don't. The data behind all of this is published by the U.S. Department of State — but it's scattered across Excel files, PDFs, and reports that nobody outside a government office would ever read.

This project takes 28 years of that data (FY1997 through FY2024), cleans it up, and turns it into something you can actually explore. V1.1 adds DOL OFLC H-1B wage intelligence and a live in-browser query tool — no server, no login, no install.

---

## Live Dashboards

| Dashboard | What It Does |
|-----------|-------------|
| [Nonimmigrant Visa Trends](https://pranavongole.github.io/Project-00/dashboard.html) | 28 years of State Department visa data — issuances, refusal rates, embassy workloads |
| [H-1B Wage Intelligence](https://pranavongole.github.io/Project-00/h1b_wages.html) | DOL LCA analytics — wage levels, salary bands, top employers, occupations, cap-season proxy |
| [H-1B Live Query Tool](https://pranavongole.github.io/Project-00/h1b_query.html) | Filter and query 120K+ LCA records in real time, entirely in the browser |

---

## What You Can See

- **How many visas the U.S. issues each year** — and how that number crashed during COVID and recovered after
- **Which countries get the most H-1B work visas** — India gets nearly 5x more than China, and the gap keeps growing
- **What H-1B employers are offering in wages** — certified DOL LCA records show offered annual wages, wage levels, employers, occupations, and worksite hotspots across 120K+ records
- **Where in the world U.S. visas are processed** — the busiest embassy isn't in New Delhi or Beijing, it's in Monterrey, Mexico (681,000 visas in one year)
- **What percentage of applicants get denied, by country** — some countries have refusal rates above 70%
- **The actual legal reasons visas get denied** — Section 214(b) alone accounts for 77% of all nonimmigrant visa denials. That's 3 million people told "you didn't prove you'll go home"
- **How different visa types compare** — H-1B (work), F-1 (student), B-1/2 (tourist), L-1 (transfer), and dozens more

---

## Where the Data Comes From

Core visa issuance data is from the U.S. Department of State, publicly available at [travel.state.gov](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics.html). V1.1 adds public Department of Labor OFLC LCA disclosure data for H-1B wage analysis.

| Source | What's In It |
|--------|-------------|
| NIV Detail Tables (FY1997–2024) | Visa issuances by country and type — 28 years, 199 countries, 90+ visa categories |
| NIV Workload by Category (FY2024) | How many applications were filed, approved, and denied per visa type |
| B-Visa Adjusted Refusal Rates (FY2024) | Country-by-country denial rates for tourist/business visas |
| Table XIX — Ineligibility Grounds (FY2024) | Every legal reason a visa was denied, with counts |
| Table IV — Visas by Issuing Office (FY2024) | Which embassies and consulates processed the most visas |
| DOL OFLC LCA Disclosure + Worksites (FY2026 Q1) | H-1B LCA case, worksite, offered wage, prevailing wage level, employer, SOC, and location records |

---

## How It Works

State Department files and DOL LCA workbooks go in. Six Python scripts clean and transform them. Twelve database tables come out. Two generators produce the full public platform.

```
State Dept files + DOL LCA workbooks
        |
6 ETL scripts (Python + pdfplumber + DuckDB)
        |
12 DuckDB tables, including H-1B LCA wage tables
        |
dashboard.py → dashboard.html (embedded JSON, Plotly)
h1b_wages.html (static analytics, Bloomberg-style)
h1b_lca_fy2026_q1.parquet (3.6MB, ZSTD, 120K rows)
        |
GitHub Pages → 3 live public URLs
```

The visa dashboard embeds all data directly in the HTML as JSON. The H-1B analytics page is fully static. The live query tool runs DuckDB-WASM in the browser — it fetches the parquet file once, then executes SQL queries client-side with no server involved.

Full technical details are in the [Business Requirements Document](docs/BRD.md).

---

## H-1B Wage Intelligence

The H-1B section is built on public DOL OFLC Labor Condition Application records. A few things worth knowing upfront:

- **206K worker positions is not 206K lottery registrations.** One LCA can cover multiple workers. The FY2027 cap registration count (USCIS) was approximately 120,141. The LCA data shows what employers filed and what wages they offered — not who got picked.
- **LCA certification does not prove H-1B approval.** It's a prerequisite, not a guarantee. Use this data for salary intelligence, not headcount.
- **The cap-season proxy** is built from certified new-employment LCAs with employment start dates near October 1, 2026 — a signal for likely FY2027 cap filings, not confirmed lottery winners.

---

## What Makes This Interesting

This isn't just a chart on a webpage. The raw data has real problems:

- **96 different column name variations** across 28 years of Excel files (the government renamed visa categories constantly)
- **Country names don't match between files** — "Korea, South" in one table, "South Korea" in another. 34 mismatches total.
- **PDF tables that resist extraction** — some PDFs have actual table structures, others are just formatted text. Each one needed a different parsing strategy.
- **Data the government doesn't publish** — per-country refusal counts by visa type don't exist in any official report. We reverse-engineered estimates using the formula: `refused = issued x rate / (1 - rate)`
- **H-1B picks are not public** — DOL LCA data can show certified wage offers and likely cap-season filing proxies, but it cannot identify lottery winners, selected beneficiaries, or USCIS-approved petitions.
- **Making 120K rows queryable without a server** — solved with DuckDB-WASM: the parquet file is fetched once, SQL runs in-browser via WebAssembly. No Heroku, no Railway, no API.

An AI agent (Claude Code) wrote every script, built every dashboard, extracted the PDFs, and documented everything. The entire pipeline — from raw Excel to three live public dashboards — was built across two working sessions.

---

## Project Structure

```
US-Immigration-Data/
├── data/
│   ├── raw/                  ← Original government files (Excel + PDF)
│   │   └── dol_lca/          ← DOL OFLC LCA disclosure/worksite workbooks
│   ├── processed/            ← Cleaned CSVs
│   └── wasm/
│       └── h1b_lca_fy2026_q1.parquet  ← 3.6MB ZSTD parquet, served via GitHub Pages CDN
├── database/
│   ├── immigration.duckdb    ← Analytics database
│   └── postgres_schema.sql   ← Postgres-ready schema generated from DuckDB
├── docs/
│   ├── BRD.md                ← Business Requirements Document
│   └── session_notes.md      ← Development log
├── scripts/
│   ├── merge_niv_sheets.py          ← Excel → unified CSV
│   ├── extract_refusal_data.py      ← B-visa refusal PDF → CSV
│   ├── extract_refusal_grounds.py   ← Table XIX PDF → CSV
│   ├── extract_consular_posts.py    ← Table IV PDF → CSV
│   ├── extract_h1b_lca_data.py      ← DOL LCA workbooks → H-1B wage tables
│   ├── export_to_postgres.py        ← DuckDB → Postgres schema/CSV export
│   ├── standardize_countries.py     ← Country name mapping
│   └── dashboard.py                 ← Dashboard generator
├── wage_dashboard/
│   ├── app.py                       ← Local backend/API for wage search
│   ├── static/                      ← Frontend HTML, CSS, JS
│   ├── METHODOLOGY.md               ← Wage and pick-estimate methodology
│   └── DESIGN.md                    ← UI language and design notes
├── dashboard.html            ← Visa trends dashboard (GitHub Pages)
├── h1b_wages.html            ← H-1B wage analytics (GitHub Pages)
├── h1b_query.html            ← Live DuckDB-WASM query tool (GitHub Pages)
├── index.html                ← Landing page linking all three
├── .nojekyll                 ← Bypasses Jekyll so GitHub Pages serves all files
└── CLAUDE.md                 ← AI agent instructions
```

---

## Tech Stack

| What | Why |
|------|-----|
| Python 3.13 | ETL scripting |
| DuckDB | Fast analytical queries without a server |
| DuckDB-WASM | Full SQL engine running in-browser via WebAssembly |
| Apache Arrow + Parquet | Columnar format for the WASM data layer; 3.6MB serves 120K rows |
| pandas + openpyxl | Excel processing |
| pdfplumber | PDF table extraction |
| Plotly.js | Interactive charts |
| GitHub Pages | Free static hosting for all three dashboards |
| Claude Code | AI agent that built the whole thing |

---

## Running It Yourself

The fastest option is to just open the live dashboards above — no install, no setup.

If you want to run the pipeline locally:

```bash
# Install dependencies
pip install duckdb pandas openpyxl pdfplumber plotly

# Run the ETL pipeline (requires the raw government data files)
python scripts/merge_niv_sheets.py
python scripts/extract_refusal_data.py
python scripts/extract_refusal_grounds.py
python scripts/extract_consular_posts.py
python scripts/standardize_countries.py
python scripts/extract_h1b_lca_data.py --fy 2026 --quarter latest

# Generate the visa dashboard
python scripts/dashboard.py

# Run the local H-1B wage query interface
python scripts/wage_query_app.py

# Open dashboard.html in your browser
```

The local wage query interface runs at [http://localhost:8765](http://localhost:8765). It queries `h1b_public_wage_fact` with filters for employer, occupation, SOC, case number, state, city, wage level, salary band, plausible wages, and cap-season proxy rows.

The public [H-1B Live Query Tool](https://pranavongole.github.io/Project-00/h1b_query.html) replicates this interface entirely in the browser — no local setup needed.

## Postgres Export

DuckDB remains the local analytics engine, but the warehouse is now Postgres-ready:

```bash
# Generate database/postgres_schema.sql and CSV exports
python scripts/export_to_postgres.py --tables default --no-load

# Optional: load directly into Postgres when a DSN is available
POSTGRES_DSN="postgresql://user:password@localhost:5432/immigration" \
  python scripts/export_to_postgres.py --tables default
```

The export materializes `h1b_public_wage_fact`, a denormalized worksite-level wage table built for fast salary, employer, occupation, location, and selection-odds analysis.

---

*Built by [Sai Pranav Ongole](https://www.linkedin.com/in/pranavo/) — Part of the DataForge365 series*

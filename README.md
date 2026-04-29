# US Immigration Visa Dashboard

Every year, millions of people apply for U.S. visas. Some get approved. Many don't. The data behind all of this is published by the U.S. Department of State — but it's scattered across Excel files, PDFs, and reports that nobody outside a government office would ever read.

This project takes 28 years of that data (FY1997 through FY2024), cleans it up, and turns it into something you can actually explore.

**[View the Live Dashboard](https://pranavongole.github.io/Project-00/dashboard.html)**

---

## What You Can See

- **How many visas the U.S. issues each year** — and how that number crashed during COVID and recovered after
- **Which countries get the most H-1B work visas** — India gets nearly 5x more than China, and the gap keeps growing
- **What H-1B employers are offering in wages** — certified DOL LCA records show offered annual wages, wage levels, employers, occupations, and worksite hotspots
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

State Department files and DOL LCA workbooks go in. Six Python scripts clean and transform them. Twelve database tables come out. One script generates the entire dashboard as a single HTML file.

```
State Dept files + DOL LCA workbooks
        |
6 ETL scripts (Python + pdfplumber + DuckDB)
        |
12 DuckDB tables, including H-1B LCA wage tables
        |
1 dashboard generator
        |
1 static HTML file → GitHub Pages
```

The dashboard is completely self-contained — all the data is embedded directly in the HTML as JSON. No server, no API calls, no database connection needed. Open the file and everything works.

Full technical details are in the [Business Requirements Document](docs/BRD.md).

---

## What Makes This Interesting

This isn't just a chart on a webpage. The raw data has real problems:

- **96 different column name variations** across 28 years of Excel files (the government renamed visa categories constantly)
- **Country names don't match between files** — "Korea, South" in one table, "South Korea" in another. 34 mismatches total.
- **PDF tables that resist extraction** — some PDFs have actual table structures, others are just formatted text. Each one needed a different parsing strategy.
- **Data the government doesn't publish** — per-country refusal counts by visa type don't exist in any official report. We reverse-engineered estimates using the formula: `refused = issued x rate / (1 - rate)`
- **H-1B picks are not public** — DOL LCA data can show certified wage offers and likely cap-season filing proxies, but it cannot identify lottery winners, selected beneficiaries, or USCIS-approved petitions.

An AI agent (Claude Code) wrote every script, built the dashboard, extracted the PDFs, and documented everything. The entire pipeline — from raw Excel to live dashboard — was built in a single working session.

---

## Project Structure

```
US-Immigration-Data/
├── data/
│   ├── raw/                  ← Original government files (Excel + PDF)
│   │   └── dol_lca/           ← DOL OFLC LCA disclosure/worksite workbooks
│   └── processed/            ← Cleaned CSVs
├── database/
│   ├── immigration.duckdb    ← Analytics database
│   └── postgres_schema.sql   ← Postgres-ready schema generated from DuckDB
├── docs/
│   ├── dashboard.html        ← The dashboard (GitHub Pages)
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
└── CLAUDE.md                 ← AI agent instructions
```

---

## Tech Stack

| What | Why |
|------|-----|
| Python 3.13 | ETL scripting |
| DuckDB | Fast analytical queries without a server |
| pandas + openpyxl | Excel processing |
| pdfplumber | PDF table extraction |
| Plotly.js | Interactive charts |
| GitHub Pages | Free static hosting |
| Claude Code | AI agent that built the whole thing |

---

## Running It Yourself

```bash
# Install dependencies
pip install duckdb pandas openpyxl pdfplumber plotly

# Run the ETL pipeline (if you have the raw data files)
python scripts/merge_niv_sheets.py
python scripts/extract_refusal_data.py
python scripts/extract_refusal_grounds.py
python scripts/extract_consular_posts.py
python scripts/standardize_countries.py
python scripts/extract_h1b_lca_data.py --fy 2026 --quarter latest

# Generate the dashboard
python scripts/dashboard.py

# Run the local H-1B wage query interface
python scripts/wage_query_app.py

# Open docs/dashboard.html in your browser
```

The wage query interface runs locally at [http://localhost:8765](http://localhost:8765). It queries `h1b_public_wage_fact` with filters for employer, occupation, SOC, case number, state, city, wage level, salary band, plausible wages, and cap-season proxy rows.

## Postgres Export

DuckDB remains the local analytics engine, but the warehouse is now Postgres-ready:

```bash
# Generate database/postgres_schema.sql and CSV exports
python scripts/export_to_postgres.py --tables default --no-load

# Optional: load directly into Postgres when a DSN is available
POSTGRES_DSN="postgresql://user:password@localhost:5432/immigration" \
  python scripts/export_to_postgres.py --tables default
```

The export materializes `h1b_public_wage_fact`, a denormalized worksite-level wage table built for fast salary, employer, occupation, location, and future selection-odds analysis.

### H-1B Wage Intelligence Methodology

The wage section uses public DOL OFLC Labor Condition Application records. It is salary intelligence, not exact "picked winners" data: one LCA can cover multiple workers, public files exclude worker names, and LCA certification does not prove H-1B lottery selection or petition approval. The FY2027 cap-season view is a proxy built from certified new-employment LCAs with employment start dates near October 1, 2026.

---

*Built by [Sai Pranav Ongole](https://www.linkedin.com/in/pranavo/) — Part of the DataForge365 series*

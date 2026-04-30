# US Immigration Data Platform

Open-source analytics on US immigration data — 28 years of State Department visa records plus 5 quarters of H-1B wage disclosures, all queryable live in the browser. No login, no install.

**Built by [Pranav Ongole](https://www.pranavongole.com) — [LinkedIn](https://www.linkedin.com/in/pranavo/) · [GitHub](https://github.com/PranavOngole)**

---

## Live Dashboards

> Click any link below — everything runs in your browser, no setup required.

| | Dashboard | What It Shows |
|---|---|---|
| 🌐 | **[Visa Trends](https://pranavongole.github.io/Project-00/dashboard.html)** | 28 years of US visa issuances, refusal rates, and embassy workloads by country |
| 💼 | **[H-1B Wage Intelligence](https://pranavongole.github.io/Project-00/h1b_wages.html)** | DOL LCA salary analytics — wage levels, top employers, occupations, cap-season proxy |
| 🔎 | **[H-1B Live Query Tool](https://pranavongole.github.io/Project-00/h1b_query.html)** | Filter and query 763K+ LCA records across 5 quarters in real time — no SQL required |

Or start at the **[project landing page](https://pranavongole.github.io/Project-00/)**.

---

## What You Can Explore

**Visa Trends (FY1997–2024)**
- How US visa issuances crashed during COVID and what the recovery looked like
- Which countries get the most H-1B work visas — India gets nearly 5x more than China
- Where in the world US visas are processed — the busiest embassy is Monterrey, Mexico (681K visas in one year)
- Country-by-country B-visa refusal rates — some exceed 70%
- The legal reasons visas get denied — Section 214(b) alone accounts for 77% of all nonimmigrant denials

**H-1B Wage Intelligence (FY2025 Q1 – FY2026 Q1)**
- Median offered salary by employer, occupation, state, and wage level
- How much employers pay above the DOL prevailing wage floor
- Which companies file the most H-1B positions and what they offer
- Cap-season filing proxies for FY2027 lottery strategy

> **Important:** This data is DOL Labor Condition Application records — salary disclosures employers file *before* sponsoring H-1B workers. It is not lottery results. LCA certification does not mean the petition was approved or the lottery was won. One LCA can cover many workers. Use it for salary intelligence, not headcount.

---

## How It Works

```
US State Dept Excel/PDF files + DOL OFLC LCA workbooks
        |
6 Python ETL scripts (pandas, pdfplumber, DuckDB)
        |
DuckDB analytics database → 763K-row combined parquet (34MB, ZSTD)
        |
3 static HTML files → GitHub Pages
        |
DuckDB-WASM runs SQL queries live in your browser — no server needed
```

All three dashboards are fully static files hosted on GitHub Pages. The live query tool downloads the parquet file once and executes real SQL in-browser via WebAssembly.

---

## Data Sources

| Source | Coverage |
|--------|----------|
| NIV Detail Tables | Visa issuances by country + type — FY1997–2024, 199 countries, 90+ categories |
| NIV Workload by Category | Applications filed, approved, denied per visa type — FY2024 |
| B-Visa Adjusted Refusal Rates | Country-by-country denial rates — FY2024 |
| Table XIX — Ineligibility Grounds | Every legal reason a visa was denied with counts — FY2024 |
| Table IV — Visas by Issuing Office | Embassy/consulate processing volumes — FY2024 |
| DOL OFLC LCA Disclosure + Worksites | H-1B offered wages, employers, SOC, locations — FY2025 Q1–FY2026 Q1 |

---

## Tech Stack

| What | Why |
|------|-----|
| Python 3.13 | ETL scripting |
| DuckDB | Fast analytical queries without a server |
| DuckDB-WASM | Full SQL engine running in-browser via WebAssembly |
| Apache Arrow + Parquet | Columnar format for the browser data layer — 34MB serves 763K rows |
| pandas + openpyxl | Excel processing |
| pdfplumber | PDF table extraction |
| Plotly.js | Interactive charts |
| GitHub Pages | Free static hosting |
| Claude Code | AI agent that built the entire pipeline |

---

## Project Structure

```
US-Immigration-Data/
├── data/
│   ├── raw/                  ← Original government files (Excel + PDF)
│   │   └── dol_lca/          ← DOL OFLC LCA disclosure/worksite workbooks
│   ├── processed/            ← Cleaned CSVs (one per quarter)
│   └── wasm/
│       └── h1b_lca_combined.parquet  ← 34MB ZSTD, 763K rows, FY2025 Q1–FY2026 Q1
├── database/
│   ├── immigration.duckdb    ← Local analytics database
│   └── postgres_schema.sql   ← Postgres-ready schema
├── scripts/
│   ├── merge_niv_sheets.py          ← Excel → unified CSV
│   ├── extract_refusal_data.py      ← B-visa refusal PDF → CSV
│   ├── extract_refusal_grounds.py   ← Table XIX PDF → CSV
│   ├── extract_consular_posts.py    ← Table IV PDF → CSV
│   ├── extract_h1b_lca_data.py      ← DOL LCA workbooks → H-1B wage tables (one quarter)
│   ├── build_all_quarters.py        ← Multi-quarter ETL + combined parquet export
│   ├── export_to_postgres.py        ← DuckDB → Postgres schema/CSV export
│   ├── standardize_countries.py     ← Country name mapping
│   └── dashboard.py                 ← Visa dashboard generator
├── dashboard.html            ← Visa trends (GitHub Pages)
├── h1b_wages.html            ← H-1B wage analytics (GitHub Pages)
├── h1b_query.html            ← Live DuckDB-WASM query tool (GitHub Pages)
├── index.html                ← Landing page
└── .nojekyll                 ← Bypasses Jekyll for GitHub Pages
```

---

## Running It Yourself

The fastest way is to just open the live links above. Everything works in your browser with no setup.

To run the pipeline locally (requires the raw government data files from DOL/State Dept):

```bash
pip install duckdb pandas openpyxl pdfplumber plotly

# Visa dashboard ETL
python scripts/merge_niv_sheets.py
python scripts/extract_refusal_data.py
python scripts/extract_refusal_grounds.py
python scripts/extract_consular_posts.py
python scripts/standardize_countries.py
python scripts/dashboard.py

# H-1B multi-quarter build (place DOL xlsx files in data/raw/dol_lca/ first)
python scripts/build_all_quarters.py

# Adding a new quarter when DOL publishes it:
# 1. Download LCA_Disclosure_Data_FY{year}_Q{n}.xlsx + LCA_Worksites_FY{year}_Q{n}.xlsx
# 2. Drop both in data/raw/dol_lca/
# 3. Run: python scripts/build_all_quarters.py
# 4. Commit and push data/wasm/h1b_lca_combined.parquet
```

---

*Built by [Pranav Ongole](https://www.pranavongole.com) — [pranavongole.com](https://www.pranavongole.com) · [LinkedIn](https://www.linkedin.com/in/pranavo/) · Part of the DataForge365 series*

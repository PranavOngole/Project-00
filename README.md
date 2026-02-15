# US Immigration Visa Dashboard

Every year, millions of people apply for U.S. visas. Some get approved. Many don't. The data behind all of this is published by the U.S. Department of State — but it's scattered across Excel files, PDFs, and reports that nobody outside a government office would ever read.

This project takes 28 years of that data (FY1997 through FY2024), cleans it up, and turns it into something you can actually explore.

**[View the Live Dashboard](https://pranavongole.github.io/Project-00/dashboard.html)**

---

## What You Can See

- **How many visas the U.S. issues each year** — and how that number crashed during COVID and recovered after
- **Which countries get the most H-1B work visas** — India gets nearly 5x more than China, and the gap keeps growing
- **Where in the world U.S. visas are processed** — the busiest embassy isn't in New Delhi or Beijing, it's in Monterrey, Mexico (681,000 visas in one year)
- **What percentage of applicants get denied, by country** — some countries have refusal rates above 70%
- **The actual legal reasons visas get denied** — Section 214(b) alone accounts for 77% of all nonimmigrant visa denials. That's 3 million people told "you didn't prove you'll go home"
- **How different visa types compare** — H-1B (work), F-1 (student), B-1/2 (tourist), L-1 (transfer), and dozens more

---

## Where the Data Comes From

All data is from the U.S. Department of State, publicly available at [travel.state.gov](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics.html):

| Source | What's In It |
|--------|-------------|
| NIV Detail Tables (FY1997–2024) | Visa issuances by country and type — 28 years, 199 countries, 90+ visa categories |
| NIV Workload by Category (FY2024) | How many applications were filed, approved, and denied per visa type |
| B-Visa Adjusted Refusal Rates (FY2024) | Country-by-country denial rates for tourist/business visas |
| Table XIX — Ineligibility Grounds (FY2024) | Every legal reason a visa was denied, with counts |
| Table IV — Visas by Issuing Office (FY2024) | Which embassies and consulates processed the most visas |

---

## How It Works

Five raw files go in. Five Python scripts clean and transform them. Eight database tables come out. One script generates the entire dashboard as a single HTML file.

```
5 source files (Excel + PDF)
        |
5 ETL scripts (Python + pdfplumber)
        |
8 DuckDB tables (~6,100 rows)
        |
1 dashboard generator
        |
1 HTML file (760 KB) → GitHub Pages
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

An AI agent (Claude Code) wrote every script, built the dashboard, extracted the PDFs, and documented everything. The entire pipeline — from raw Excel to live dashboard — was built in a single working session.

---

## Project Structure

```
US-Immigration-Data/
├── data/
│   ├── raw/                  ← Original government files (Excel + PDF)
│   └── processed/            ← Cleaned CSVs (5 files)
├── database/
│   └── immigration.duckdb    ← Analytics database (8 tables)
├── docs/
│   ├── dashboard.html        ← The dashboard (GitHub Pages)
│   ├── BRD.md                ← Business Requirements Document
│   └── session_notes.md      ← Development log
├── scripts/
│   ├── merge_niv_sheets.py          ← Excel → unified CSV
│   ├── extract_refusal_data.py      ← B-visa refusal PDF → CSV
│   ├── extract_refusal_grounds.py   ← Table XIX PDF → CSV
│   ├── extract_consular_posts.py    ← Table IV PDF → CSV
│   ├── standardize_countries.py     ← Country name mapping
│   └── dashboard.py                 ← Dashboard generator
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

# Generate the dashboard
python scripts/dashboard.py

# Open docs/dashboard.html in your browser
```

---

*Built by [Sai Pranav Ongole](https://www.linkedin.com/in/pranavo/) — Part of the DataForge365 series*

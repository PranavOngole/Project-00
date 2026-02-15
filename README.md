# Project-00: US Immigration Data Platform

> Part of the **POV (Pranav Ongole's Vision)** series — AI agent-driven data platforms.

**One AI agent. 27 years of messy government data. Zero manual wrangling.**

---

## What This Is

A fully autonomous data pipeline built using Claude Code (AI agent) that ingests, cleans, and visualizes US nonimmigrant visa data published by the State Department — FY1997 through FY2024.

No manual Excel work. No copy-paste. The agent did it.

---

## What the Agent Did

```
Input:   28 inconsistent Excel sheets from travel.state.gov
Output:  Clean database + interactive dashboard

✓ Diagnosed column schema changes across 27 years automatically
✓ Standardized 96 visa type names (H-1B vs H1B vs H-1B, etc.)
✓ Filtered out subtotals, region headers, and junk rows
✓ Merged 5,564 rows × 98 columns across 215 countries into DuckDB
✓ Built interactive Plotly dashboard with visa type filters
✓ Wrote its own session documentation

Time: ~2 hours. Manual estimate: ~2 days.
```

---

## Key Insight

India issued **1.37M nonimmigrant visas in FY2024** — including **150,647 H-1B visas**, nearly **5x China's 31,735**.

---

## Data Source

US Department of State — NIV Detail Tables FY1997–2024  
[travel.state.gov](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-statistics/nonimmigrant-visa-statistics.html)  
Licensed under Creative Commons CC BY 4.0

---

## Stack

| Layer | Tool |
|-------|------|
| AI Agent | Claude Code (Anthropic) |
| Database | DuckDB |
| Processing | Python · pandas · openpyxl |
| Visualization | Plotly |
| Version Control | GitHub |

---

## Project Structure

```
US-Immigration-Data/
├── data/
│   ├── raw/          ← Original State Dept Excel files
│   └── processed/    ← Cleaned CSVs
├── database/         ← DuckDB file
├── docs/
│   ├── dashboard.html      ← Interactive dashboard
│   ├── data_dictionary.md  ← Schema documentation
│   └── session_notes.md    ← Agent work log
├── scripts/
│   ├── merge_niv_sheets.py ← ETL script (agent-written)
│   └── dashboard.py        ← Dashboard generator (agent-written)
└── CLAUDE.md         ← Agent instructions
```

---

## This Is Project-00

The immigration data is the test case. The real product being built here is the **AI agent workflow system** — a proof of concept that one agent can autonomously handle what a junior data team takes days to do.

Projects 01 and 02 coming soon under the **POV** brand.

---

*Built by [Sai Pranav Ongole](https://www.linkedin.com/in/pranavo/) · Powered by Claude Code*

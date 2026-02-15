# Business Requirements Document (BRD)
## US Immigration Visa Data Platform — Project-00

**Author:** Sai Pranav Ongole
**Date:** February 15, 2026
**Version:** 2.0
**Status:** Active Development

---

## 1. Executive Summary

This project transforms 28 years of raw U.S. government immigration data into a single interactive dashboard. The data comes from the U.S. Department of State in five separate source files — messy Excel workbooks, multi-page PDFs with inconsistent formatting, and tables that use different country names for the same nations.

The platform ingests, cleans, standardizes, and joins all of this into a unified analytics layer (DuckDB) and generates a self-contained HTML dashboard that runs entirely in the browser with zero server dependencies.

**Scale:** 5 source files → 5 ETL scripts → 8 database tables → 6,000+ rows → 1 dashboard
**Time span:** FY1997 through FY2024 (28 fiscal years)
**Coverage:** 199 countries, 90+ visa categories, 220 consular posts, 79 legal grounds for denial

---

## 2. Problem Statement

U.S. immigration visa data is publicly available but practically inaccessible:

- **Fragmented across formats:** Excel workbooks with 28 sheets (one per fiscal year), PDFs with tables that can't be copy-pasted, and supplementary reports published separately
- **Inconsistent schemas:** Column names change between fiscal years (e.g., "H-1B" vs "H1B" vs "H-1B1")
- **No cross-referencing:** The State Department publishes issuances, refusal rates, ineligibility grounds, and consular post data in separate documents with no common identifiers
- **Country name mismatches:** "Korea, South" in one table is "South Korea" in another — 34 such mismatches exist across source files
- **No trend analysis:** Data is published per-year with no multi-year aggregation or visualization

There is no single place where someone can see how many H-1B visas India received in 2005 vs 2024, or what percentage of Nigerian B-visa applicants are denied, or which embassy processes the most visas globally.

---

## 3. Business Objectives

| # | Objective | Metric |
|---|-----------|--------|
| 1 | Consolidate all available State Dept visa data into one queryable database | 8 tables, 6,000+ rows, 100% coverage of published source data |
| 2 | Enable trend analysis across 28 fiscal years by country and visa type | Interactive time-series charts with country/visa filters |
| 3 | Surface refusal rate patterns by nationality | Per-country B-visa refusal rates with estimated denied counts |
| 4 | Identify the statutory grounds for visa denial and their relative frequency | Ranked INA section analysis with finding/overcome breakdowns |
| 5 | Map the global consular network by volume | Embassy/consulate rankings by region and visa type |
| 6 | Deliver as a zero-dependency static site deployable to GitHub Pages | Single HTML file, all data embedded as JSON, no backend required |

---

## 4. Data Sources

### 4.1 Source Files

| File | Format | Description | Rows/Pages |
|------|--------|-------------|------------|
| `FYs97-24_NIVDetailTable.xlsx` | Excel (.xlsx) | 28 sheets — one per fiscal year. Each contains nonimmigrant visa issuances by country and visa type. Column schemas change between years. | ~200 rows × 90+ cols per sheet |
| `FY24NIVDetailTable.xlsx` | Excel (.xlsx) | FY2024 standalone detail table | ~200 rows × 90+ cols |
| `data/raw/pdf/` (B-visa refusal) | PDF | Adjusted B-visa refusal rates by nationality, FY2024. Published as "Adjusted Refusal Rate — B-Visas Only" | 7 pages, 199 countries |
| `data/raw/annual_report/table_xix.pdf` | PDF | Table XIX from State Dept Annual Report: Visa ineligibility grounds with IV/NIV findings and waivers | 3 pages, 79 INA sections |
| `data/raw/annual_report/table_iv.pdf` | PDF | Table IV from State Dept Annual Report: Summary of visas issued by issuing office (consular post) | 6 pages, 220 posts |

### 4.2 Data Quality Challenges

| Challenge | Impact | Resolution |
|-----------|--------|------------|
| 96 variant visa type column names across 28 years | Columns don't align between sheets — can't stack data | Automated column name standardization mapping |
| Country names differ between sources | JOINs fail silently — data appears to not exist | `country_mapping` bridge table with 34 manual mappings |
| PDF tables can't be extracted with standard tools | pdfplumber table detection returns empty for some PDFs | Fallback to text extraction + regex parsing per-line |
| Subtotal and region header rows mixed with data | Aggregations double-count if not filtered | Row classification logic to identify and flag totals |
| State Dept doesn't publish per-country refusal counts by visa type | Can't directly answer "how many H-1B visas did Nigeria get denied?" | Derived estimation: `est_refused = issued × rate / (1 - rate)` using B-visa refusal rate as proxy |
| Grand Total row has `ina_section = "Total Grounds"` not `"TOTAL"` | Validation sums appear doubled (7.8M vs expected 3.9M) | Post-extraction label correction |

---

## 5. ETL Pipeline

### 5.1 Pipeline Architecture

```
Raw Sources (5 files)
    │
    ▼
ETL Scripts (5 Python scripts)
    │
    ▼
DuckDB (8 tables, ~6,100 total rows)
    │
    ▼
dashboard.py (Python generator)
    │
    ▼
dashboard.html (760 KB static file → GitHub Pages)
```

### 5.2 ETL Scripts

| Script | Input | Output | Key Logic |
|--------|-------|--------|-----------|
| `merge_niv_sheets.py` | 28 Excel sheets | `visa_issuances` (5,564 rows) | Reads each sheet, standardizes 96 column names, filters subtotals/headers, stacks all years |
| `extract_refusal_data.py` | B-visa refusal PDF | `b_visa_refusals` (199 rows) | pdfplumber table extraction → rate parsing → percentage cleaning |
| `standardize_countries.py` | All tables | `country_mapping` (34 rows) + derived tables | Identifies name mismatches → creates bridge table → generates `b_visa_workload_by_country` and `niv_workload_by_country` |
| `extract_refusal_grounds.py` | Table XIX PDF | `visa_ineligibility_grounds` (79 rows) | Text extraction + regex: `^(\S+(?:\s+\S+)?)\s+(.+?)\s+([\d,]+\|-)\s+([\d,]+\|-)\s+([\d,]+\|-)\s+([\d,]+\|-)$` |
| `extract_consular_posts.py` | Table IV PDF | `visas_by_consular_post` (227 rows) | Text extraction with region-tracking state machine, handles multi-line entries and subtotals |

### 5.3 Database Schema

**Engine:** DuckDB (embedded OLAP database)
**File:** `database/immigration.duckdb`

| Table | Rows | Columns | Description | Join Keys |
|-------|------|---------|-------------|-----------|
| `visa_issuances` | 5,564 | 98 | Core fact table. 28 FYs × ~199 countries. One column per visa type. | `country`, `fiscal_year` |
| `niv_workload` | 81 | 5 | FY2024 applications, issued, refused by visa category | `visa_category` |
| `b_visa_refusals` | 199 | 4 | Adjusted B-visa refusal rates by nationality | `nationality` → `country_mapping` |
| `country_mapping` | 34 | 2 | Bridge: maps variant country names between tables | `source_name` ↔ `standard_name` |
| `b_visa_workload_by_country` | ~199 | 5 | Derived: estimated B-visa applications, issued, refused per country | `country` |
| `niv_workload_by_country` | ~199 | 5 | Derived: national totals disaggregated by country proportion | `country` |
| `visa_ineligibility_grounds` | 79 | 7 | INA statutory grounds with IV/NIV finding & overcome counts | `ina_section` |
| `visas_by_consular_post` | 227 | 7 | Issuing office with IV/NIV/BCC counts by region | `issuing_office`, `region` |

### 5.4 Derived Data Calculations

**Estimated B-Visa Refusals by Country:**
```
est_refused = b_visa_issued × (refusal_rate / (1 - refusal_rate))
est_applications = b_visa_issued + est_refused
```

**Country-Level NIV Workload Disaggregation:**
```
country_share = country_issued / global_issued  (from visa_issuances)
country_applications = global_applications × country_share  (from niv_workload)
```

**Country × Visa Type Estimated Refusal Rate:**
```
est_rate = global_visa_type_refusal_rate × (country_b_rate / global_b_rate)
```
This uses B-visa refusal rate as a country-level difficulty proxy scaled against global per-visa-type refusal rates.

---

## 6. Dashboard Requirements

### 6.1 Functional Requirements

| # | Requirement | Implementation |
|---|-------------|----------------|
| FR-1 | Display aggregate statistics (all-time issued, FY2024 apps/issued/refused, country count) | Hero stat cards with formatted numbers |
| FR-2 | Interactive 28-year timeline with visa type breakdown | Client-side Plotly.js chart with category dropdown (Total, H-1B, F-1, B-1,2, L-1) + country overlay |
| FR-3 | FY2024 top-20 countries by visa type with log-normalized coloring | Client-side bar chart with visa type selector, JS-computed color gradient |
| FR-4 | Country explorer with multi-country comparison | Visa type selector + multi-select country dropdown → stacked area chart |
| FR-5 | H-1B historical trend for top 10 countries | Server-side Plotly chart with country filter dropdown |
| FR-6 | India vs China H-1B head-to-head | Filled area comparison chart |
| FR-7 | FY2024 NIV workload by visa category (issued vs refused) | Stacked horizontal bar chart |
| FR-8 | B-visa estimated applications by country | Stacked bar: issued vs estimated refused |
| FR-9 | B-visa refusal rates with 3 view modes | Client-side: Top 20 Highest, Top 15 Lowest, Search by Country |
| FR-10 | Visa ineligibility grounds analysis | Client-side: Top NIV, Top IV, Overcome Rate views |
| FR-11 | Busiest consular posts ranking | Client-side: Top 25 by NIV, by IV, or by region |
| FR-12 | Country × Visa Type estimated refusal heatmap | Color-coded HTML table with green→yellow→red gradient |
| FR-13 | Data model and pipeline architecture diagram | CSS pipeline visualization with 4 layers + relationship cards |
| FR-14 | Methodology and data source documentation | In-dashboard knowledge cards |

### 6.2 Non-Functional Requirements

| # | Requirement | Specification |
|---|-------------|---------------|
| NFR-1 | Zero server dependencies | Static HTML, all data embedded as JSON, hosted on GitHub Pages |
| NFR-2 | File size under 1 MB | Currently 760 KB — all charts, data, and styles in one file |
| NFR-3 | Mobile responsive | CSS breakpoints at 768px with column stacking |
| NFR-4 | Dark theme | Professional dark palette with subtle grid background |
| NFR-5 | Load time under 3 seconds | Only external dependency: Plotly.js CDN (~3.5 MB gzipped) |
| NFR-6 | Accessible color contrast | Minimum 4.5:1 contrast ratio on all text elements |

---

## 7. Key Findings

These are the analytical insights surfaced by the platform:

1. **India dominates H-1B:** 150,647 H-1B visas in FY2024 — nearly 5x China's 31,735. This gap has been widening since 2015.

2. **COVID cratered visa issuances:** FY2020 saw a ~55% drop from FY2019 levels. Recovery didn't reach pre-pandemic levels until FY2023.

3. **214(b) is the denial machine:** Section 214(b) ("failure to establish entitlement to nonimmigrant status") accounts for 77.4% of ALL NIV refusal findings — 3,010,544 out of 3,891,139.

4. **221(g) is the second killer:** "Application does not comply with INA provisions" — 809,735 NIV findings, but 672,461 were eventually overcome (83% overcome rate). This is essentially a "your paperwork is wrong, try again."

5. **Monterrey, Mexico is the busiest consular post on Earth** for NIV processing: 681,000 visas issued in FY2024 — more than some entire countries.

6. **Refusal rates vary wildly by nationality:** Some countries have B-visa refusal rates above 70%, while others are under 5%. This data is public but rarely visualized.

---

## 8. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| AI Agent | Claude Code (Anthropic) | Autonomous development — wrote all ETL scripts, dashboard code, and documentation |
| Database | DuckDB | Embedded OLAP engine — fast analytical queries without a server |
| ETL | Python 3.13 + pandas + openpyxl | Excel file processing and data transformation |
| PDF Extraction | pdfplumber | Table and text extraction from government PDFs |
| Visualization | Plotly.js | Interactive charts (both server-side generated and client-side rendered) |
| Hosting | GitHub Pages | Static site hosting from `/docs` directory |
| Version Control | Git + GitHub | Source control and collaboration |

---

## 9. Future Scope

| Phase | Data Source | What It Adds |
|-------|------------|-------------|
| Phase 2 | CBP Public Data Portal | Port of entry encounters, inadmissibility by nationality and field office |
| Phase 2 | Trade.gov Historical I-94 | Decades of arrival data by country, port, visa type, and travel mode |
| Phase 2 | DHS OHSS NIV Admissions | Annual flow data by class of admission back to FY1981 |
| Phase 3 | TRAC Reports (FOIA) | CBP inadmissibility by specific INA ground, port, and nationality |
| Phase 3 | State Dept Monthly NIV | Monthly granularity for seasonal trend analysis |

---

## 10. Risks and Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| State Dept changes Excel format in future years | ETL pipeline breaks on new data | Column standardization mapping is extensible; add new mappings as needed |
| PDF table layout changes between annual reports | Extraction regex fails | Each PDF script is standalone; can be updated independently |
| Derived refusal estimates may not match actual refusal counts | Users may cite estimated numbers as fact | Clear "Estimated" labels throughout dashboard; methodology section explains derivation |
| B-visa refusal rate as proxy for other visa types | Cross-visa-type estimation has unknown accuracy | Labeled as "estimated" with explicit methodology disclosure |
| GitHub Pages has 100 MB site size limit | Dashboard can't grow indefinitely | Current size is 760 KB — substantial headroom |

---

*Document maintained by Sai Pranav Ongole | Last updated: February 15, 2026*

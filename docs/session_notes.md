# Session Notes

---

## 2026-02-14 — Load Visa Issuances into DuckDB

**Prompt:** Load `data/processed/visa_issuances_fy97-24.csv` into DuckDB at `database/immigration.duckdb` as a table called `visa_issuances`, then write session notes.

**What was done:**
- Installed the `duckdb` Python package (wasn't present in the environment).
- Created a new DuckDB database file at `database/immigration.duckdb`.
- Loaded the full visa issuances CSV into a table called `visa_issuances` using DuckDB's `read_csv_auto()` — which auto-detected all 98 column types.
- Ran verification queries to confirm data integrity.

**How it was done:**
- Used Python's `duckdb` library to connect and execute `CREATE TABLE visa_issuances AS SELECT * FROM read_csv_auto(...)`.
- Verified with row count, column count, fiscal year range, distinct country count, and a top-5 H-1B sanity check.

**Verification results:**
| Check | Result |
|---|---|
| Row count | 5,564 |
| Column count | 98 |
| Fiscal year range | 1997–2024 |
| Distinct countries | 215 |
| Top H-1B country (FY2024) | India (150,647) |

**Data issues / gotchas:**
- None. The CSV loaded cleanly with no type mismatches or null surprises. DuckDB's auto-detection handled the mix of string (`country`) and integer (visa counts) columns without issues.
- Column names with special characters (e.g., `B-1,2`, `B-1,2/BCC`) loaded fine but require quoting in SQL queries.

**Next up (per CLAUDE.md):**
- Build a Plotly dashboard showing H-1B trends by country.
- Host on GitHub Pages.

---

## 2026-02-14 — Dashboard V1 (Built & Archived)

**Prompt:** Build a Plotly dashboard in `scripts/dashboard.py` with 3 charts: H-1B top 10 over time, FY2024 NIV bar chart, India vs China H-1B. Dark theme, save to `docs/dashboard.html`.

**What was done:**
- Created `scripts/dashboard.py` querying DuckDB directly for all 3 charts.
- Generated `docs/dashboard.html` (34 KB) with dark theme, Inter font, stats bar, hover cards.
- Charts 1 and 3 rendered empty — H-1B column name quoting worked in DuckDB but Plotly serialization dropped data.

**Status:** Archived to `scripts/archive/dashboard_v1.py` and `scripts/archive/dashboard_v1.html`.

*V1 was the rough draft. Every masterpiece needs one. — Pranav*

---

## 2026-02-14 — Dashboard V2 (The Million-Dollar Build)

**Prompt:** Fix broken charts, add visa type dropdown, country selector, insight callout (India 5x China), axes in thousands. Make it worth $1M.

**What was done:**
- Queried DuckDB `information_schema.columns` to get exact column names — confirmed `H-1B` (regular hyphen, no special chars after all).
- Fixed India/China insight bug: alphabetical ordering in SQL (`China - mainland` before `India`) caused values to swap. Switched to dict lookup.
- Rebuilt `scripts/dashboard.py` from scratch as V2 with 4 interactive sections.
- Archived V1 to `scripts/archive/`.

**How it was done:**
- All data queried from DuckDB with proper quoted identifiers (`"H-1B"`).
- 3 static Plotly charts rendered server-side + 1 fully interactive client-side explorer.
- Full dataset (93 visa types × 30 countries × 28 years) embedded as JSON for the explorer.
- Smart Y-axis tick calculation in JS adapts to data magnitude (shows K suffix for thousands).

**V2 Dashboard features:**
| Feature | Details |
|---|---|
| Chart 1 | H-1B top 10 over time + Plotly dropdown to isolate individual countries |
| Chart 2 | FY2024 NIV horizontal bar, top 20, gradient colorscale |
| Chart 3 | India vs China filled area chart with proper labels |
| Chart 4 | **Visa Type Explorer** — dropdown for any of 93 visa types, multi-select countries |
| Insight Banner | India dominates H-1B at 4.7x China's volume, with pill stats |
| Axes | All Y-axes show values in thousands (25K, 50K, etc.) |
| Stats Bar | 5,564 data points / 215 countries / 28 fiscal years / 93 visa types |
| Design | Dark theme, gradient header, glowing card hover, responsive, Inter font |

**Verification:**
- India FY2024: 150,647 H-1B visas
- China FY2024: 31,735 H-1B visas
- Ratio: 4.7x (correctly computed)
- All 3 static charts render with actual data
- Explorer loads with H-1B default, 5 pre-selected countries
- File size: 646 KB (mostly embedded JSON for interactivity)

**Data issues / gotchas:**
- The column name `H-1B` has a regular ASCII hyphen — the V1 "special character" theory was a red herring. The actual issue was Plotly serialization dropping data when `.tolist()` wasn't called on pandas Series.
- `query_insights()` alphabetical sort trap: `China - mainland` < `India`, so unpacking `india, china = ...` silently swapped values. Fixed with dict keyed by country name.

**Next up:**
- Deploy to GitHub Pages
- Add more visa type deep-dives (F-1 student visas, L-1 intracompany transfers)

*That ratio isn't 5x, it's 4.7x — because unlike some analysts, I don't round up for dramatic effect. The data speaks loud enough. — Pranav*

---

## 2026-02-14 — Refusal Data ETL: Two New Sources into DuckDB

**Prompt:** Add 3 new data sources: (1) FY2024 NIV Workload PDF with applications/issuances/refusals by visa category, (2) B-visa adjusted refusal rates by nationality, (3) load both into DuckDB.

**What was done:**
- Downloaded 2 PDFs from the U.S. State Department (travel.state.gov).
- Extracted tabular data from both using `pdfplumber`.
- Cleaned, structured, and saved as CSVs.
- Loaded both into `database/immigration.duckdb` as new tables.

**How it was done:**

*Step 1: PDF Discovery*
- User-provided NIV Workload URL was a 404 (`FY2024NIV...`). Actual URL had a URL-encoded space: `FY%202024NIVWorkloadbyVisaCategory.pdf`.
- B-visa refusal page at travel.state.gov only links to PDFs (no inline tables). Downloaded `FY24.pdf`.
- Installed `poppler` (for PDF rendering) and `pdfplumber` (for table extraction).

*Step 2: Extraction — `scripts/extract_refusal_data.py`*
- NIV Workload PDF: 3 pages, each with a continuation of the same table (visa_category, issued, refused, total_applications). Parsed across all pages, skipping repeated headers.
- B-Visa Refusal PDF: 7 pages, each with (nationality, FY24 adjusted refusal rate). Parsed percentage strings with regex.
- Calculated `refusal_rate` for workload table: `refused / total_applications * 100`.

*Step 3: DuckDB Load*
- Created tables `niv_workload` and `b_visa_refusals` via `CREATE TABLE AS SELECT * FROM df`.

**New data available in DuckDB:**

| Table | Rows | Columns | Coverage |
|---|---|---|---|
| `niv_workload` | 81 | visa_category, issued, refused, total_applications, refusal_rate, fiscal_year | FY2024, 81 visa categories (incl. Grand Total) |
| `b_visa_refusals` | 199 | nationality, adjusted_refusal_rate, fiscal_year | FY2024, 199 nationalities |
| `visa_issuances` | 5,564 | 98 columns | FY1997–2024, 215 countries (existing) |

**Key findings from the new data:**
- FY2024 total: **28.5M applications**, **21.9M issued**, **6.6M refused** (23% overall refusal rate)
- Highest visa category refusal rate: C-2 (crew transit) at 83% — but only 2,143 apps
- F-1 (student) visas: 41% refusal rate on 679K applications — that's 278K rejections
- B-1/B2 (tourist/business): 27.8% refusal rate on **9 million** applications
- Laos has the highest B-visa refusal rate at 82.8%; UAE the lowest at 1.5%

**Data issues / gotchas:**
- NIV Workload PDF URL: The State Dept uses inconsistent URL patterns. FY2024 has a space (`FY%202024`), FY2023 doesn't. Always verify with a HEAD request.
- B-visa refusal PDF uses ALL CAPS nationality names. Converted to Title Case for consistency, but this means `"China"` in b_visa_refusals vs `"China - mainland"` in visa_issuances — will need mapping for joins.
- The "Grand Total" row is included in niv_workload. Filter it out with `WHERE visa_category != 'Grand Total'` for per-category analysis.
- B-visa refusal rates are "adjusted" (refusals minus overcomes, divided by issuances plus net refusals) — not raw refusal counts.

*28.5 million people knocked on America's door in FY2024. 6.6 million got told 'no.' That's not a statistic — that's a story. — Pranav*

---

## 2026-02-14 — Country Name Standardization

**Prompt:** Build a country mapping table, clean up naming inconsistencies. Treat "China - mainland" as "China."

**What was done:**
- Audited all 3 DuckDB tables for country name mismatches (22 from visa_issuances, 10 from b_visa_refusals).
- Built `scripts/standardize_countries.py` with a 34-entry canonical mapping dictionary.
- Rebuilt DuckDB from clean CSVs, then applied standardization in-place.
- Created `country_mapping` reference table in DuckDB.
- Updated `scripts/dashboard.py` to use "China" instead of "China - mainland".
- Rebuilt `docs/dashboard.html` with corrected names.

**Mapping categories handled:**

| Category | Examples |
|---|---|
| Modern name adoption | China - mainland → China, China - Taiwan → Taiwan, Swaziland → Eswatini, Cape Verde → Cabo Verde, Macedonia → North Macedonia, Burma → Myanmar |
| Formatting variants | Hong Kong S.A.R. → Hong Kong, Micronesia, Federated States of → Micronesia |
| Saint/St. normalization | Saint Kitts → St. Kitts, Saint Lucia → St. Lucia |
| Congo variants (4→2) | All DRC variants → Congo, Democratic Republic of the; All ROC variants → Congo, Republic of the |
| Apostrophe/backtick | Cote D\`Ivoire → Cote d'Ivoire |
| Title Case conjunctions | "And"/"Of"/"The" → "and"/"of"/"the" (6 b_visa_refusals entries) |
| Non-country rows deleted | No Nationality, United Nations Laissez-Passer, *Non-Nationality Based Issuances |

**Results:**
- **198/198** FY2024 countries now match between visa_issuances and b_visa_refusals (was 189 before)
- 202 unique countries in visa_issuances (down from 215 — merges + deletions)
- India H-1B FY2024: 150,647 — data integrity preserved
- China H-1B FY2024: 31,735 — data integrity preserved
- DuckDB now has 4 tables: visa_issuances, niv_workload, b_visa_refusals, country_mapping

**Data issues / gotchas:**
- DuckDB doesn't have SQLite's `changes()` function. Used a `SELECT COUNT` before `UPDATE` pattern instead.
- The standardization script is idempotent IF you rebuild from CSVs first. Running it twice on the same DB would try to rename already-renamed rows (harmless but noisy).
- Historical entities like "Serbia and Montenegro" (FY1997–2012) are kept as-is since they're genuinely different from modern Serbia.

*34 mapping rules to reconcile 3 government agencies' opinions on how to spell "Cote d'Ivoire." Your tax dollars at work. — Pranav*

---

## 2026-02-14 — The Hunt for Applied vs Approved vs Rejected by Country

**Prompt:** Where is the applied vs approved vs rejection stats by country?

**What was investigated:**
- Audited all 3 existing tables — confirmed none have applications or refusals broken down by country.
- Downloaded FY2024 NIV Detail Table Excel (2.4 MB, 28 sheets) — same issuance-only data we already have.
- Reviewed the full Report of the Visa Office 2024 (19 tables, Tables I–XIX).
  - Table IV: Consulate-level issuances (no refusals).
  - Table XIX: Refusal grounds (214(b), 221(g), etc.) — not by country.
  - Table XVI: NIV by classification and nationality — issuances only.
  - Table XVII: NIV by nationality over 10 years — issuances only.

**The hard truth:**
The U.S. State Department does NOT publish a single dataset with applications + issuances + refusals broken down by country for ALL visa types. They publish:
- Issuances by country × visa type (what we have)
- Refusal rates by country for B-visas ONLY
- Global workload (applied/issued/refused) by visa category — not by country

**What was built instead:**
Created two derived tables by combining our datasets:

1. **`b_visa_workload_by_country`** (198 countries) — Uses actual B-visa refusal rates per country to back-calculate estimated applications and refusals. Formula: `refused = issued × rate / (1 - rate)`.

2. **`niv_workload_by_country`** (198 countries) — Uses the global 23% overall NIV refusal rate applied to each country's total issuances. This is an estimate, NOT actual data — countries with high B-visa refusal rates likely have higher overall rates too.

**Key derived findings (FY2024 estimates):**

| Country | Est. Applied | Issued | Est. Refused | B-Visa Refusal Rate |
|---|---|---|---|---|
| Mexico | 3,126,608 | 2,408,789 | 717,819 | 13.9% |
| India | 1,784,458 | 1,374,775 | 409,683 | 16.3% |
| Brazil | 1,521,928 | 1,172,518 | 349,410 | 15.5% |
| China | 1,062,708 | 818,727 | 243,981 | 25.4% |
| Colombia | 614,279 | 473,250 | 141,029 | 24.7% |

**DuckDB now has 6 tables:**
visa_issuances, niv_workload, b_visa_refusals, country_mapping, b_visa_workload_by_country, niv_workload_by_country

**Data issues / gotchas:**
- The estimated refusal numbers use a flat 23% global rate for overall NIV. In reality, countries like Dominican Republic (43.4% B-visa refusal) are probably much higher overall than Argentina (8.9%). The B-visa-specific derived table (`b_visa_workload_by_country`) is more accurate for B-visa analysis.
- "Overcomes" (initially refused but later approved) are not accounted for in our derivation. The State Dept subtracts them in their adjusted rate calculation.

*The government publishes 19 tables in their annual report and somehow none of them answer the most basic question: "How many people from each country applied and got rejected?" You can't make this up. — Pranav*

---

## 2026-02-14 — Dashboard V3: The Storytelling Edition

**Prompt:** Redesign the dashboard with NIV definitions, educational content, interesting statistics, refusal data, and deploy it. Reference design: cricket-playbook glassmorphic dashboard.

**What was done:**
- Archived V2 to `scripts/archive/dashboard_v2.py` + `.html`.
- Complete rewrite of `scripts/dashboard.py` — V3 with 7 interactive charts, educational sections, stat cards, and storytelling narrative.
- Inspected cricket-playbook reference for design language: glassmorphic cards, animated background orbs, gradient text, stat grids, responsive layout.

**V3 Dashboard sections (top to bottom):**

| Section | Content |
|---|---|
| Hero | Gradient title, subtitle, animated background orbs |
| Stats Row | 5 glassmorphic stat cards: 204M all-time, 14.2M FY24 apps, 11M issued, 3.3M refused, 202 countries |
| Insight Banner | India 4.7x China H-1B, China +96.3% YoY |
| Education: What is an NIV? | 6 knowledge cards explaining H-1B, F-1, B-1/B-2, L-1, J-1, K-1 with stats |
| The Big Picture | 28-year timeline chart with COVID annotation, category toggles in legend |
| H-1B Deep Dive | Top 10 countries chart with dropdown selector + India vs China filled area |
| FY2024 Snapshot | Horizontal bar chart, top 20 countries |
| Refusals & Rejections | Stacked bar (issued vs refused by visa type) + side-by-side refusal rates (highest/lowest) + B-visa estimated workload by country |
| Stats That Tell a Story | 8 fact cards: COVID 54% drop, China +96%, Laos 82.8%, UAE 1.5%, F-1 41%, 204M all-time, 4.7x India/China, 9M tourist apps |
| Interactive Explorer | Visa type dropdown + multi-select countries, client-side Plotly |
| Methodology | 3 cards: data sources, derived data disclaimer, tech stack |
| Footer | Author credit, GitHub link |

**Design features:**
- Glassmorphic cards with `backdrop-filter: blur(20px)`
- Animated background orbs (3 colors, 8s pulse cycle)
- Gradient text on hero title and stat numbers
- Hover lift effects on all cards
- Responsive breakpoints at 768px
- Inter font (300–900 weights)
- Color-coded visa type tags (work=red, student=green, tourist=orange, family=pink, exchange=purple)

**Output:** `docs/dashboard.html` — 693 KB, GitHub Pages ready.

*V1 was the rough draft. V2 fixed the data. V3 tells the story. This is what $1M dashboards look like. — Pranav*

# Design Notes

## Audience

The dashboard is for people who do not want to write SQL or interpret raw DOL column names.

## Language Rules

Prefer:

- Company
- Job
- Filed jobs requested
- Estimated picked
- Offered salary
- Required wage
- Offer above required wage
- Lottery weight points

Avoid in the primary UI:

- `h1b_public_wage_fact`
- `worker_positions`
- `weighted_entries`
- `prevailing_wage`
- `SOC title`

Technical labels can appear in methodology docs, but the main interface should read like an immigration wage research tool.

## Layout

- Header explains the product and selected-registration assumption.
- A caveat block distinguishes filed vs picked.
- Filters come before metrics.
- Metric cards answer the user's first question before tables do.
- Grouped summary table is above row-level details.
- Raw-ish row-level data remains available but secondary.

## Visual Style

The design follows the existing Project-00 dark editorial dashboard style:

- Dark background
- Compact controls
- Dense tables for analysis
- Muted explanatory copy
- Gold caveat block for methodology warnings
- Green highlight for primary results

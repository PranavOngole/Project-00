# Methodology

## Source Data

The dashboard uses public DOL OFLC Labor Condition Application disclosure data already loaded into DuckDB as:

```text
h1b_public_wage_fact
```

This table is worksite-level and joins case, employer, occupation, location, offered wage, prevailing wage, wage level, worker positions, and derived wage fields.

## Plain-English Definitions

| Dashboard Term | Meaning |
|---|---|
| Filed jobs requested | Worker positions listed on public LCA records |
| LCA filings | Distinct public Labor Condition Application case numbers |
| Offered salary | `WAGE_RATE_OF_PAY_FROM`, annualized |
| Required wage | DOL prevailing wage, annualized |
| Offer above required wage | Percent difference between offered salary and required wage |
| Wage level | DOL prevailing wage level: Level I, II, III, IV |
| Lottery weight points | Worker positions multiplied by wage-level weight |
| Estimated picked | Public-data estimate, not official USCIS group-level selection data |
| Cap proxy | Certified new-employment LCAs near the H-1B cap start window |

## Annualized Wages

The ETL normalizes wages to annual dollars:

```text
Year      x 1
Month     x 12
Bi-weekly x 26
Week      x 52
Hour      x 2080
```

If a wage range exists, the dashboard uses the lower bound as the conservative offered salary and keeps the upper bound for context.

## Estimated Picked

USCIS publishes aggregate selected-registration counts, but not selections by employer, occupation, wage level, or location. The dashboard estimates selected registrations by allocating a user-provided aggregate selected count across the filtered public LCA universe by wage-level weight.

Default:

```text
selected_registrations = 120,141
```

Formula:

```text
estimated_picked =
  selected_registrations * group_lottery_weight_points / universe_lottery_weight_points
```

Wage weights:

```text
Level I   = 1
Level II  = 2
Level III = 3
Level IV  = 4
Unknown   = 0 in the current ETL
```

## Caveat

This is not official USCIS picked-worker data. One LCA can cover multiple workers, LCA certification does not prove lottery selection, and selected beneficiary names are not public.

Use the dashboard for public-data intelligence and directional comparisons, not as legal advice or a guaranteed probability.

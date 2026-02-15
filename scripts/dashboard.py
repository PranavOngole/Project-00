"""
US Immigration Visa Dashboard — V6
Interactive dashboard with client-side filtering, Bloomberg-terminal aesthetic,
professional blue/emerald editorial palette, embedded JSON data, refusal grounds analysis,
consular post rankings, and Country × Visa Type refusal heatmap.
Outputs: docs/dashboard.html (GitHub Pages ready)
"""

import json
import duckdb
import plotly.graph_objects as go
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "immigration.duckdb"
OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "dashboard.html"

COLORS = [
    "#3B82F6", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4",
    "#EC4899", "#84CC16", "#FB923C", "#A78BFA", "#22D3EE",
]
BG = "#09090b"
CARD = "#18181b"
TEXT = "#d4d4d8"
GRID = "#27272a"
ACCENT = "#3B82F6"
ACCENT2 = "#10B981"
RED = "#EF4444"
GOLD = "#F59E0B"

CHART_LAYOUT_BASE = dict(
    plot_bgcolor=CARD, paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Inter, system-ui, sans-serif"),
    margin=dict(l=65, r=25, t=60, b=45),
    hovermode="x unified",
)


def con_ro():
    """Read-only DuckDB connection."""
    return duckdb.connect(str(DB_PATH), read_only=True)


def q(con, sql):
    """Execute SQL and return DataFrame."""
    return con.execute(sql).fetchdf()


def fetch_all_data():
    """Fetch all data needed for the dashboard."""
    con = con_ro()
    data = {}

    # --- Hero stats ---
    data["total_alltime"] = con.execute('SELECT SUM("Grand Total") FROM visa_issuances').fetchone()[0]
    data["fy24_issued"] = con.execute('SELECT SUM("Grand Total") FROM visa_issuances WHERE fiscal_year=2024').fetchone()[0]
    data["countries"] = con.execute('SELECT COUNT(DISTINCT country) FROM visa_issuances').fetchone()[0]
    data["h1b_alltime"] = con.execute('SELECT SUM("H-1B") FROM visa_issuances').fetchone()[0]
    data["f1_alltime"] = con.execute('SELECT SUM("F-1") FROM visa_issuances').fetchone()[0]

    # FY2024 workload
    wl = con.execute("SELECT SUM(total_applications), SUM(issued), SUM(refused) FROM niv_workload WHERE visa_category != 'Grand Total'").fetchone()
    data["fy24_apps"] = wl[0]
    data["fy24_refused"] = wl[2]

    # COVID
    data["fy19"] = con.execute('SELECT SUM("Grand Total") FROM visa_issuances WHERE fiscal_year=2019').fetchone()[0]
    data["fy20"] = con.execute('SELECT SUM("Grand Total") FROM visa_issuances WHERE fiscal_year=2020').fetchone()[0]

    # India vs China H-1B FY2024
    vals = {r[0]: r[1] for r in con.execute('SELECT country, "H-1B" FROM visa_issuances WHERE fiscal_year=2024 AND country IN (\'India\',\'China\')').fetchall()}
    data["india_h1b_24"] = vals.get("India", 0)
    data["china_h1b_24"] = vals.get("China", 0)

    # China YoY
    china_23 = con.execute('SELECT "Grand Total" FROM visa_issuances WHERE fiscal_year=2023 AND country=\'China\'').fetchone()[0]
    china_24 = con.execute('SELECT "Grand Total" FROM visa_issuances WHERE fiscal_year=2024 AND country=\'China\'').fetchone()[0]
    data["china_yoy"] = round((china_24 - china_23) / china_23 * 100, 1)

    # --- Chart 1: H-1B top 10 over time ---
    data["df_h1b"] = q(con, """
        WITH top AS (SELECT country, SUM("H-1B") as t FROM visa_issuances GROUP BY country ORDER BY t DESC LIMIT 10)
        SELECT v.fiscal_year, v.country, v."H-1B" as h1b
        FROM visa_issuances v JOIN top t ON v.country=t.country
        ORDER BY t.t DESC, v.fiscal_year
    """)

    # --- Chart 2: India vs China ---
    data["df_ivc"] = q(con, """
        SELECT fiscal_year, country, "H-1B" as h1b FROM visa_issuances
        WHERE country IN ('India','China') ORDER BY country, fiscal_year
    """)

    # --- Chart 3: Full refusal rates (all countries for client-side filtering) ---
    data["df_refusal_all"] = q(con, """
        SELECT nationality, adjusted_refusal_rate as rate FROM b_visa_refusals
        ORDER BY rate DESC
    """)

    # --- Chart 4: NIV workload by visa type ---
    data["df_workload"] = q(con, """
        SELECT visa_category, issued, refused, total_applications, refusal_rate
        FROM niv_workload WHERE visa_category != 'Grand Total'
        AND total_applications >= 500 ORDER BY total_applications DESC LIMIT 25
    """)

    # --- Chart 5: Total NIV timeline (global) ---
    data["df_timeline"] = q(con, """
        SELECT fiscal_year, SUM("Grand Total") as total, SUM("H-1B") as h1b,
               SUM("F-1") as f1, SUM("B-1,2") as b12, SUM("L-1") as l1
        FROM visa_issuances GROUP BY fiscal_year ORDER BY fiscal_year
    """)

    # --- Timeline country data (top 30) for client-side interactivity ---
    data["df_timeline_countries"] = q(con, """
        WITH top AS (SELECT country, SUM("Grand Total") as t FROM visa_issuances GROUP BY country ORDER BY t DESC LIMIT 30)
        SELECT v.fiscal_year, v.country, v."Grand Total" as grand_total, v."H-1B" as h1b,
               v."F-1" as f1, v."B-1,2" as b12, v."L-1" as l1
        FROM visa_issuances v JOIN top t ON v.country=t.country
        ORDER BY v.country, v.fiscal_year
    """)

    # --- FY2024 bar chart data for multiple visa types (top 30) ---
    data["df_fy24_multi"] = q(con, """
        SELECT country, "Grand Total", "H-1B", "F-1", "B-1,2", "L-1", "J-1", "H-2A", "H-2B", "O-1"
        FROM visa_issuances WHERE fiscal_year=2024
        ORDER BY "Grand Total" DESC LIMIT 30
    """)

    # --- Chart 6: B-visa estimated workload by country ---
    data["df_bvisa_wl"] = q(con, """
        SELECT country, b_visa_issued, refusal_rate_pct, est_refused, est_applications
        FROM b_visa_workload_by_country WHERE b_visa_issued > 5000
        ORDER BY est_applications DESC LIMIT 20
    """)

    # --- Chart 7: Visa Ineligibility Grounds (refusal reasons) ---
    data["df_refusal_grounds"] = q(con, """
        SELECT ina_section, description, iv_finding, iv_overcome, niv_finding, niv_overcome
        FROM visa_ineligibility_grounds
        WHERE ina_section != 'TOTAL' AND niv_finding > 0
        ORDER BY niv_finding DESC
    """)

    # --- Chart 8: Consular Posts (top 25 by NIV issued) ---
    data["df_consular_posts"] = q(con, """
        SELECT issuing_office, region, niv_issued, iv_issued, border_crossing_cards
        FROM visas_by_consular_post
        WHERE is_total = false AND niv_issued > 0
        ORDER BY niv_issued DESC LIMIT 25
    """)

    # --- Chart 9: Country x Visa Type Heatmap data ---
    data["df_heatmap"] = q(con, """
        SELECT v.country,
               v."B-1,2" as b12_issued,
               v."H-1B" as h1b_issued,
               v."F-1" as f1_issued,
               v."L-1" as l1_issued,
               v."J-1" as j1_issued,
               v."Grand Total" as grand_total,
               COALESCE(w.b_visa_refusal_rate, 0) as b_refusal_rate
        FROM visa_issuances v
        LEFT JOIN niv_workload_by_country w ON v.country = w.country
        WHERE v.fiscal_year = 2024
        ORDER BY v."Grand Total" DESC
        LIMIT 25
    """)

    # --- Explorer data ---
    visa_types = [r[0] for r in con.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='visa_issuances' AND column_name NOT IN
        ('fiscal_year','country','Total Visas','BCC','Grand Total')
        ORDER BY ordinal_position
    """).fetchall()]
    countries = [r[0] for r in con.execute("""
        SELECT country FROM visa_issuances GROUP BY country
        ORDER BY SUM("Grand Total") DESC LIMIT 30
    """).fetchall()]
    quoted = ", ".join(f'"{v}"' for v in visa_types)
    clist = ", ".join(f"'{c}'" for c in countries)
    full_df = q(con, f"""
        SELECT fiscal_year, country, {quoted} FROM visa_issuances
        WHERE country IN ({clist}) ORDER BY country, fiscal_year
    """)
    explorer = {}
    for vt in visa_types:
        explorer[vt] = {}
        for c in countries:
            cdf = full_df[full_df["country"] == c]
            vals = cdf[vt].tolist()
            if any(v > 0 for v in vals):
                explorer[vt][c] = {"years": cdf["fiscal_year"].tolist(), "values": vals}
    data["explorer"] = explorer
    data["visa_types"] = visa_types
    data["explorer_countries"] = countries

    con.close()
    return data


def make_chart(fig):
    """Apply base layout and return HTML snippet."""
    fig.update_layout(**CHART_LAYOUT_BASE)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def chart_h1b_top10(df):
    """H-1B visas over time for top 10 countries."""
    fig = go.Figure()
    countries = df["country"].unique()
    for i, c in enumerate(countries):
        cd = df[df["country"] == c]
        fig.add_trace(go.Scatter(
            x=cd["fiscal_year"].tolist(), y=cd["h1b"].tolist(), name=c,
            mode="lines+markers", line=dict(color=COLORS[i % len(COLORS)], width=2.5),
            marker=dict(size=4),
            hovertemplate=f"<b>{c}</b><br>FY%{{x}}<br>H-1B: %{{y:,.0f}}<extra></extra>",
        ))
    buttons = [dict(label="All Top 10", method="update", args=[{"visible": [True]*len(countries)}])]
    for i, c in enumerate(countries):
        vis = [False]*len(countries); vis[i] = True
        buttons.append(dict(label=c, method="update", args=[{"visible": vis}]))
    fig.update_layout(
        title=dict(text="H-1B Visa Issuances — Top 10 Countries (FY1997–2024)", font=dict(size=18, color=TEXT), x=0.5),
        updatemenus=[dict(buttons=buttons, direction="down", showactive=True,
            x=0.0, xanchor="left", y=1.22, yanchor="top",
            bgcolor="#1e1e21", bordercolor="rgba(59,130,246,0.35)", font=dict(color=TEXT, size=11), active=0)],
        xaxis=dict(title="Fiscal Year", gridcolor=GRID, dtick=2, color=TEXT),
        yaxis=dict(title="Visas Issued", gridcolor=GRID, color=TEXT,
            tickvals=list(range(0, 200001, 25000)),
            ticktext=[f"{v//1000}K" for v in range(0, 200001, 25000)]),
        legend=dict(bgcolor="rgba(24,24,27,0.9)", bordercolor=GRID, borderwidth=1, font=dict(size=10)),
        height=520, margin=dict(l=65, r=25, t=100, b=45),
    )
    return make_chart(fig)


def chart_india_china(df):
    """India vs China H-1B filled area."""
    fig = go.Figure()
    cfg = {"India": (RED, "rgba(239,68,68,0.15)"), "China": (ACCENT, "rgba(59,130,246,0.15)")}
    for country, (color, fill) in cfg.items():
        cd = df[df["country"] == country]
        fig.add_trace(go.Scatter(
            x=cd["fiscal_year"].tolist(), y=cd["h1b"].tolist(), name=country,
            mode="lines+markers", line=dict(color=color, width=3), marker=dict(size=6),
            fill="tozeroy", fillcolor=fill,
            hovertemplate=f"<b>{country}</b><br>FY%{{x}}<br>H-1B: %{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text="India vs China — H-1B Head to Head (FY1997–2024)", font=dict(size=18, color=TEXT), x=0.5),
        xaxis=dict(title="Fiscal Year", gridcolor=GRID, dtick=2, color=TEXT),
        yaxis=dict(title="H-1B Visas Issued", gridcolor=GRID, color=TEXT,
            tickvals=list(range(0, 175001, 25000)),
            ticktext=[f"{v//1000}K" for v in range(0, 175001, 25000)]),
        legend=dict(bgcolor="rgba(24,24,27,0.9)", bordercolor=GRID, borderwidth=1, font=dict(size=13),
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=460,
    )
    return make_chart(fig)


def chart_workload(df):
    """NIV workload: issued vs refused by visa category."""
    ds = df.sort_values("total_applications", ascending=True).tail(15)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=ds["visa_category"].tolist(), x=ds["issued"].tolist(), name="Issued",
        orientation="h", marker=dict(color=ACCENT), hovertemplate="%{y}: %{x:,.0f} issued<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=ds["visa_category"].tolist(), x=ds["refused"].tolist(), name="Refused",
        orientation="h", marker=dict(color=RED), hovertemplate="%{y}: %{x:,.0f} refused<extra></extra>",
    ))
    fig.update_layout(
        barmode="stack",
        title=dict(text="FY2024 NIV Workload: Issued vs Refused by Visa Category", font=dict(size=18, color=TEXT), x=0.5),
        xaxis=dict(title="Applications", gridcolor=GRID, color=TEXT,
            tickvals=list(range(0, 10000001, 2000000)),
            ticktext=[f"{v//1000000}M" for v in range(0, 10000001, 2000000)]),
        yaxis=dict(color=TEXT, tickfont=dict(size=10)),
        legend=dict(bgcolor="rgba(24,24,27,0.9)", bordercolor=GRID, borderwidth=1, font=dict(size=12),
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=520, margin=dict(l=80, r=25, t=80, b=45),
    )
    return make_chart(fig)


def chart_bvisa_workload(df):
    """B-visa estimated applications vs issued vs refused by country."""
    ds = df.sort_values("est_applications", ascending=True).tail(15)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=ds["country"].tolist(), x=ds["b_visa_issued"].tolist(), name="Issued",
        orientation="h", marker=dict(color=ACCENT2),
        hovertemplate="%{y}<br>B-Visa Issued: %{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=ds["country"].tolist(), x=ds["est_refused"].tolist(), name="Est. Refused",
        orientation="h", marker=dict(color=RED),
        hovertemplate="%{y}<br>Est. Refused: %{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        barmode="stack",
        title=dict(text="B-Visa: Estimated Applications by Country — FY2024", font=dict(size=18, color=TEXT), x=0.5),
        xaxis=dict(title="Estimated Applications", gridcolor=GRID, color=TEXT,
            tickvals=list(range(0, 1500001, 250000)),
            ticktext=[f"{v//1000}K" for v in range(0, 1500001, 250000)]),
        yaxis=dict(color=TEXT, tickfont=dict(size=10)),
        legend=dict(bgcolor="rgba(24,24,27,0.9)", bordercolor=GRID, borderwidth=1, font=dict(size=12),
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=520, margin=dict(l=160, r=25, t=80, b=45),
    )
    return make_chart(fig)


def fmt(n, suffix=""):
    """Format large numbers: 10,967,703 -> 10.97M"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M{suffix}"
    if n >= 1_000:
        return f"{n/1_000:.0f}K{suffix}"
    return f"{n:,.0f}{suffix}"


def build_timeline_json(df_global, df_countries):
    """Build JSON data for the client-side interactive timeline chart."""
    global_data = {
        "years": df_global["fiscal_year"].tolist(),
        "total": [int(x) for x in df_global["total"].tolist()],
        "h1b": [int(x) for x in df_global["h1b"].tolist()],
        "f1": [int(x) for x in df_global["f1"].tolist()],
        "b12": [int(x) for x in df_global["b12"].tolist()],
        "l1": [int(x) for x in df_global["l1"].tolist()],
    }
    country_data = {}
    for c in df_countries["country"].unique():
        cd = df_countries[df_countries["country"] == c]
        country_data[c] = {
            "years": cd["fiscal_year"].tolist(),
            "grand_total": [int(x) for x in cd["grand_total"].tolist()],
            "h1b": [int(x) for x in cd["h1b"].tolist()],
            "f1": [int(x) for x in cd["f1"].tolist()],
            "b12": [int(x) for x in cd["b12"].tolist()],
            "l1": [int(x) for x in cd["l1"].tolist()],
        }
    return json.dumps({"global": global_data, "countries": country_data})


def build_fy24_json(df):
    """Build JSON data for the client-side FY2024 bar chart."""
    result = {}
    col_map = {
        "Grand Total": "Grand Total",
        "H-1B": "H-1B",
        "F-1": "F-1",
        "B-1,2": "B-1,2",
        "L-1": "L-1",
        "J-1": "J-1",
        "H-2A": "H-2A",
        "H-2B": "H-2B",
        "O-1": "O-1",
    }
    for label, col in col_map.items():
        sorted_df = df.sort_values(col, ascending=False).head(20)
        result[label] = {
            "countries": sorted_df["country"].tolist(),
            "values": [int(x) for x in sorted_df[col].tolist()],
        }
    return json.dumps(result)


def build_refusal_json(df):
    """Build JSON data for client-side refusal rate chart with country filtering."""
    return json.dumps([
        {"nationality": str(row["nationality"]), "rate": round(float(row["rate"]), 1)}
        for _, row in df.iterrows()
    ])


def build_refusal_grounds_json(df):
    """Build JSON data for refusal grounds chart."""
    return json.dumps([
        {"ina": str(row["ina_section"]), "desc": str(row["description"]),
         "niv_find": int(row["niv_finding"]), "niv_over": int(row["niv_overcome"]),
         "iv_find": int(row["iv_finding"]), "iv_over": int(row["iv_overcome"])}
        for _, row in df.iterrows()
    ])


def build_consular_json(df):
    """Build JSON data for consular posts chart."""
    return json.dumps([
        {"office": str(row["issuing_office"]), "region": str(row["region"]),
         "niv": int(row["niv_issued"]), "iv": int(row["iv_issued"]),
         "bcc": int(row["border_crossing_cards"])}
        for _, row in df.iterrows()
    ])


def build_heatmap_json(df):
    """Build JSON data for Country x Visa Type heatmap."""
    global_b_rate = 0.2776
    visa_rates = {"B-1,2": 0.2776, "H-1B": 0.0279, "F-1": 0.4101, "L-1": 0.0390, "J-1": 0.1096}
    result = []
    for _, row in df.iterrows():
        b_rate = row["b_refusal_rate"] / 100.0 if row["b_refusal_rate"] > 0 else global_b_rate
        adj = b_rate / global_b_rate
        rates = {}
        for visa, g_rate in visa_rates.items():
            rates[visa] = round(min(g_rate * adj * 100, 95.0), 1)
        result.append({
            "country": str(row["country"]),
            "b12": rates["B-1,2"], "h1b": rates["H-1B"], "f1": rates["F-1"],
            "l1": rates["L-1"], "j1": rates["J-1"],
            "b12_issued": int(row["b12_issued"]), "h1b_issued": int(row["h1b_issued"]),
            "f1_issued": int(row["f1_issued"]), "grand_total": int(row["grand_total"]),
        })
    return json.dumps(result)


def build_html(data, charts):
    """Build the full HTML dashboard."""
    d = data
    explorer_json = json.dumps(d["explorer"])
    visa_types_json = json.dumps(d["visa_types"])
    countries_json = json.dumps(d["explorer_countries"])
    timeline_json = build_timeline_json(d["df_timeline"], d["df_timeline_countries"])
    fy24_json = build_fy24_json(d["df_fy24_multi"])
    refusal_json = build_refusal_json(d["df_refusal_all"])
    grounds_json = build_refusal_grounds_json(d["df_refusal_grounds"])
    consular_json = build_consular_json(d["df_consular_posts"])
    heatmap_json = build_heatmap_json(d["df_heatmap"])

    # COVID annotation data for timeline
    covid_row = d["df_timeline"][d["df_timeline"]["fiscal_year"] == 2020]
    covid_total = int(covid_row["total"].values[0])

    timeline_countries_list = json.dumps(sorted(d["df_timeline_countries"]["country"].unique().tolist()))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>US Immigration Visa Dashboard | DataForge365</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: {BG}; --card: {CARD}; --text: {TEXT}; --grid: {GRID};
  --accent: {ACCENT}; --accent2: {ACCENT2}; --red: {RED}; --gold: {GOLD};
  --glass: rgba(24,24,27,0.8); --glass-border: rgba(59,130,246,0.12);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif; overflow-x:hidden; }}

/* === Subtle grid background === */
body::before {{
  content:''; position:fixed; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:0;
  background-image:
    linear-gradient(rgba(39,39,42,0.3) 1px, transparent 1px),
    linear-gradient(90deg, rgba(39,39,42,0.3) 1px, transparent 1px);
  background-size: 60px 60px;
  opacity: 0.4;
}}

.content {{ position:relative; z-index:1; }}

/* === Hero === */
.hero {{ text-align:center; padding:60px 20px 40px; }}
.hero h1 {{ font-size:3rem; font-weight:900; letter-spacing:-1.5px;
  background:linear-gradient(135deg,#fff 0%,{ACCENT} 50%,{ACCENT2} 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.hero .subtitle {{ font-size:1.1rem; color:#71717a; margin-top:8px; font-weight:300; max-width:700px; margin-left:auto; margin-right:auto; }}
.hero .version-badge {{ display:inline-block; margin-top:12px; background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.25);
  border-radius:20px; padding:4px 16px; font-size:0.7rem; font-weight:600; color:{ACCENT}; letter-spacing:1px; text-transform:uppercase; }}

/* === Stats Row === */
.stats-row {{ display:flex; justify-content:center; gap:20px; padding:20px; flex-wrap:wrap; max-width:1200px; margin:0 auto; }}
.stat-card {{ background:var(--glass); border:1px solid var(--glass-border); border-radius:16px;
  padding:20px 28px; text-align:center; min-width:140px; flex:1; max-width:200px;
  transition:transform 0.3s ease, border-color 0.3s ease; }}
.stat-card:hover {{ transform:translateY(-4px); border-color:var(--accent); }}
.stat-card .value {{ font-size:2rem; font-weight:800;
  background:linear-gradient(135deg,{ACCENT},{ACCENT2});
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.stat-card .label {{ font-size:0.7rem; color:#52525b; text-transform:uppercase; letter-spacing:1.5px; margin-top:4px; font-weight:600; }}

/* === Insight Banner === */
.insight {{ max-width:1200px; margin:24px auto; padding:0 20px; }}
.insight-card {{ background:linear-gradient(135deg,rgba(59,130,246,0.06),rgba(16,185,129,0.04));
  border:1px solid rgba(59,130,246,0.15); border-radius:16px; padding:24px 32px;
  display:flex; align-items:center; gap:20px; flex-wrap:wrap; }}
.insight-icon {{ font-size:2.4rem; }}
.insight-body {{ flex:1; min-width:200px; }}
.insight-body h3 {{ font-size:1.15rem; font-weight:700; color:#fff; margin-bottom:4px; }}
.insight-body p {{ font-size:0.9rem; color:#71717a; line-height:1.6; }}
.insight-body strong {{ color:var(--accent); }}
.pills {{ display:flex; gap:12px; flex-wrap:wrap; }}
.pill {{ background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.15);
  border-radius:20px; padding:8px 20px; text-align:center; min-width:100px; }}
.pill .pv {{ font-size:1.1rem; font-weight:700; color:#fff; }}
.pill .pl {{ font-size:0.6rem; color:#52525b; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }}

/* === Section === */
.section {{ max-width:1200px; margin:0 auto; padding:0 20px; }}
.section-header {{ padding:40px 0 16px; }}
.section-header .tag {{ font-size:0.65rem; text-transform:uppercase; letter-spacing:2.5px; color:var(--accent); font-weight:700; }}
.section-header h2 {{ font-size:1.6rem; font-weight:700; color:#fff; margin-top:4px; }}
.section-header p {{ font-size:0.9rem; color:#71717a; margin-top:4px; max-width:700px; }}

/* === Chart Card === */
.chart-card {{ background:var(--glass); border:1px solid var(--glass-border); border-radius:16px;
  padding:24px; margin-bottom:24px; transition:border-color 0.3s ease; }}
.chart-card:hover {{ border-color:rgba(59,130,246,0.25); }}

/* === Chart Controls & Dropdowns === */
.chart-controls {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; align-items:end; }}
.chart-ctrl {{ display:flex; flex-direction:column; gap:4px; }}
.chart-ctrl label {{ font-size:0.65rem; text-transform:uppercase; letter-spacing:1.5px; color:{ACCENT}; font-weight:600; }}
.chart-ctrl select {{
  background:#1e1e21; color:var(--text); border:1.5px solid rgba(59,130,246,0.35); border-radius:8px;
  padding:8px 36px 8px 12px; font-size:0.85rem; font-family:inherit; cursor:pointer; min-width:180px;
  -webkit-appearance:none; appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2 4l4 4 4-4' stroke='%233B82F6' stroke-width='2' fill='none'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:right 12px center; background-size:12px;
  transition:border-color 0.2s, box-shadow 0.2s;
}}
.chart-ctrl select:hover {{ border-color:rgba(59,130,246,0.6); box-shadow:0 0 12px rgba(59,130,246,0.08); }}
.chart-ctrl select:focus {{ outline:none; border-color:{ACCENT}; box-shadow:0 0 0 3px rgba(59,130,246,0.15); }}
.chart-ctrl select[multiple] {{ min-height:100px; background-image:none; padding-right:12px; }}
.chart-note {{ font-size:0.78rem; color:#52525b; margin-top:12px; line-height:1.5; padding:12px 16px;
  background:rgba(39,39,42,0.5); border-radius:8px; border-left:3px solid var(--accent); }}

/* === Knowledge Cards === */
.know-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin:16px 0 32px; }}
.know-card {{ background:var(--glass); border:1px solid var(--glass-border); border-radius:14px;
  padding:20px 24px; transition:transform 0.3s ease, border-color 0.3s ease; }}
.know-card:hover {{ transform:translateY(-3px); border-color:var(--accent); }}
.know-card .kc-tag {{ font-size:0.6rem; text-transform:uppercase; letter-spacing:2px; font-weight:700; margin-bottom:8px; }}
.know-card .kc-tag.work {{ color:{RED}; }} .know-card .kc-tag.student {{ color:{ACCENT2}; }}
.know-card .kc-tag.tourist {{ color:{GOLD}; }} .know-card .kc-tag.family {{ color:#EC4899; }}
.know-card .kc-tag.exchange {{ color:#8B5CF6; }} .know-card .kc-tag.other {{ color:#06B6D4; }}
.know-card h4 {{ font-size:1rem; font-weight:700; color:#fff; margin-bottom:6px; }}
.know-card p {{ font-size:0.82rem; color:#71717a; line-height:1.5; }}
.know-card .kc-stat {{ font-size:0.75rem; color:var(--accent); font-weight:600; margin-top:8px; }}

/* === Fun Facts === */
.facts-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; margin:16px 0 32px; }}
.fact-card {{ background:var(--glass); border:1px solid var(--glass-border); border-radius:14px; padding:20px 24px; }}
.fact-card .fact-number {{ font-size:1.8rem; font-weight:800;
  background:linear-gradient(135deg,{ACCENT},{ACCENT2});
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.fact-card .fact-label {{ font-size:0.7rem; color:#52525b; text-transform:uppercase; letter-spacing:1.5px; font-weight:600; margin-top:2px; }}
.fact-card .fact-desc {{ font-size:0.82rem; color:#71717a; margin-top:8px; line-height:1.5; }}

/* === AI Stats === */
.ai-stats-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin:16px 0 32px; }}
.ai-stat-card {{ background:var(--glass); border:1px solid rgba(139,92,246,0.15); border-radius:14px; padding:20px 24px;
  transition:transform 0.3s ease, border-color 0.3s ease; }}
.ai-stat-card:hover {{ transform:translateY(-3px); border-color:rgba(139,92,246,0.4); }}
.ai-stat-card .ai-label {{ font-size:0.6rem; text-transform:uppercase; letter-spacing:2px; color:#8B5CF6; font-weight:700; margin-bottom:6px; }}
.ai-stat-card .ai-value {{ font-size:1.1rem; font-weight:700; color:#fff; }}
.ai-stat-card .ai-detail {{ font-size:0.78rem; color:#52525b; margin-top:4px; line-height:1.4; }}

/* === Explorer === */
.explorer-controls {{ display:flex; gap:16px; margin-bottom:16px; flex-wrap:wrap; align-items:end; }}
.ctrl {{ display:flex; flex-direction:column; gap:6px; }}
.ctrl label {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:1.5px; color:{ACCENT}; font-weight:600; }}
.ctrl select {{
  background:#1e1e21; color:var(--text); border:1.5px solid rgba(59,130,246,0.35); border-radius:10px;
  padding:10px 36px 10px 14px; font-size:0.9rem; font-family:inherit; cursor:pointer; min-width:200px;
  -webkit-appearance:none; appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2 4l4 4 4-4' stroke='%233B82F6' stroke-width='2' fill='none'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:right 12px center; background-size:12px;
  transition:border-color 0.2s, box-shadow 0.2s;
}}
.ctrl select:hover {{ border-color:rgba(59,130,246,0.6); box-shadow:0 0 12px rgba(59,130,246,0.08); }}
.ctrl select:focus {{ outline:none; border-color:{ACCENT}; box-shadow:0 0 0 3px rgba(59,130,246,0.15); }}
.ctrl select[multiple] {{ min-height:120px; background-image:none; padding-right:14px; }}

/* === Heatmap === */
.heatmap-wrap {{ overflow-x:auto; }}
.heatmap-table {{ border-collapse:collapse; width:100%; font-size:0.78rem; }}
.heatmap-table th {{ padding:10px 12px; text-align:center; color:{ACCENT}; font-weight:600;
  font-size:0.65rem; text-transform:uppercase; letter-spacing:1px; border-bottom:1px solid var(--grid); }}
.heatmap-table th:first-child {{ text-align:left; }}
.heatmap-table td {{ padding:8px 12px; text-align:center; border-bottom:1px solid rgba(39,39,42,0.5); }}
.heatmap-table td:first-child {{ text-align:left; color:#fff; font-weight:600; font-size:0.82rem; }}
.heatmap-table tr:hover {{ background:rgba(59,130,246,0.05); }}
.hm-cell {{ display:inline-block; padding:4px 10px; border-radius:6px; font-weight:600; font-size:0.78rem; min-width:50px; }}

/* === Pipeline Architecture === */
.pipeline {{ margin:24px 0; }}
.pipeline-layer {{ margin:8px 0; }}
.layer-label {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:2px; font-weight:700; margin-bottom:10px; color:#71717a; }}
.layer-nodes {{ display:flex; gap:12px; flex-wrap:wrap; }}
.p-node {{ background:var(--glass); border-radius:10px; padding:14px 18px; font-size:0.85rem;
  font-weight:600; color:#fff; flex:1; min-width:180px; max-width:280px; }}
.p-node span {{ display:block; font-size:0.72rem; color:#52525b; font-weight:400; margin-top:4px; }}
.p-node.source {{ border:1.5px solid #8B5CF6; }}
.p-node.etl {{ border:1.5px solid {GOLD}; }}
.p-node.table {{ border:1.5px solid {ACCENT}; }}
.p-node.table.primary {{ border:1.5px solid {ACCENT2}; }}
.p-node.output {{ border:1.5px solid {ACCENT2}; }}
.pipeline-arrow {{ text-align:center; color:#52525b; font-size:1.4rem; margin:6px 0; letter-spacing:8px; }}
.rel-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; margin:16px 0 32px; }}
.rel-card {{ background:var(--glass); border:1px solid var(--glass-border); border-radius:14px; padding:18px 22px; }}
.rel-card h4 {{ font-size:0.9rem; font-weight:700; color:#fff; margin-bottom:6px; }}
.rel-card p {{ font-size:0.78rem; color:#71717a; line-height:1.5; }}
.rel-card code {{ font-size:0.72rem; color:{ACCENT}; background:rgba(59,130,246,0.08); padding:2px 6px; border-radius:4px; }}

/* === Footer === */
.footer {{ text-align:center; padding:40px 20px; color:#27272a; font-size:0.8rem; max-width:1200px; margin:0 auto;
  border-top:1px solid var(--grid); }}
.footer a {{ color:var(--accent); text-decoration:none; }}
.footer a:hover {{ text-decoration:underline; }}

/* === Responsive === */
@media(max-width:768px) {{
  .hero h1 {{ font-size:1.8rem; }}
  .stats-row {{ gap:10px; }}
  .stat-card {{ min-width:100px; padding:14px 16px; }}
  .stat-card .value {{ font-size:1.4rem; }}
  .insight-card {{ flex-direction:column; text-align:center; }}
  .know-grid,.facts-grid,.ai-stats-grid,.rel-grid {{ grid-template-columns:1fr; }}
  .explorer-controls,.chart-controls {{ flex-direction:column; }}
  .ctrl select,.chart-ctrl select {{ min-width:100%; }}
  .layer-nodes {{ flex-direction:column; }}
  .p-node {{ max-width:100%; }}
}}
</style>
</head>
<body>

<div class="content">

<!-- ===== HERO ===== -->
<div class="hero">
  <h1>US Immigration Visa Dashboard</h1>
  <p class="subtitle">28 years of nonimmigrant visa data from the U.S. Department of State — every visa, every country, every trend.</p>
  <div class="version-badge">V6 Interactive</div>
</div>

<!-- ===== STATS ROW ===== -->
<div class="stats-row">
  <div class="stat-card"><div class="value">{fmt(d['total_alltime'])}</div><div class="label">Visas Issued All-Time</div></div>
  <div class="stat-card"><div class="value">{fmt(d['fy24_apps'])}</div><div class="label">FY2024 Applications</div></div>
  <div class="stat-card"><div class="value">{fmt(d['fy24_issued'])}</div><div class="label">FY2024 Issued</div></div>
  <div class="stat-card"><div class="value">{fmt(d['fy24_refused'])}</div><div class="label">FY2024 Refused</div></div>
  <div class="stat-card"><div class="value">{d['countries']}</div><div class="label">Countries</div></div>
</div>

<!-- ===== INSIGHT BANNER ===== -->
<div class="insight">
  <div class="insight-card">
    <div class="insight-icon">&#x1f4ca;</div>
    <div class="insight-body">
      <h3>India dominates H-1B at {d['india_h1b_24']/d['china_h1b_24']:.1f}x China's volume</h3>
      <p>In FY2024, India received <strong>{fmt(d['india_h1b_24'])}</strong> H-1B visas vs China's <strong>{fmt(d['china_h1b_24'])}</strong>.
      Meanwhile, China's total NIV issuances surged <strong>+{d['china_yoy']}% year-over-year</strong> — the biggest jump of any major country.</p>
    </div>
    <div class="pills">
      <div class="pill"><div class="pv">{fmt(d['india_h1b_24'])}</div><div class="pl">India H-1B</div></div>
      <div class="pill"><div class="pv">{fmt(d['china_h1b_24'])}</div><div class="pl">China H-1B</div></div>
      <div class="pill"><div class="pv">+{d['china_yoy']}%</div><div class="pl">China YoY</div></div>
    </div>
  </div>
</div>

<!-- ===== SECTION: What is an NIV? ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Education</div>
    <h2>What is a Nonimmigrant Visa (NIV)?</h2>
    <p>A nonimmigrant visa allows foreign nationals to enter the U.S. temporarily — for tourism, work, study, or cultural exchange. Unlike immigrant visas (green cards), NIVs do not grant permanent residency. There are over 90 NIV categories, each with different rules, quotas, and approval rates.</p>
  </div>
  <div class="know-grid">
    <div class="know-card">
      <div class="kc-tag work">Work Visa</div>
      <h4>H-1B — Specialty Occupation</h4>
      <p>For professionals in fields like tech, engineering, medicine, and finance. Requires a bachelor's degree or equivalent. Subject to an annual cap of 65,000 (plus 20,000 for U.S. master's degrees). The most sought-after work visa.</p>
      <div class="kc-stat">All-time issued: {fmt(d['h1b_alltime'])} | FY2024 refusal rate: 2.8%</div>
    </div>
    <div class="know-card">
      <div class="kc-tag student">Student Visa</div>
      <h4>F-1 — Academic Student</h4>
      <p>For full-time students at accredited U.S. colleges, universities, and language programs. Allows limited on-campus work and post-graduation OPT (Optional Practical Training) for up to 3 years in STEM fields.</p>
      <div class="kc-stat">All-time issued: {fmt(d['f1_alltime'])} | FY2024 refusal rate: 41.0%</div>
    </div>
    <div class="know-card">
      <div class="kc-tag tourist">Tourist / Business</div>
      <h4>B-1/B-2 — Visitor Visa</h4>
      <p>B-1 is for business (meetings, conferences, negotiations). B-2 is for tourism, medical treatment, or visiting family. B-1/B-2 combo is the most commonly issued visa in the world — 6.5 million in FY2024 alone.</p>
      <div class="kc-stat">FY2024: 9M applications | 27.8% refusal rate</div>
    </div>
    <div class="know-card">
      <div class="kc-tag work">Intracompany Transfer</div>
      <h4>L-1 — Intracompany Transferee</h4>
      <p>For employees transferring from a foreign office to a U.S. branch of the same company. L-1A for managers/executives, L-1B for specialized knowledge workers. No annual cap — popular with large multinationals.</p>
      <div class="kc-stat">FY2024 refusal rate: 6.0%</div>
    </div>
    <div class="know-card">
      <div class="kc-tag exchange">Exchange Visitor</div>
      <h4>J-1 — Exchange Visitor</h4>
      <p>For participants in approved exchange programs: research scholars, professors, au pairs, interns, and cultural exchange visitors. Some J-1 holders are subject to a 2-year home residency requirement before applying for other visas.</p>
      <div class="kc-stat">FY2024: 362K applications | 11.0% refusal rate</div>
    </div>
    <div class="know-card">
      <div class="kc-tag family">Fianc&eacute;(e) Visa</div>
      <h4>K-1 — Fianc&eacute;(e) of U.S. Citizen</h4>
      <p>Allows a foreign fianc&eacute;(e) to enter the U.S. to marry their American partner within 90 days of arrival. After marriage, the K-1 holder can apply for adjustment of status to permanent residence.</p>
      <div class="kc-stat">FY2024: 53.7K applications | 11.4% refusal rate</div>
    </div>
  </div>
</div>

<!-- ===== SECTION: The Big Picture (CLIENT-SIDE INTERACTIVE) ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Overview</div>
    <h2>The Big Picture: 28 Years of NIV Trends</h2>
    <p>From the post-9/11 security tightening to the COVID-19 collapse and the 2024 recovery boom — every major policy shift shows up in the data. Select countries to compare individual trends.</p>
  </div>
  <div class="chart-card">
    <div class="chart-controls">
      <div class="chart-ctrl">
        <label>Country Filter</label>
        <select id="timeline-country-select" multiple>
          <option value="__global__" selected>Global Total (All Countries)</option>
        </select>
      </div>
    </div>
    <div id="timeline-chart" style="height:480px;"></div>
  </div>
</div>

<!-- ===== SECTION: H-1B Deep Dive ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">H-1B Deep Dive</div>
    <h2>The H-1B Race: Who's Getting America's Work Visas?</h2>
    <p>India has dominated H-1B for over two decades, receiving more visas than the next 9 countries combined. Use the dropdown to isolate individual countries.</p>
  </div>
  <div class="chart-card">
    {charts['h1b']}
    <div class="chart-note">Note: H-1B data is broken down by country of origin, not by occupation. Occupation-level data (e.g., Software Engineers, Mechanical Engineers) is published separately by USCIS and is planned for a future update.</div>
  </div>
  <div class="chart-card">{charts['india_china']}</div>
</div>

<!-- ===== SECTION: FY2024 Snapshot (CLIENT-SIDE INTERACTIVE) ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">FY2024 Snapshot</div>
    <h2>Who Got the Most Visas in FY2024?</h2>
    <p>Mexico leads overall volume driven by proximity and B-1/B-2 tourist visas. India dominates work categories. Use the dropdown to explore different visa types.</p>
  </div>
  <div class="chart-card">
    <div class="chart-controls">
      <div class="chart-ctrl">
        <label>Visa Type</label>
        <select id="fy24-visa-select">
          <option value="Grand Total" selected>Grand Total</option>
          <option value="H-1B">H-1B</option>
          <option value="F-1">F-1 (Student)</option>
          <option value="B-1,2">B-1,2 (Tourist/Business)</option>
          <option value="L-1">L-1 (Intracompany)</option>
          <option value="J-1">J-1 (Exchange)</option>
          <option value="H-2A">H-2A (Agricultural)</option>
          <option value="H-2B">H-2B (Temporary Worker)</option>
          <option value="O-1">O-1 (Extraordinary Ability)</option>
        </select>
      </div>
    </div>
    <div id="fy24-bar-chart" style="height:600px;"></div>
    <div class="chart-note">Note: India's H-1B dominance (150K+) is real data, not a display bug. The color scale uses logarithmic normalization so smaller countries remain visible. Values shown as text labels on each bar.</div>
  </div>
</div>

<!-- ===== SECTION: Refusals ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Refusals &amp; Rejections</div>
    <h2>The Other Side: Who Gets Denied?</h2>
    <p>In FY2024, the U.S. refused <strong>{fmt(d['fy24_refused'])}</strong> visa applications out of <strong>{fmt(d['fy24_apps'])}</strong> total — a 23% overall refusal rate.
    The "adjusted refusal rate" accounts for cases initially refused but later approved (overcomes).</p>
  </div>
  <div class="chart-card">{charts['workload']}</div>
  <div class="chart-card">
    <div class="chart-controls">
      <div class="chart-ctrl">
        <label>View</label>
        <select id="refusal-mode-select">
          <option value="top20" selected>Top 20 Highest Refusal Rates</option>
          <option value="low15">Top 15 Lowest Refusal Rates</option>
          <option value="search">Search by Country</option>
        </select>
      </div>
      <div class="chart-ctrl" id="refusal-search-ctrl" style="display:none;">
        <label>Country</label>
        <select id="refusal-country-select"></select>
      </div>
    </div>
    <div id="refusal-chart" style="height:560px;"></div>
  </div>
  <div class="chart-card">{charts['bvisa_wl']}</div>
</div>

<!-- ===== SECTION: Why Visas Get Denied ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Refusal Grounds</div>
    <h2>Why Visas Get Denied: The Statutory Breakdown</h2>
    <p>Every visa refusal cites a specific section of the Immigration and Nationality Act. Section 214(b) — "failure to establish entitlement to nonimmigrant status" — accounts for 77% of all NIV refusals. Translation: the consular officer didn't believe you'd return home.</p>
  </div>
  <div class="chart-card">
    <div class="chart-controls">
      <div class="chart-ctrl">
        <label>View</label>
        <select id="grounds-mode-select">
          <option value="top15" selected>Top 15 NIV Refusal Grounds</option>
          <option value="top15iv">Top 15 Immigrant Visa Grounds</option>
          <option value="overcome">Highest Overcome Rates (NIV)</option>
        </select>
      </div>
    </div>
    <div id="grounds-chart" style="height:520px;"></div>
    <div class="chart-note">Note: One application can be refused on multiple grounds — totals exceed the number of individual refusals. "Overcome" means the refusal was later waived or resolved. Source: Table XIX, State Dept Annual Report FY2024.</div>
  </div>
</div>

<!-- ===== SECTION: Where Visas Are Issued ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Consular Geography</div>
    <h2>Where Visas Are Issued: Busiest U.S. Embassies</h2>
    <p>Not all consular posts are created equal. Monterrey, Mexico processes more NIVs than most countries' entire visa operations. India's five posts combined issued over 1.1 million visas in FY2024.</p>
  </div>
  <div class="chart-card">
    <div id="consular-chart" style="height:620px;"></div>
  </div>
</div>

<!-- ===== SECTION: Country x Visa Type Heatmap ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Refusal Heatmap</div>
    <h2>Country &times; Visa Type: Estimated Refusal Rates</h2>
    <p>Not all countries face the same odds. A Nigerian F-1 applicant faces an estimated 69% refusal rate vs a Romanian at 4%. Rates are estimated using each country's B-visa refusal rate as a proxy for overall consular scrutiny, applied to global per-visa-type rates.</p>
  </div>
  <div class="chart-card">
    <div class="heatmap-wrap">
      <table class="heatmap-table" id="heatmap-table">
        <thead>
          <tr>
            <th>Country</th>
            <th>B-1/B-2</th>
            <th>H-1B</th>
            <th>F-1</th>
            <th>L-1</th>
            <th>J-1</th>
            <th>FY24 Total Issued</th>
          </tr>
        </thead>
        <tbody id="heatmap-body"></tbody>
      </table>
    </div>
    <div class="chart-note">Methodology: Each country's B-visa adjusted refusal rate (published by State Dept) is used as a scaling factor against global per-visa-type refusal rates. This assumes a country with 2x the average B-visa refusal rate will have roughly 2x the refusal rate for other visa types. This is an estimate — actual per-country per-visa refusal data is not publicly available.</div>
  </div>
</div>

<!-- ===== SECTION: Fun Facts ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">By the Numbers</div>
    <h2>Stats That Tell a Story</h2>
  </div>
  <div class="facts-grid">
    <div class="fact-card">
      <div class="fact-number">54%</div><div class="fact-label">COVID Collapse</div>
      <div class="fact-desc">Visa issuances dropped 54% from FY2019 to FY2020 — from {fmt(d['fy19'])} to {fmt(d['fy20'])}. The biggest single-year drop in modern immigration history.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">+96%</div><div class="fact-label">China's Comeback</div>
      <div class="fact-desc">China's total NIV issuances nearly doubled from FY2023 to FY2024, surging 96.3% year-over-year as post-COVID travel demand exploded.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">82.8%</div><div class="fact-label">Highest Refusal Rate</div>
      <div class="fact-desc">Laos has the highest B-visa adjusted refusal rate in FY2024. Over 4 in 5 Laotian tourist/business visa applicants are denied.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">1.5%</div><div class="fact-label">Lowest Refusal Rate</div>
      <div class="fact-desc">UAE citizens enjoy the lowest B-visa refusal rate at just 1.5%. Wealth, stability, and strong return rates make the difference.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">41%</div><div class="fact-label">Student Visa Rejections</div>
      <div class="fact-desc">F-1 student visas have a 41% refusal rate — 278,553 applicants were denied in FY2024 alone. Consular officers must be convinced you'll return home.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">{fmt(d['total_alltime'])}</div><div class="fact-label">All-Time Visas Issued</div>
      <div class="fact-desc">Over 200 million nonimmigrant visas issued from FY1997 to FY2024. That's more than the combined populations of the UK, France, and Canada.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">4.7x</div><div class="fact-label">India vs China H-1B</div>
      <div class="fact-desc">India received 4.7x more H-1B visas than China in FY2024. India's dominance in tech outsourcing and IT services drives this gap.</div>
    </div>
    <div class="fact-card">
      <div class="fact-number">9M</div><div class="fact-label">Tourist Visa Apps</div>
      <div class="fact-desc">B-1/B-2 (tourist/business) visas alone generated 9 million applications in FY2024 — 63% of all NIV applications worldwide.</div>
    </div>
  </div>
</div>

<!-- ===== SECTION: Explorer ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Interactive Explorer</div>
    <h2>Build Your Own Chart</h2>
    <p>Pick any visa type and any combination of countries to explore 28 years of data.</p>
  </div>
  <div class="chart-card">
    <div class="explorer-controls">
      <div class="ctrl"><label>Visa Type</label><select id="visa-select"></select></div>
      <div class="ctrl"><label>Countries (Cmd/Ctrl + click for multiple)</label><select id="country-select" multiple></select></div>
    </div>
    <div id="explorer-chart"></div>
  </div>
</div>

<!-- ===== SECTION: AI & Pipeline Stats ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Behind the Scenes</div>
    <h2>AI &amp; Pipeline Stats</h2>
    <p>This entire dashboard — data pipeline, analysis, and visualization — was built in a single session with AI assistance.</p>
  </div>
  <div class="ai-stats-grid">
    <div class="ai-stat-card">
      <div class="ai-label">Model</div>
      <div class="ai-value">Claude Opus 4.6</div>
      <div class="ai-detail">Anthropic's frontier reasoning model</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Pipeline</div>
      <div class="ai-value">5 ETL Scripts, 6 DuckDB Tables</div>
      <div class="ai-detail">3 data sources ingested and normalized</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Data Points Processed</div>
      <div class="ai-value">5,878 Total</div>
      <div class="ai-detail">5,564 visa issuance rows + 81 workload rows + 199 refusal rates + 34 country mappings</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">PDF Pages Parsed</div>
      <div class="ai-value">10 Pages</div>
      <div class="ai-detail">3 workload + 7 refusal rate tables extracted via pdfplumber</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Country Standardization</div>
      <div class="ai-value">34 Mappings</div>
      <div class="ai-detail">Cross-referenced across 3 tables with different naming conventions</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Dashboard Versions</div>
      <div class="ai-value">V1 &rarr; V2 &rarr; V3 &rarr; V4 &rarr; V5 &rarr; V6</div>
      <div class="ai-detail">V1 (broken) &rarr; V2 (fixed) &rarr; V3 (storytelling) &rarr; V4 (interactive) &rarr; V5 (editorial) &rarr; V6 (deep analysis)</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Session</div>
      <div class="ai-value">Single Session</div>
      <div class="ai-detail">February 14, 2026</div>
    </div>
    <div class="ai-stat-card">
      <div class="ai-label">Tech Stack</div>
      <div class="ai-value">Python 3.13 + DuckDB</div>
      <div class="ai-detail">Plotly.js + pdfplumber for full pipeline</div>
    </div>
  </div>
</div>

<!-- ===== SECTION: Data Model & Architecture ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Architecture</div>
    <h2>Data Model &amp; Pipeline Architecture</h2>
    <p>From raw government PDFs and Excel files to interactive dashboard — here's how the data flows through 3 ETL scripts, 6 DuckDB tables, and one Python generator.</p>
  </div>
  <div class="chart-card">
    <div class="pipeline">
      <div class="pipeline-layer">
        <div class="layer-label">Raw Sources</div>
        <div class="layer-nodes">
          <div class="p-node source">State Dept Excel<span>FYs97-24_NIVDetailTable.xlsx — 28 sheets, one per fiscal year</span></div>
          <div class="p-node source">NIV Workload PDF<span>FY2024 workload by visa category — 3 pages of tables</span></div>
          <div class="p-node source">B-Visa Refusal PDF<span>FY2024 adjusted refusal rates by nationality — 7 pages</span></div>
        </div>
      </div>
      <div class="pipeline-arrow">&#x25BC; &#x25BC; &#x25BC;</div>
      <div class="pipeline-layer">
        <div class="layer-label">ETL Scripts</div>
        <div class="layer-nodes">
          <div class="p-node etl">merge_niv_sheets.py<span>Reads 28 Excel sheets &rarr; standardizes columns &rarr; single CSV (5,564 rows)</span></div>
          <div class="p-node etl">extract_refusal_data.py<span>pdfplumber extracts tables from PDF &rarr; cleans rates &rarr; CSV</span></div>
          <div class="p-node etl">standardize_countries.py<span>34 name mappings across 3 tables with different naming conventions</span></div>
        </div>
      </div>
      <div class="pipeline-arrow">&#x25BC; &#x25BC; &#x25BC;</div>
      <div class="pipeline-layer">
        <div class="layer-label">DuckDB Tables</div>
        <div class="layer-nodes">
          <div class="p-node table primary">visa_issuances<span>5,564 rows &middot; 28 FYs &times; 199 countries &middot; Primary fact table</span></div>
          <div class="p-node table">niv_workload<span>81 rows &middot; FY2024 applications, issued, refused by category</span></div>
          <div class="p-node table">b_visa_refusals<span>199 rows &middot; Adjusted refusal rates by nationality</span></div>
          <div class="p-node table">country_mapping<span>34 rows &middot; Bridge table for name standardization</span></div>
          <div class="p-node table">b_visa_workload_by_country<span>Derived &middot; issued &times; rate / (1 - rate) = estimated refused</span></div>
          <div class="p-node table">niv_workload_by_country<span>Derived &middot; National totals disaggregated by country proportion</span></div>
        </div>
      </div>
      <div class="pipeline-arrow">&#x25BC;</div>
      <div class="pipeline-layer">
        <div class="layer-label">Output</div>
        <div class="layer-nodes">
          <div class="p-node output">dashboard.html<span>Single-file static site &rarr; GitHub Pages &middot; All data embedded as JSON</span></div>
        </div>
      </div>
    </div>
  </div>

  <h3 style="font-size:1.1rem;font-weight:700;color:#fff;margin:24px 0 12px;">How the 6 Tables Connect</h3>
  <div class="rel-grid">
    <div class="rel-card">
      <h4>visa_issuances (Primary)</h4>
      <p>The core fact table. Every chart starts here. JOIN key: <code>country</code> + <code>fiscal_year</code>. Contains 90+ NIV category columns (H-1B, F-1, B-1,2, L-1, etc.) with issuance counts per country per year.</p>
    </div>
    <div class="rel-card">
      <h4>b_visa_refusals &rarr; b_visa_workload</h4>
      <p>Refusal rates by nationality are JOINed to B-visa issuance counts via <code>country_mapping</code>. Derived formula: <code>est_refused = issued &times; rate / (1 - rate)</code>. This is an estimate — State Dept doesn't publish per-country refusal counts.</p>
    </div>
    <div class="rel-card">
      <h4>niv_workload &rarr; niv_workload_by_country</h4>
      <p>National-level workload totals (applications, issued, refused) are disaggregated to country-level using each country's share of issuances from <code>visa_issuances</code>.</p>
    </div>
    <div class="rel-card">
      <h4>country_mapping (Bridge)</h4>
      <p>Maps 34 different country names across tables. Example: "Korea, South" in visa_issuances matches "South Korea" in b_visa_refusals. Without this, JOINs fail silently — the worst kind of data bug.</p>
    </div>
  </div>
</div>

<!-- ===== SECTION: Methodology ===== -->
<div class="section">
  <div class="section-header">
    <div class="tag">Methodology</div>
    <h2>How This Dashboard Was Built</h2>
  </div>
  <div class="know-grid">
    <div class="know-card">
      <div class="kc-tag other">Data Sources</div>
      <h4>U.S. Department of State</h4>
      <p>All data comes from officially published State Department statistics: NIV issuance tables (FY1997–2024), NIV Workload by Visa Category (FY2024), and B-Visa Adjusted Refusal Rates by Nationality (FY2024).</p>
    </div>
    <div class="know-card">
      <div class="kc-tag other">Estimated Refusals</div>
      <h4>Derived Data Disclaimer</h4>
      <p>Country-level refusal counts are <em>estimated</em> using the B-visa adjusted refusal rate formula: refused = issued &times; rate / (1 - rate). The State Dept does not publish per-country refusal counts for all visa types.</p>
    </div>
    <div class="know-card">
      <div class="kc-tag other">Tech Stack</div>
      <h4>DuckDB + Plotly + Python</h4>
      <p>Data pipeline: Python 3.13 + pandas + pdfplumber for extraction. Analytics: DuckDB as the query engine. Visualization: Plotly.js for interactive charts. All code is open source on GitHub.</p>
    </div>
  </div>
</div>

</div><!-- /content -->

<!-- ===== FOOTER ===== -->
<div class="footer">
  Built by <strong>Pranav Ongole</strong> | Data: U.S. Department of State |
  <a href="https://github.com/PranavOngole/Project-00">View on GitHub</a><br>
  <span style="font-size:0.7rem;color:#27272a;margin-top:8px;display:inline-block;">DataForge365 &middot; Project 00 &middot; 2026</span>
</div>

<!-- ===== EMBEDDED DATA FOR CLIENT-SIDE CHARTS ===== -->
<script>
const TIMELINE_DATA = {timeline_json};
const TIMELINE_COUNTRIES = {timeline_countries_list};
const FY24_DATA = {fy24_json};
const REFUSAL_DATA = {refusal_json};
const GROUNDS_DATA = {grounds_json};
const CONSULAR_DATA = {consular_json};
const HEATMAP_DATA = {heatmap_json};
const CHART_COLORS = {json.dumps(COLORS)};
const CARD_BG = '{CARD}';
const TEXT_COLOR = '{TEXT}';
const GRID_COLOR = '{GRID}';
const RED_COLOR = '{RED}';
const ACCENT_COLOR = '{ACCENT}';
const ACCENT2_COLOR = '{ACCENT2}';
const GOLD_COLOR = '{GOLD}';
const COVID_TOTAL = {covid_total};
</script>

<!-- ===== TIMELINE CHART JS ===== -->
<script>
(function() {{
  const sel = document.getElementById('timeline-country-select');
  TIMELINE_COUNTRIES.forEach(c => {{
    const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o);
  }});

  const catMap = {{
    'total': 'Total NIV', 'h1b': 'H-1B', 'f1': 'F-1', 'b12': 'B-1/B-2', 'l1': 'L-1'
  }};
  const catColors = {{
    'total': CHART_COLORS[0], 'h1b': CHART_COLORS[1], 'f1': CHART_COLORS[2],
    'b12': CHART_COLORS[3], 'l1': CHART_COLORS[4]
  }};

  function renderTimeline() {{
    const selected = Array.from(sel.selectedOptions).map(o => o.value);
    const showGlobal = selected.includes('__global__') || selected.length === 0;
    const countryPicks = selected.filter(s => s !== '__global__');
    const traces = [];
    const annotations = [];

    if (showGlobal && countryPicks.length === 0) {{
      const g = TIMELINE_DATA.global;
      const cats = [['total',true],['b12',false],['h1b',false],['f1',false],['l1',false]];
      cats.forEach(([key, vis]) => {{
        traces.push({{
          x: g.years, y: g[key], name: catMap[key],
          mode: 'lines+markers', line: {{color: catColors[key], width: vis ? 2.5 : 2}},
          marker: {{size: 4}}, visible: vis ? true : 'legendonly',
          hovertemplate: '<b>' + catMap[key] + '</b><br>FY%{{x}}: %{{y:,.0f}}<extra></extra>'
        }});
      }});
      const covidIdx = g.years.indexOf(2020);
      if (covidIdx >= 0) {{
        annotations.push({{
          x: 2020, y: COVID_TOTAL, text: 'COVID-19<br>-54% drop',
          showarrow: true, arrowhead: 2, arrowcolor: RED_COLOR,
          font: {{color: RED_COLOR, size: 11}}, ax: 40, ay: -50
        }});
      }}
    }} else {{
      countryPicks.forEach((c, i) => {{
        const cd = TIMELINE_DATA.countries[c];
        if (!cd) return;
        const cats = [['grand_total',true],['b12',false],['h1b',false],['f1',false],['l1',false]];
        const catLabels = {{'grand_total':'Total','b12':'B-1/B-2','h1b':'H-1B','f1':'F-1','l1':'L-1'}};
        cats.forEach(([key, vis]) => {{
          const baseColor = CHART_COLORS[i % CHART_COLORS.length];
          traces.push({{
            x: cd.years, y: cd[key],
            name: countryPicks.length === 1 ? catLabels[key] : c + ' - ' + catLabels[key],
            mode: 'lines+markers',
            line: {{color: key === 'grand_total' ? baseColor : CHART_COLORS[(i * 5 + ['grand_total','h1b','f1','b12','l1'].indexOf(key)) % CHART_COLORS.length], width: key === 'grand_total' ? 2.5 : 2}},
            marker: {{size: 4}},
            visible: vis ? true : 'legendonly',
            hovertemplate: '<b>' + c + ' ' + catLabels[key] + '</b><br>FY%{{x}}: %{{y:,.0f}}<extra></extra>'
          }});
        }});
      }});
    }}

    const allY = traces.filter(t => t.visible === true).flatMap(t => t.y);
    const mx = Math.max(...allY, 1);
    let step;
    if (mx > 5000000) step = 2000000;
    else if (mx > 1000000) step = 500000;
    else if (mx > 100000) step = 50000;
    else if (mx > 10000) step = 5000;
    else step = 1000;
    const tv = [], tt = [];
    for (let v = 0; v <= mx * 1.15; v += step) {{
      tv.push(v);
      if (v >= 1000000) tt.push((v/1000000).toFixed(v % 1000000 === 0 ? 0 : 1) + 'M');
      else if (v >= 1000) tt.push((v/1000).toFixed(0) + 'K');
      else tt.push(v.toString());
    }}

    Plotly.newPlot('timeline-chart', traces, {{
      title: {{text: '28 Years of US Nonimmigrant Visas (FY1997–2024)', font: {{size: 18, color: TEXT_COLOR}}, x: 0.5}},
      xaxis: {{title: 'Fiscal Year', gridcolor: GRID_COLOR, dtick: 2, color: TEXT_COLOR}},
      yaxis: {{title: 'Visas Issued', gridcolor: GRID_COLOR, color: TEXT_COLOR, tickvals: tv, ticktext: tt}},
      plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
      font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
      legend: {{bgcolor: 'rgba(24,24,27,0.9)', bordercolor: GRID_COLOR, borderwidth: 1, font: {{size: 11}}}},
      hovermode: 'x unified', margin: {{l: 65, r: 25, t: 55, b: 45}},
      annotations: annotations
    }}, {{responsive: true, displayModeBar: false}});
  }}

  sel.addEventListener('change', renderTimeline);
  renderTimeline();
}})();
</script>

<!-- ===== FY2024 BAR CHART JS (Log-Normalized) ===== -->
<script>
(function() {{
  const sel = document.getElementById('fy24-visa-select');

  function fmtVal(v) {{
    if (v >= 1000000) return (v/1000000).toFixed(1) + 'M';
    if (v >= 1000) return (v/1000).toFixed(1) + 'K';
    return v.toString();
  }}

  function renderFY24() {{
    const vt = sel.value;
    const d = FY24_DATA[vt];
    if (!d) return;
    const countries = d.countries.slice().reverse();
    const values = d.values.slice().reverse();

    // Log-normalized color mapping: small bars get visible dark blue, large bars get bright blue
    const maxVal = Math.max(...values, 1);
    const logMax = Math.log10(maxVal);
    const colors = values.map(v => {{
      if (v <= 0) return '#1E3A5F';
      const norm = Math.log10(Math.max(v, 1)) / logMax;
      // Interpolate #1E3A5F (dark blue) -> #3B82F6 (accent blue) -> #93C5FD (light blue)
      let r, g, b;
      if (norm < 0.5) {{
        const t = norm * 2;
        r = Math.round(30 + t * 29);   // 30 -> 59
        g = Math.round(58 + t * 72);   // 58 -> 130
        b = Math.round(95 + t * 151);  // 95 -> 246
      }} else {{
        const t = (norm - 0.5) * 2;
        r = Math.round(59 + t * 88);   // 59 -> 147
        g = Math.round(130 + t * 67);  // 130 -> 197
        b = Math.round(246 + t * 7);   // 246 -> 253
      }}
      return 'rgb(' + r + ',' + g + ',' + b + ')';
    }});

    const mx = maxVal;
    let step;
    if (mx > 1000000) step = 500000;
    else if (mx > 100000) step = 50000;
    else if (mx > 10000) step = 5000;
    else if (mx > 1000) step = 500;
    else step = 100;
    const tv = [], tt = [];
    for (let v = 0; v <= mx * 1.25; v += step) {{
      tv.push(v);
      if (v >= 1000000) tt.push((v/1000000).toFixed(v % 1000000 === 0 ? 0 : 1) + 'M');
      else if (v >= 1000) tt.push((v/1000).toFixed(0) + 'K');
      else tt.push(v.toString());
    }}

    Plotly.newPlot('fy24-bar-chart', [{{
      x: values, y: countries, orientation: 'h', type: 'bar',
      marker: {{color: colors, line: {{width: 0}}}},
      text: values.map(v => fmtVal(v)),
      textposition: 'outside',
      textfont: {{color: TEXT_COLOR, size: 10}},
      hovertemplate: '<b>%{{y}}</b><br>' + vt + ': %{{x:,.0f}}<extra></extra>'
    }}], {{
      title: {{text: vt + ' Issuances by Country — FY2024 (Top 20)', font: {{size: 18, color: TEXT_COLOR}}, x: 0.5}},
      xaxis: {{title: 'Visas Issued', gridcolor: GRID_COLOR, color: TEXT_COLOR, tickvals: tv, ticktext: tt}},
      yaxis: {{color: TEXT_COLOR, tickfont: {{size: 10}}}},
      plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
      font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
      hovermode: 'closest', margin: {{l: 170, r: 60, t: 60, b: 45}}
    }}, {{responsive: true, displayModeBar: false}});
  }}

  sel.addEventListener('change', renderFY24);
  renderFY24();
}})();
</script>

<!-- ===== REFUSAL CHART JS (Client-Side Filtering) ===== -->
<script>
(function() {{
  const modeSel = document.getElementById('refusal-mode-select');
  const searchCtrl = document.getElementById('refusal-search-ctrl');
  const countrySel = document.getElementById('refusal-country-select');

  // Populate country dropdown
  REFUSAL_DATA.forEach(d => {{
    const o = document.createElement('option');
    o.value = d.nationality; o.textContent = d.nationality + ' (' + d.rate.toFixed(1) + '%)';
    countrySel.appendChild(o);
  }});

  function renderRefusal() {{
    const mode = modeSel.value;
    searchCtrl.style.display = mode === 'search' ? 'flex' : 'none';

    let chartData, title, barColors, annotations = [];

    if (mode === 'top20') {{
      chartData = REFUSAL_DATA.slice(0, 20).slice().reverse();
      title = 'Top 20 Highest B-Visa Refusal Rates — FY2024';
      const maxRate = Math.max(...chartData.map(d => d.rate), 1);
      barColors = chartData.map(d => {{
        const t = d.rate / maxRate;
        const r = Math.round(59 + t * 180);
        const g = Math.round(130 - t * 62);
        const b = Math.round(246 - t * 178);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
      }});
    }} else if (mode === 'low15') {{
      const filtered = REFUSAL_DATA.filter(d => d.rate > 0);
      chartData = filtered.slice(-15).slice().reverse();
      title = 'Top 15 Lowest B-Visa Refusal Rates — FY2024';
      barColors = chartData.map(() => ACCENT2_COLOR);
    }} else {{
      // Search mode: show top 20 with selected country highlighted
      const country = countrySel.value;
      const idx = REFUSAL_DATA.findIndex(d => d.nationality === country);
      const top20 = REFUSAL_DATA.slice(0, 20);
      const inTop20 = idx >= 0 && idx < 20;

      if (inTop20) {{
        chartData = top20.slice().reverse();
        title = country + ' — Rank #' + (idx + 1) + ' of ' + REFUSAL_DATA.length + ' Countries';
      }} else if (idx >= 0) {{
        // Show top 19 + the selected country inserted at the right position
        const context = top20.slice(0, 19);
        context.push(REFUSAL_DATA[idx]);
        context.sort((a, b) => a.rate - b.rate);
        chartData = context;
        title = country + ' — Rank #' + (idx + 1) + ' of ' + REFUSAL_DATA.length + ' Countries';
      }} else {{
        chartData = top20.slice().reverse();
        title = 'Country not found — showing Top 20';
      }}

      barColors = chartData.map(d => d.nationality === country ? GOLD_COLOR : 'rgba(59,130,246,0.4)');
    }}

    const textLabels = chartData.map(d => d.rate.toFixed(1) + '%');

    Plotly.newPlot('refusal-chart', [{{
      x: chartData.map(d => d.rate),
      y: chartData.map(d => d.nationality),
      orientation: 'h', type: 'bar',
      marker: {{color: barColors, line: {{width: 0}}}},
      text: textLabels,
      textposition: 'outside',
      textfont: {{color: TEXT_COLOR, size: 10}},
      hovertemplate: '<b>%{{y}}</b><br>Refusal Rate: %{{x:.1f}}%<extra></extra>'
    }}], {{
      title: {{text: title, font: {{size: 16, color: TEXT_COLOR}}, x: 0.5}},
      xaxis: {{title: 'Refusal Rate (%)', gridcolor: GRID_COLOR, color: TEXT_COLOR, ticksuffix: '%'}},
      yaxis: {{color: TEXT_COLOR, tickfont: {{size: 10}}}},
      plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
      font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
      height: 560, margin: {{l: 160, r: 60, t: 60, b: 45}},
      annotations: annotations
    }}, {{responsive: true, displayModeBar: false}});
  }}

  modeSel.addEventListener('change', renderRefusal);
  countrySel.addEventListener('change', renderRefusal);
  renderRefusal();
}})();
</script>

<!-- ===== REFUSAL GROUNDS CHART JS ===== -->
<script>
(function() {{
  const modeSel = document.getElementById('grounds-mode-select');

  function fmtK(v) {{
    if (v >= 1000000) return (v/1000000).toFixed(1) + 'M';
    if (v >= 1000) return (v/1000).toFixed(1) + 'K';
    return v.toString();
  }}

  function renderGrounds() {{
    const mode = modeSel.value;
    let chartData, title, barColors, textLabels;

    if (mode === 'top15') {{
      chartData = GROUNDS_DATA.slice(0, 15).slice().reverse();
      title = 'Top 15 NIV Refusal Grounds — FY2024';
      const maxVal = Math.max(...chartData.map(d => d.niv_find), 1);
      const logMax = Math.log10(maxVal);
      barColors = chartData.map(d => {{
        if (d.niv_find <= 0) return '#1E3A5F';
        const norm = Math.log10(Math.max(d.niv_find, 1)) / logMax;
        const r = Math.round(30 + norm * 66);
        const g = Math.round(58 + norm * 107);
        const b = Math.round(95 + norm * 155);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
      }});
      textLabels = chartData.map(d => fmtK(d.niv_find));

      Plotly.newPlot('grounds-chart', [{{
        x: chartData.map(d => d.niv_find),
        y: chartData.map(d => d.ina.substring(0, 25) + (d.ina.length > 25 ? '...' : '')),
        orientation: 'h', type: 'bar',
        marker: {{color: barColors, line: {{width: 0}}}},
        text: textLabels, textposition: 'outside',
        textfont: {{color: TEXT_COLOR, size: 10}},
        hovertemplate: chartData.map(d => '<b>' + d.ina + '</b><br>' + d.desc + '<br>Findings: ' + d.niv_find.toLocaleString() + '<br>Overcome: ' + d.niv_over.toLocaleString() + '<extra></extra>')
      }}], {{
        title: {{text: title, font: {{size: 16, color: TEXT_COLOR}}, x: 0.5}},
        xaxis: {{title: 'NIV Ineligibility Findings', gridcolor: GRID_COLOR, color: TEXT_COLOR}},
        yaxis: {{color: TEXT_COLOR, tickfont: {{size: 9}}}},
        plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
        font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
        height: 520, margin: {{l: 200, r: 70, t: 50, b: 45}}
      }}, {{responsive: true, displayModeBar: false}});

    }} else if (mode === 'top15iv') {{
      chartData = GROUNDS_DATA.filter(d => d.iv_find > 0).sort((a,b) => b.iv_find - a.iv_find).slice(0, 15).reverse();
      title = 'Top 15 Immigrant Visa Refusal Grounds — FY2024';
      barColors = chartData.map(() => ACCENT2_COLOR);
      textLabels = chartData.map(d => fmtK(d.iv_find));

      Plotly.newPlot('grounds-chart', [{{
        x: chartData.map(d => d.iv_find),
        y: chartData.map(d => d.ina.substring(0, 25) + (d.ina.length > 25 ? '...' : '')),
        orientation: 'h', type: 'bar',
        marker: {{color: barColors, line: {{width: 0}}}},
        text: textLabels, textposition: 'outside',
        textfont: {{color: TEXT_COLOR, size: 10}},
        hovertemplate: chartData.map(d => '<b>' + d.ina + '</b><br>' + d.desc + '<br>Findings: ' + d.iv_find.toLocaleString() + '<br>Overcome: ' + d.iv_over.toLocaleString() + '<extra></extra>')
      }}], {{
        title: {{text: title, font: {{size: 16, color: TEXT_COLOR}}, x: 0.5}},
        xaxis: {{title: 'IV Ineligibility Findings', gridcolor: GRID_COLOR, color: TEXT_COLOR}},
        yaxis: {{color: TEXT_COLOR, tickfont: {{size: 9}}}},
        plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
        font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
        height: 520, margin: {{l: 200, r: 70, t: 50, b: 45}}
      }}, {{responsive: true, displayModeBar: false}});

    }} else {{
      // Overcome rates: NIV grounds with >100 findings, sorted by overcome %
      chartData = GROUNDS_DATA.filter(d => d.niv_find >= 100).map(d => ({{
        ...d, overcome_pct: d.niv_over / d.niv_find * 100
      }})).sort((a,b) => b.overcome_pct - a.overcome_pct).slice(0, 15).reverse();
      title = 'NIV Grounds with Highest Overcome Rate — FY2024';
      barColors = chartData.map(d => {{
        const t = d.overcome_pct / 100;
        return 'rgb(' + Math.round(16 + t * 0) + ',' + Math.round(185 * t) + ',' + Math.round(129 * t) + ')';
      }});
      textLabels = chartData.map(d => d.overcome_pct.toFixed(1) + '%');

      Plotly.newPlot('grounds-chart', [{{
        x: chartData.map(d => d.overcome_pct),
        y: chartData.map(d => d.ina.substring(0, 25) + (d.ina.length > 25 ? '...' : '')),
        orientation: 'h', type: 'bar',
        marker: {{color: barColors, line: {{width: 0}}}},
        text: textLabels, textposition: 'outside',
        textfont: {{color: TEXT_COLOR, size: 10}},
        hovertemplate: chartData.map(d => '<b>' + d.ina + '</b><br>' + d.desc + '<br>Findings: ' + d.niv_find.toLocaleString() + '<br>Overcome: ' + d.niv_over.toLocaleString() + ' (' + d.overcome_pct.toFixed(1) + '%)<extra></extra>')
      }}], {{
        title: {{text: title, font: {{size: 16, color: TEXT_COLOR}}, x: 0.5}},
        xaxis: {{title: 'Overcome Rate (%)', gridcolor: GRID_COLOR, color: TEXT_COLOR, ticksuffix: '%'}},
        yaxis: {{color: TEXT_COLOR, tickfont: {{size: 9}}}},
        plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
        font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
        height: 520, margin: {{l: 200, r: 70, t: 50, b: 45}}
      }}, {{responsive: true, displayModeBar: false}});
    }}
  }}

  modeSel.addEventListener('change', renderGrounds);
  renderGrounds();
}})();
</script>

<!-- ===== CONSULAR POSTS CHART JS ===== -->
<script>
(function() {{
  const data = CONSULAR_DATA;
  const reversed = data.slice().reverse();

  const regionColors = {{
    'Africa': '#8B5CF6',
    'East Asia and Pacific': '#06B6D4',
    'Europe and Eurasia': ACCENT_COLOR,
    'Near East': GOLD_COLOR,
    'South and Central Asia': '#EC4899',
    'Western Hemisphere': ACCENT2_COLOR,
    'null': '#71717a'
  }};

  const colors = reversed.map(d => regionColors[d.region] || ACCENT_COLOR);

  function fmtK(v) {{
    if (v >= 1000000) return (v/1000000).toFixed(1) + 'M';
    if (v >= 1000) return (v/1000).toFixed(1) + 'K';
    return v.toString();
  }}

  Plotly.newPlot('consular-chart', [{{
    x: reversed.map(d => d.niv),
    y: reversed.map(d => d.office),
    orientation: 'h', type: 'bar',
    marker: {{color: colors, line: {{width: 0}}}},
    text: reversed.map(d => fmtK(d.niv)),
    textposition: 'outside',
    textfont: {{color: TEXT_COLOR, size: 10}},
    hovertemplate: reversed.map(d => '<b>' + d.office + '</b><br>Region: ' + d.region + '<br>NIV Issued: ' + d.niv.toLocaleString() + '<br>IV Issued: ' + d.iv.toLocaleString() + (d.bcc > 0 ? '<br>Border Cards: ' + d.bcc.toLocaleString() : '') + '<extra></extra>')
  }}], {{
    title: {{text: 'Top 25 Busiest U.S. Consular Posts — NIV Issuances FY2024', font: {{size: 16, color: TEXT_COLOR}}, x: 0.5}},
    xaxis: {{title: 'Nonimmigrant Visas Issued', gridcolor: GRID_COLOR, color: TEXT_COLOR}},
    yaxis: {{color: TEXT_COLOR, tickfont: {{size: 9}}}},
    plot_bgcolor: CARD_BG, paper_bgcolor: 'rgba(0,0,0,0)',
    font: {{color: TEXT_COLOR, family: 'Inter,system-ui,sans-serif'}},
    height: 620, margin: {{l: 200, r: 70, t: 50, b: 45}}
  }}, {{responsive: true, displayModeBar: false}});
}})();
</script>

<!-- ===== HEATMAP TABLE JS ===== -->
<script>
(function() {{
  const tbody = document.getElementById('heatmap-body');
  const visaCols = ['b12', 'h1b', 'f1', 'l1', 'j1'];

  function getColor(rate) {{
    // Green (low) -> Yellow (mid) -> Red (high)
    if (rate <= 10) {{
      const t = rate / 10;
      return 'rgba(16,185,129,' + (0.15 + t * 0.35) + ')';
    }} else if (rate <= 30) {{
      const t = (rate - 10) / 20;
      return 'rgba(245,158,11,' + (0.2 + t * 0.4) + ')';
    }} else {{
      const t = Math.min((rate - 30) / 40, 1);
      return 'rgba(239,68,68,' + (0.25 + t * 0.5) + ')';
    }}
  }}

  function fmtK(v) {{
    if (v >= 1000000) return (v/1000000).toFixed(1) + 'M';
    if (v >= 1000) return Math.round(v/1000) + 'K';
    return v.toString();
  }}

  HEATMAP_DATA.forEach(row => {{
    const tr = document.createElement('tr');
    // Country name
    const tdName = document.createElement('td');
    tdName.textContent = row.country;
    tr.appendChild(tdName);
    // Rate cells
    visaCols.forEach(col => {{
      const td = document.createElement('td');
      const rate = row[col];
      const span = document.createElement('span');
      span.className = 'hm-cell';
      span.style.background = getColor(rate);
      span.style.color = rate > 40 ? '#fff' : (rate > 20 ? '#fff' : '#d4d4d8');
      span.textContent = rate.toFixed(1) + '%';
      td.appendChild(span);
      tr.appendChild(td);
    }});
    // Total issued
    const tdTotal = document.createElement('td');
    tdTotal.style.color = '#d4d4d8';
    tdTotal.style.fontWeight = '600';
    tdTotal.textContent = fmtK(row.grand_total);
    tr.appendChild(tdTotal);
    tbody.appendChild(tr);
  }});
}})();
</script>

<!-- ===== EXPLORER JS ===== -->
<script>
(function() {{
  const DATA = {explorer_json};
  const VT = {visa_types_json};
  const CS = {countries_json};
  const vs = document.getElementById('visa-select');
  const cs = document.getElementById('country-select');
  VT.forEach(v => {{ const o=document.createElement('option'); o.value=v; o.textContent=v; if(v==='H-1B') o.selected=true; vs.appendChild(o); }});
  const dc = ['India','China','Philippines','Mexico','Korea, South'];
  CS.forEach(c => {{ const o=document.createElement('option'); o.value=c; o.textContent=c; if(dc.includes(c)) o.selected=true; cs.appendChild(o); }});
  function render() {{
    const vt=vs.value, sel=Array.from(cs.selectedOptions).map(o=>o.value), vd=DATA[vt]||{{}};
    const traces=sel.map((c,i) => {{
      const cd=vd[c]; if(!cd) return null;
      return {{ x:cd.years, y:cd.values, name:c, mode:'lines+markers',
        line:{{color:CHART_COLORS[i%CHART_COLORS.length],width:2.5}}, marker:{{size:4}},
        hovertemplate:'<b>'+c+'</b><br>FY%{{x}}<br>'+vt+': %{{y:,.0f}}<extra></extra>' }};
    }}).filter(Boolean);
    const allV=traces.flatMap(t=>t.y), mx=Math.max(...allV,1);
    let step; if(mx>100000) step=25000; else if(mx>50000) step=10000; else if(mx>10000) step=5000; else if(mx>1000) step=500; else step=100;
    const tv=[],tt=[]; for(let v=0;v<=mx*1.15;v+=step) {{ tv.push(v); tt.push(v>=1000?(v/1000).toFixed(v%1000===0?0:1)+'K':v.toString()); }}
    Plotly.newPlot('explorer-chart',traces,{{
      title:{{text:vt+' Visa Issuances Over Time',font:{{size:18,color:TEXT_COLOR}},x:0.5}},
      xaxis:{{title:'Fiscal Year',gridcolor:GRID_COLOR,dtick:2,color:TEXT_COLOR}},
      yaxis:{{title:vt+' Visas Issued',gridcolor:GRID_COLOR,color:TEXT_COLOR,tickvals:tv,ticktext:tt}},
      plot_bgcolor:CARD_BG,paper_bgcolor:'rgba(0,0,0,0)',
      font:{{color:TEXT_COLOR,family:'Inter,system-ui,sans-serif'}},
      legend:{{bgcolor:'rgba(24,24,27,0.9)',bordercolor:GRID_COLOR,borderwidth:1,font:{{size:10}}}},
      hovermode:'x unified', margin:{{l:65,r:25,t:55,b:45}}, height:460
    }},{{responsive:true,displayModeBar:false}});
  }}
  vs.addEventListener('change',render); cs.addEventListener('change',render); render();
}})();
</script>

</body>
</html>"""
    return html


def main():
    """Build V6 dashboard."""
    print("Fetching data from DuckDB...")
    data = fetch_all_data()

    print("Building charts...")
    charts = {
        "h1b": chart_h1b_top10(data["df_h1b"]),
        "india_china": chart_india_china(data["df_ivc"]),
        "workload": chart_workload(data["df_workload"]),
        "bvisa_wl": chart_bvisa_workload(data["df_bvisa_wl"]),
    }

    print("Generating HTML...")
    html = build_html(data, charts)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html)

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\nDashboard V6 saved to {OUTPUT_PATH}")
    print(f"File size: {size_kb:.0f} KB")
    print("Done.")


if __name__ == "__main__":
    main()

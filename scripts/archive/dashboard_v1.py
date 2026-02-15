"""
US Immigration Visa Dashboard
Generates a dark-themed Plotly dashboard from DuckDB visa_issuances data.
Outputs: docs/dashboard.html (GitHub Pages ready)
"""

import duckdb
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# -- Config --
DB_PATH = Path(__file__).parent.parent / "database" / "immigration.duckdb"
OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "dashboard.html"

# Color palette — professional, accessible, visually distinct
COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
    "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
]

BG_COLOR = "#0f0f0f"
CARD_COLOR = "#1a1a2e"
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#2a2a3e"


def get_connection():
    """Connect to the immigration DuckDB database."""
    return duckdb.connect(str(DB_PATH), read_only=True)


def query_h1b_top10(con):
    """Get H-1B visa counts over time for the top 10 countries by total issuances."""
    return con.execute("""
        WITH top_countries AS (
            SELECT country, SUM("H-1B") as total
            FROM visa_issuances
            GROUP BY country
            ORDER BY total DESC
            LIMIT 10
        )
        SELECT v.fiscal_year, v.country, v."H-1B" as h1b_count
        FROM visa_issuances v
        INNER JOIN top_countries t ON v.country = t.country
        ORDER BY v.country, v.fiscal_year
    """).fetchdf()


def query_total_niv_fy2024(con):
    """Get total NIV issuances by country for FY2024, top 20."""
    return con.execute("""
        SELECT country, "Grand Total" as total_visas
        FROM visa_issuances
        WHERE fiscal_year = 2024
        ORDER BY total_visas DESC
        LIMIT 20
    """).fetchdf()


def query_india_vs_china(con):
    """Get H-1B counts for India and China over time."""
    return con.execute("""
        SELECT fiscal_year, country, "H-1B" as h1b_count
        FROM visa_issuances
        WHERE country IN ('India', 'China - mainland')
        ORDER BY country, fiscal_year
    """).fetchdf()


def build_h1b_top10_chart(df):
    """Chart 1: H-1B visas over time for top 10 countries."""
    fig = go.Figure()

    for i, country in enumerate(df["country"].unique()):
        country_df = df[df["country"] == country]
        fig.add_trace(go.Scatter(
            x=country_df["fiscal_year"],
            y=country_df["h1b_count"],
            name=country,
            mode="lines+markers",
            line=dict(color=COLORS[i % len(COLORS)], width=2.5),
            marker=dict(size=5),
            hovertemplate=f"<b>{country}</b><br>"
                          "FY%{x}<br>"
                          "H-1B Visas: %{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text="H-1B Visa Issuances by Country (FY1997–2024)",
            font=dict(size=22, color=TEXT_COLOR),
            x=0.5,
        ),
        xaxis=dict(
            title="Fiscal Year",
            gridcolor=GRID_COLOR,
            dtick=2,
            color=TEXT_COLOR,
        ),
        yaxis=dict(
            title="H-1B Visas Issued",
            gridcolor=GRID_COLOR,
            color=TEXT_COLOR,
            tickformat=",",
        ),
        plot_bgcolor=CARD_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        legend=dict(
            bgcolor="rgba(26,26,46,0.8)",
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(size=11),
        ),
        hovermode="x unified",
        margin=dict(l=60, r=30, t=70, b=50),
        height=520,
    )
    return fig


def build_niv_fy2024_chart(df):
    """Chart 2: Total NIV issuances by country for FY2024 (bar chart, top 20)."""
    df_sorted = df.sort_values("total_visas", ascending=True)

    fig = go.Figure(go.Bar(
        x=df_sorted["total_visas"],
        y=df_sorted["country"],
        orientation="h",
        marker=dict(
            color=df_sorted["total_visas"],
            colorscale=[[0, "#1a1a5e"], [0.5, "#636EFA"], [1, "#00CC96"]],
            line=dict(width=0),
        ),
        hovertemplate="<b>%{y}</b><br>"
                      "Total Visas: %{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="Total NIV Issuances by Country — FY2024 (Top 20)",
            font=dict(size=22, color=TEXT_COLOR),
            x=0.5,
        ),
        xaxis=dict(
            title="Total Visas Issued",
            gridcolor=GRID_COLOR,
            color=TEXT_COLOR,
            tickformat=",",
        ),
        yaxis=dict(
            color=TEXT_COLOR,
            tickfont=dict(size=11),
        ),
        plot_bgcolor=CARD_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        margin=dict(l=160, r=30, t=70, b=50),
        height=600,
    )
    return fig


def build_india_vs_china_chart(df):
    """Chart 3: India vs China H-1B comparison over time."""
    fig = go.Figure()

    config = {
        "India": {"color": "#EF553B", "emoji": "🇮🇳"},
        "China - mainland": {"color": "#636EFA", "emoji": "🇨🇳"},
    }

    for country in ["India", "China - mainland"]:
        cdf = df[df["country"] == country]
        label = country.replace(" - mainland", "")
        fig.add_trace(go.Scatter(
            x=cdf["fiscal_year"],
            y=cdf["h1b_count"],
            name=f"{config[country]['emoji']} {label}",
            mode="lines+markers",
            line=dict(color=config[country]["color"], width=3),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor=f"rgba({','.join(str(int(config[country]['color'][i:i+2], 16)) for i in (1, 3, 5))}, 0.1)",
            hovertemplate=f"<b>{label}</b><br>"
                          "FY%{x}<br>"
                          "H-1B Visas: %{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text="India vs China — H-1B Visa Issuances (FY1997–2024)",
            font=dict(size=22, color=TEXT_COLOR),
            x=0.5,
        ),
        xaxis=dict(
            title="Fiscal Year",
            gridcolor=GRID_COLOR,
            dtick=2,
            color=TEXT_COLOR,
        ),
        yaxis=dict(
            title="H-1B Visas Issued",
            gridcolor=GRID_COLOR,
            color=TEXT_COLOR,
            tickformat=",",
        ),
        plot_bgcolor=CARD_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        legend=dict(
            bgcolor="rgba(26,26,46,0.8)",
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(size=14),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        hovermode="x unified",
        margin=dict(l=60, r=30, t=90, b=50),
        height=480,
    )
    return fig


def build_html(fig1, fig2, fig3):
    """Combine all 3 charts into a single styled HTML page."""
    chart1_html = fig1.to_html(full_html=False, include_plotlyjs=False)
    chart2_html = fig2.to_html(full_html=False, include_plotlyjs=False)
    chart3_html = fig3.to_html(full_html=False, include_plotlyjs=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>US Immigration Visa Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: {BG_COLOR};
            color: {TEXT_COLOR};
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            padding: 0;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            padding: 40px 20px 30px;
            text-align: center;
            border-bottom: 2px solid #636EFA;
        }}
        .header h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}
        .header p {{
            font-size: 1rem;
            color: #8892b0;
            max-width: 600px;
            margin: 0 auto;
        }}
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px 60px;
        }}
        .chart-card {{
            background: {CARD_COLOR};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid {GRID_COLOR};
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            transition: box-shadow 0.3s ease;
        }}
        .chart-card:hover {{
            box-shadow: 0 6px 30px rgba(99, 110, 250, 0.15);
        }}
        .footer {{
            text-align: center;
            padding: 30px 20px;
            color: #555;
            font-size: 0.85rem;
            border-top: 1px solid {GRID_COLOR};
        }}
        .footer a {{ color: #636EFA; text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 40px;
            padding: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            text-align: center;
        }}
        .stat .number {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #636EFA;
        }}
        .stat .label {{
            font-size: 0.8rem;
            color: #8892b0;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>US Immigration Visa Dashboard</h1>
        <p>Nonimmigrant visa issuance trends from the US Department of State, FY1997–2024</p>
        <div class="stats-bar">
            <div class="stat">
                <div class="number">5,564</div>
                <div class="label">Data Points</div>
            </div>
            <div class="stat">
                <div class="number">215</div>
                <div class="label">Countries</div>
            </div>
            <div class="stat">
                <div class="number">28</div>
                <div class="label">Fiscal Years</div>
            </div>
            <div class="stat">
                <div class="number">96</div>
                <div class="label">Visa Types</div>
            </div>
        </div>
    </div>

    <div class="dashboard">
        <div class="chart-card">
            {chart1_html}
        </div>
        <div class="chart-card">
            {chart2_html}
        </div>
        <div class="chart-card">
            {chart3_html}
        </div>
    </div>

    <div class="footer">
        Built with DuckDB + Plotly | Data: US Department of State |
        <a href="https://github.com/PranavOngole/Project-00">GitHub</a>
    </div>
</body>
</html>"""
    return html


def main():
    """Build and export the dashboard."""
    print("Connecting to DuckDB...")
    con = get_connection()

    print("Querying H-1B top 10 countries...")
    df_h1b = query_h1b_top10(con)

    print("Querying FY2024 total NIV issuances...")
    df_niv = query_total_niv_fy2024(con)

    print("Querying India vs China H-1B...")
    df_ivc = query_india_vs_china(con)

    con.close()

    print("Building charts...")
    fig1 = build_h1b_top10_chart(df_h1b)
    fig2 = build_niv_fy2024_chart(df_niv)
    fig3 = build_india_vs_china_chart(df_ivc)

    print("Generating HTML...")
    html = build_html(fig1, fig2, fig3)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html)
    print(f"Dashboard saved to {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

"""
US Immigration Visa Dashboard — V2
Generates a dark-themed, interactive Plotly dashboard from DuckDB visa_issuances data.
Features: visa type dropdown, country selector, insight callouts, axes in thousands.
Outputs: docs/dashboard.html (GitHub Pages ready)
"""

import json
import duckdb
import plotly.graph_objects as go
from pathlib import Path

# -- Config --
DB_PATH = Path(__file__).parent.parent / "database" / "immigration.duckdb"
OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "dashboard.html"

COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
    "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
]

BG_COLOR = "#0f0f0f"
CARD_COLOR = "#1a1a2e"
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#2a2a3e"
ACCENT = "#636EFA"
ACCENT2 = "#00CC96"


def get_connection():
    """Connect to the immigration DuckDB database."""
    return duckdb.connect(str(DB_PATH), read_only=True)


def get_visa_type_columns(con):
    """Get all visa type column names (excluding metadata columns)."""
    cols = con.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'visa_issuances'
        AND column_name NOT IN ('fiscal_year', 'country', 'Total Visas', 'BCC', 'Grand Total')
        ORDER BY ordinal_position
    """).fetchall()
    return [c[0] for c in cols]


def get_top_countries(con, n=30):
    """Get top N countries by all-time grand total visas."""
    rows = con.execute(f"""
        SELECT country FROM visa_issuances
        GROUP BY country ORDER BY SUM("Grand Total") DESC LIMIT {n}
    """).fetchall()
    return [r[0] for r in rows]


def query_all_visa_data(con, visa_types, countries):
    """Query full dataset for all visa types and top countries for client-side interactivity."""
    quoted_cols = ", ".join(f'"{vt}"' for vt in visa_types)
    country_list = ", ".join(f"'{c}'" for c in countries)
    df = con.execute(f"""
        SELECT fiscal_year, country, {quoted_cols}
        FROM visa_issuances
        WHERE country IN ({country_list})
        ORDER BY country, fiscal_year
    """).fetchdf()
    return df


def query_h1b_top10(con):
    """Get H-1B visa counts over time for the top 10 countries by total H-1B issuances."""
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
        ORDER BY t.total DESC, v.fiscal_year
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
        WHERE country IN ('India', 'China')
        ORDER BY country, fiscal_year
    """).fetchdf()


def query_insights(con):
    """Get key stats for the insight callout banner."""
    rows = con.execute("""
        SELECT country, "H-1B"
        FROM visa_issuances
        WHERE fiscal_year = 2024 AND country IN ('India', 'China')
        ORDER BY country
    """).fetchall()
    # Build a dict so order doesn't matter
    vals = {r[0]: r[1] for r in rows}
    india_val = vals["India"]
    china_val = vals["China"]
    ratio = india_val / china_val if china_val > 0 else 0

    peak = con.execute("""
        SELECT fiscal_year, SUM("H-1B") as total
        FROM visa_issuances GROUP BY fiscal_year ORDER BY total DESC LIMIT 1
    """).fetchone()

    total_h1b = con.execute('SELECT SUM("H-1B") FROM visa_issuances').fetchone()[0]

    return {
        "india_2024": india_val,
        "china_2024": china_val,
        "ratio": ratio,
        "peak_year": peak[0],
        "peak_total": peak[1],
        "total_h1b_alltime": total_h1b,
    }


def build_h1b_top10_chart(df):
    """Chart 1: H-1B visas over time for top 10 countries with country selector."""
    fig = go.Figure()
    countries = df["country"].unique()

    for i, country in enumerate(countries):
        cdf = df[df["country"] == country]
        fig.add_trace(go.Scatter(
            x=cdf["fiscal_year"].tolist(),
            y=cdf["h1b_count"].tolist(),
            name=country,
            mode="lines+markers",
            line=dict(color=COLORS[i % len(COLORS)], width=2.5),
            marker=dict(size=5),
            hovertemplate=(
                f"<b>{country}</b><br>"
                "FY%{x}<br>"
                "H-1B Visas: %{y:,.0f}<extra></extra>"
            ),
        ))

    # Add dropdown buttons to toggle countries
    buttons = [dict(label="All Top 10", method="update",
                     args=[{"visible": [True] * len(countries)}])]
    for i, country in enumerate(countries):
        visibility = [False] * len(countries)
        visibility[i] = True
        buttons.append(dict(label=country, method="update",
                            args=[{"visible": visibility}]))

    fig.update_layout(
        title=dict(text="H-1B Visa Issuances by Country (FY1997–2024)", font=dict(size=22, color=TEXT_COLOR), x=0.5),
        updatemenus=[dict(
            buttons=buttons,
            direction="down",
            showactive=True,
            x=0.0, xanchor="left", y=1.18, yanchor="top",
            bgcolor=CARD_COLOR,
            bordercolor=GRID_COLOR,
            font=dict(color=TEXT_COLOR, size=11),
            active=0,
        )],
        xaxis=dict(title="Fiscal Year", gridcolor=GRID_COLOR, dtick=2, color=TEXT_COLOR),
        yaxis=dict(
            title="H-1B Visas Issued (Thousands)",
            gridcolor=GRID_COLOR, color=TEXT_COLOR,
            tickformat=",", ticksuffix="",
            # Show in thousands
            tickvals=list(range(0, 200001, 25000)),
            ticktext=[f"{v // 1000}K" for v in range(0, 200001, 25000)],
        ),
        plot_bgcolor=CARD_COLOR, paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        legend=dict(bgcolor="rgba(26,26,46,0.8)", bordercolor=GRID_COLOR, borderwidth=1, font=dict(size=11)),
        hovermode="x unified",
        margin=dict(l=70, r=30, t=100, b=50),
        height=560,
    )
    return fig


def build_niv_fy2024_chart(df):
    """Chart 2: Total NIV issuances by country for FY2024 (horizontal bar, top 20)."""
    df_sorted = df.sort_values("total_visas", ascending=True)

    fig = go.Figure(go.Bar(
        x=df_sorted["total_visas"].tolist(),
        y=df_sorted["country"].tolist(),
        orientation="h",
        marker=dict(
            color=df_sorted["total_visas"].tolist(),
            colorscale=[[0, "#1a1a5e"], [0.35, "#636EFA"], [0.7, "#00CC96"], [1.0, "#FECB52"]],
            line=dict(width=0),
        ),
        hovertemplate="<b>%{y}</b><br>Total Visas: %{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Total NIV Issuances by Country — FY2024 (Top 20)", font=dict(size=22, color=TEXT_COLOR), x=0.5),
        xaxis=dict(
            title="Total Visas Issued (Thousands)",
            gridcolor=GRID_COLOR, color=TEXT_COLOR,
            tickvals=list(range(0, 3500001, 500000)),
            ticktext=[f"{v // 1000}K" for v in range(0, 3500001, 500000)],
        ),
        yaxis=dict(color=TEXT_COLOR, tickfont=dict(size=11)),
        plot_bgcolor=CARD_COLOR, paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        margin=dict(l=180, r=40, t=70, b=50),
        height=620,
    )
    return fig


def build_india_vs_china_chart(df):
    """Chart 3: India vs China H-1B comparison over time (filled line chart)."""
    fig = go.Figure()

    config = {
        "India": {"color": "#EF553B", "fill_rgba": "rgba(239,85,59,0.15)"},
        "China": {"color": "#636EFA", "fill_rgba": "rgba(99,110,250,0.15)"},
    }

    for country in ["India", "China"]:
        cdf = df[df["country"] == country]
        label = country.replace("", "")
        fig.add_trace(go.Scatter(
            x=cdf["fiscal_year"].tolist(),
            y=cdf["h1b_count"].tolist(),
            name=label,
            mode="lines+markers",
            line=dict(color=config[country]["color"], width=3),
            marker=dict(size=7),
            fill="tozeroy",
            fillcolor=config[country]["fill_rgba"],
            hovertemplate=(
                f"<b>{label}</b><br>"
                "FY%{x}<br>"
                "H-1B Visas: %{y:,.0f}<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=dict(text="India vs China — H-1B Visa Issuances (FY1997–2024)", font=dict(size=22, color=TEXT_COLOR), x=0.5),
        xaxis=dict(title="Fiscal Year", gridcolor=GRID_COLOR, dtick=2, color=TEXT_COLOR),
        yaxis=dict(
            title="H-1B Visas Issued (Thousands)",
            gridcolor=GRID_COLOR, color=TEXT_COLOR,
            tickvals=list(range(0, 200001, 25000)),
            ticktext=[f"{v // 1000}K" for v in range(0, 200001, 25000)],
        ),
        plot_bgcolor=CARD_COLOR, paper_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="Inter, system-ui, sans-serif"),
        legend=dict(
            bgcolor="rgba(26,26,46,0.8)", bordercolor=GRID_COLOR, borderwidth=1,
            font=dict(size=14), orientation="h",
            yanchor="bottom", y=1.02, xanchor="center", x=0.5,
        ),
        hovermode="x unified",
        margin=dict(l=70, r=30, t=90, b=50),
        height=500,
    )
    return fig


def prepare_explorer_data(full_df, visa_types, countries):
    """Prepare JSON data for the client-side visa type explorer chart."""
    data = {}
    for vt in visa_types:
        data[vt] = {}
        for country in countries:
            cdf = full_df[full_df["country"] == country]
            values = cdf[vt].tolist()
            if any(v > 0 for v in values):
                data[vt][country] = {
                    "years": cdf["fiscal_year"].tolist(),
                    "values": values,
                }
    return data


def build_html(fig1, fig2, fig3, insights, explorer_data, visa_types, countries):
    """Combine all charts + interactive explorer into a single styled HTML page."""
    chart1_html = fig1.to_html(full_html=False, include_plotlyjs=False)
    chart2_html = fig2.to_html(full_html=False, include_plotlyjs=False)
    chart3_html = fig3.to_html(full_html=False, include_plotlyjs=False)

    explorer_json = json.dumps(explorer_data)
    visa_types_json = json.dumps(visa_types)
    countries_json = json.dumps(countries)

    india_k = f"{insights['india_2024'] // 1000}K"
    china_k = f"{insights['china_2024'] // 1000}K"
    ratio_str = f"{insights['ratio']:.1f}x"
    peak_k = f"{insights['peak_total'] // 1000}K"
    total_m = f"{insights['total_h1b_alltime'] / 1_000_000:.1f}M"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>US Immigration Visa Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            background: {BG_COLOR};
            color: {TEXT_COLOR};
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }}

        /* --- Header --- */
        .header {{
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 40%, #0f3460 100%);
            padding: 48px 20px 36px;
            text-align: center;
            border-bottom: 3px solid {ACCENT};
            position: relative;
            overflow: hidden;
        }}
        .header::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(ellipse at 50% 0%, rgba(99,110,250,0.12) 0%, transparent 60%);
            pointer-events: none;
        }}
        .header h1 {{
            font-size: 2.6rem;
            font-weight: 800;
            color: #fff;
            margin-bottom: 8px;
            letter-spacing: -1px;
        }}
        .header .subtitle {{
            font-size: 1.05rem;
            color: #8892b0;
            max-width: 650px;
            margin: 0 auto 24px;
            font-weight: 300;
        }}

        /* --- Stats Bar --- */
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 48px;
            padding: 16px 0;
            flex-wrap: wrap;
        }}
        .stat {{ text-align: center; }}
        .stat .number {{
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, {ACCENT}, {ACCENT2});
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .stat .label {{
            font-size: 0.75rem;
            color: #6a7490;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 4px;
            font-weight: 600;
        }}

        /* --- Insight Banner --- */
        .insight-banner {{
            max-width: 1200px;
            margin: 28px auto 0;
            padding: 0 20px;
        }}
        .insight-card {{
            background: linear-gradient(135deg, rgba(99,110,250,0.1) 0%, rgba(0,204,150,0.08) 100%);
            border: 1px solid rgba(99,110,250,0.3);
            border-radius: 14px;
            padding: 24px 32px;
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .insight-icon {{
            font-size: 2.4rem;
            flex-shrink: 0;
        }}
        .insight-text {{
            flex: 1;
            min-width: 200px;
        }}
        .insight-text .headline {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 4px;
        }}
        .insight-text .detail {{
            font-size: 0.9rem;
            color: #8892b0;
            line-height: 1.5;
        }}
        .insight-text .detail strong {{
            color: {ACCENT};
        }}
        .insight-pills {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .pill {{
            background: rgba(99,110,250,0.15);
            border: 1px solid rgba(99,110,250,0.25);
            border-radius: 20px;
            padding: 8px 18px;
            text-align: center;
            min-width: 100px;
        }}
        .pill .pill-value {{
            font-size: 1.1rem;
            font-weight: 700;
            color: #fff;
        }}
        .pill .pill-label {{
            font-size: 0.65rem;
            color: #6a7490;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 2px;
        }}

        /* --- Dashboard --- */
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 28px 20px 60px;
        }}

        .chart-card {{
            background: {CARD_COLOR};
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 28px;
            border: 1px solid {GRID_COLOR};
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
            transition: box-shadow 0.3s ease, border-color 0.3s ease;
        }}
        .chart-card:hover {{
            box-shadow: 0 8px 40px rgba(99, 110, 250, 0.12);
            border-color: rgba(99, 110, 250, 0.3);
        }}

        .chart-section-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: {ACCENT};
            font-weight: 700;
            margin-bottom: 12px;
        }}

        /* --- Explorer Controls --- */
        .explorer-controls {{
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
            flex-wrap: wrap;
            align-items: end;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .control-group label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #6a7490;
            font-weight: 600;
        }}
        .control-group select {{
            background: #12122a;
            color: {TEXT_COLOR};
            border: 1px solid {GRID_COLOR};
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 0.9rem;
            font-family: inherit;
            cursor: pointer;
            min-width: 200px;
            appearance: auto;
        }}
        .control-group select:focus {{
            outline: none;
            border-color: {ACCENT};
            box-shadow: 0 0 0 2px rgba(99,110,250,0.2);
        }}
        .control-group select[multiple] {{
            min-height: 120px;
        }}

        /* --- Footer --- */
        .footer {{
            text-align: center;
            padding: 32px 20px;
            color: #444;
            font-size: 0.85rem;
            border-top: 1px solid {GRID_COLOR};
            max-width: 1200px;
            margin: 0 auto;
        }}
        .footer a {{ color: {ACCENT}; text-decoration: none; }}
        .footer a:hover {{ text-decoration: underline; }}

        /* --- Responsive --- */
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.8rem; }}
            .stats-bar {{ gap: 24px; }}
            .stat .number {{ font-size: 1.5rem; }}
            .insight-card {{ flex-direction: column; text-align: center; }}
            .explorer-controls {{ flex-direction: column; }}
            .control-group select {{ min-width: 100%; }}
        }}
    </style>
</head>
<body>

    <!-- ====== HEADER ====== -->
    <div class="header">
        <h1>US Immigration Visa Dashboard</h1>
        <p class="subtitle">Nonimmigrant visa issuance trends from the U.S. Department of State — FY1997 to FY2024</p>
        <div class="stats-bar">
            <div class="stat"><div class="number">5,564</div><div class="label">Data Points</div></div>
            <div class="stat"><div class="number">215</div><div class="label">Countries</div></div>
            <div class="stat"><div class="number">28</div><div class="label">Fiscal Years</div></div>
            <div class="stat"><div class="number">93</div><div class="label">Visa Types</div></div>
        </div>
    </div>

    <!-- ====== INSIGHT BANNER ====== -->
    <div class="insight-banner">
        <div class="insight-card">
            <div class="insight-icon">&#x1f4ca;</div>
            <div class="insight-text">
                <div class="headline">India dominates H-1B at {ratio_str} China's volume</div>
                <div class="detail">
                    In FY2024, India received <strong>{india_k}</strong> H-1B visas vs China's <strong>{china_k}</strong>.
                    Peak H-1B year globally was <strong>FY{insights['peak_year']}</strong> with <strong>{peak_k}</strong> total issuances.
                </div>
            </div>
            <div class="insight-pills">
                <div class="pill"><div class="pill-value">{india_k}</div><div class="pill-label">India FY24</div></div>
                <div class="pill"><div class="pill-value">{china_k}</div><div class="pill-label">China FY24</div></div>
                <div class="pill"><div class="pill-value">{total_m}</div><div class="pill-label">H-1B All-Time</div></div>
            </div>
        </div>
    </div>

    <!-- ====== DASHBOARD ====== -->
    <div class="dashboard">

        <!-- Chart 1: H-1B Top 10 with Country Selector -->
        <div class="chart-card">
            <div class="chart-section-label">Chart 1 &mdash; H-1B Trends</div>
            {chart1_html}
        </div>

        <!-- Chart 2: FY2024 NIV Bar -->
        <div class="chart-card">
            <div class="chart-section-label">Chart 2 &mdash; FY2024 Overview</div>
            {chart2_html}
        </div>

        <!-- Chart 3: India vs China -->
        <div class="chart-card">
            <div class="chart-section-label">Chart 3 &mdash; Head to Head</div>
            {chart3_html}
        </div>

        <!-- Chart 4: Visa Type Explorer -->
        <div class="chart-card">
            <div class="chart-section-label">Explorer &mdash; Any Visa Type, Any Country</div>
            <div class="explorer-controls">
                <div class="control-group">
                    <label>Visa Type</label>
                    <select id="visa-select"></select>
                </div>
                <div class="control-group">
                    <label>Countries (hold Cmd/Ctrl to multi-select)</label>
                    <select id="country-select" multiple></select>
                </div>
            </div>
            <div id="explorer-chart"></div>
        </div>

    </div>

    <!-- ====== FOOTER ====== -->
    <div class="footer">
        Built with DuckDB + Plotly by <strong>Pranav Ongole</strong> |
        Data: U.S. Department of State |
        <a href="https://github.com/PranavOngole/Project-00">View on GitHub</a>
    </div>

    <!-- ====== EXPLORER SCRIPT ====== -->
    <script>
    (function() {{
        const DATA = {explorer_json};
        const VISA_TYPES = {visa_types_json};
        const COUNTRIES = {countries_json};
        const COLORS = {json.dumps(COLORS)};

        const visaSelect = document.getElementById('visa-select');
        const countrySelect = document.getElementById('country-select');

        // Populate dropdowns
        VISA_TYPES.forEach(vt => {{
            const opt = document.createElement('option');
            opt.value = vt;
            opt.textContent = vt;
            if (vt === 'H-1B') opt.selected = true;
            visaSelect.appendChild(opt);
        }});

        const defaultCountries = ['India', 'China', 'Philippines', 'Mexico', 'Korea, South'];
        COUNTRIES.forEach(c => {{
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            if (defaultCountries.includes(c)) opt.selected = true;
            countrySelect.appendChild(opt);
        }});

        function renderExplorer() {{
            const vt = visaSelect.value;
            const selected = Array.from(countrySelect.selectedOptions).map(o => o.value);
            const vtData = DATA[vt] || {{}};

            const traces = selected.map((country, i) => {{
                const cd = vtData[country];
                if (!cd) return null;
                return {{
                    x: cd.years,
                    y: cd.values,
                    name: country,
                    mode: 'lines+markers',
                    line: {{ color: COLORS[i % COLORS.length], width: 2.5 }},
                    marker: {{ size: 5 }},
                    hovertemplate: '<b>' + country + '</b><br>FY%{{x}}<br>' + vt + ': %{{y:,.0f}}<extra></extra>',
                }};
            }}).filter(Boolean);

            const layout = {{
                title: {{ text: vt + ' Visa Issuances Over Time', font: {{ size: 20, color: '{TEXT_COLOR}' }}, x: 0.5 }},
                xaxis: {{ title: 'Fiscal Year', gridcolor: '{GRID_COLOR}', dtick: 2, color: '{TEXT_COLOR}' }},
                yaxis: {{ title: vt + ' Visas Issued (Thousands)', gridcolor: '{GRID_COLOR}', color: '{TEXT_COLOR}', tickformat: ',.0f',
                    tickprefix: '', ticksuffix: '' }},
                plot_bgcolor: '{CARD_COLOR}',
                paper_bgcolor: '{BG_COLOR}',
                font: {{ color: '{TEXT_COLOR}', family: 'Inter, system-ui, sans-serif' }},
                legend: {{ bgcolor: 'rgba(26,26,46,0.8)', bordercolor: '{GRID_COLOR}', borderwidth: 1, font: {{ size: 11 }} }},
                hovermode: 'x unified',
                margin: {{ l: 70, r: 30, t: 60, b: 50 }},
                height: 480,
            }};

            // Calculate smart tick values based on max
            const allValues = traces.flatMap(t => t.y);
            const maxVal = Math.max(...allValues, 1);
            let step;
            if (maxVal > 100000) step = 25000;
            else if (maxVal > 50000) step = 10000;
            else if (maxVal > 10000) step = 5000;
            else if (maxVal > 1000) step = 500;
            else step = 100;

            const tickVals = [];
            const tickTexts = [];
            for (let v = 0; v <= maxVal * 1.1; v += step) {{
                tickVals.push(v);
                tickTexts.push(v >= 1000 ? (v / 1000).toFixed(v % 1000 === 0 ? 0 : 1) + 'K' : v.toString());
            }}
            layout.yaxis.tickvals = tickVals;
            layout.yaxis.ticktext = tickTexts;

            Plotly.newPlot('explorer-chart', traces, layout, {{ responsive: true, displayModeBar: false }});
        }}

        visaSelect.addEventListener('change', renderExplorer);
        countrySelect.addEventListener('change', renderExplorer);

        renderExplorer();
    }})();
    </script>

</body>
</html>"""
    return html


def main():
    """Build and export the V2 dashboard."""
    print("Connecting to DuckDB...")
    con = get_connection()

    print("Fetching schema metadata...")
    visa_types = get_visa_type_columns(con)
    countries = get_top_countries(con, n=30)
    print(f"  {len(visa_types)} visa types, {len(countries)} countries for explorer")

    print("Querying H-1B top 10...")
    df_h1b = query_h1b_top10(con)

    print("Querying FY2024 NIV totals...")
    df_niv = query_total_niv_fy2024(con)

    print("Querying India vs China...")
    df_ivc = query_india_vs_china(con)

    print("Querying insight stats...")
    insights = query_insights(con)
    print(f"  India FY2024: {insights['india_2024']:,} | China: {insights['china_2024']:,} | Ratio: {insights['ratio']:.1f}x")

    print("Querying full dataset for explorer...")
    full_df = query_all_visa_data(con, visa_types, countries)
    print(f"  {len(full_df)} rows loaded for interactive explorer")

    con.close()

    print("Building charts...")
    fig1 = build_h1b_top10_chart(df_h1b)
    fig2 = build_niv_fy2024_chart(df_niv)
    fig3 = build_india_vs_china_chart(df_ivc)

    print("Preparing explorer data...")
    explorer_data = prepare_explorer_data(full_df, visa_types, countries)

    print("Generating HTML...")
    html = build_html(fig1, fig2, fig3, insights, explorer_data, visa_types, countries)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html)

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\nDashboard V2 saved to {OUTPUT_PATH}")
    print(f"File size: {size_kb:.0f} KB")
    print("Done.")


if __name__ == "__main__":
    main()

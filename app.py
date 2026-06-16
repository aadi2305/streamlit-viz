import json
import os
import urllib.parse
import requests
import streamlit as st
import plotly.express as px
import pandas as pd
from utils.table_renderer import render_dynamic_table

# Set CACHE_API_URL in Streamlit Cloud secrets or as an env var.
# Locally it defaults to http://localhost:8000 (run cache_server.py separately).
CACHE_API_URL = os.getenv("CACHE_API_URL", st.secrets.get("CACHE_API_URL", "http://localhost:8000"))

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Syngenta Data Viz",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------

SAMPLE_PAYLOAD = {
    "data": [
        {"state": "Andhra Pradesh", "territory": "Guntur",    "revenue": 450000, "orders": 120, "growers": 45},
        {"state": "Andhra Pradesh", "territory": "Krishna",   "revenue": 520000, "orders": 145, "growers": 52},
        {"state": "Telangana",      "territory": "Hyderabad", "revenue": 680000, "orders": 190, "growers": 67},
        {"state": "Telangana",      "territory": "Warangal",  "revenue": 380000, "orders": 98,  "growers": 38},
        {"state": "Karnataka",      "territory": "Bangalore", "revenue": 590000, "orders": 160, "growers": 58},
    ],
    "config": {
        "title": "Territory Performance (Sample)",
        "theme": "syngenta",
        "density": "default",
        "alternateRows": True,
        "columns": [
            {"id": "state",     "label": "State",     "width": "130px"},
            {"id": "territory", "label": "Territory",  "width": "150px"},
            {"id": "revenue",   "label": "Revenue",    "format": "currency_INR", "align": "right"},
            {"id": "orders",    "label": "Orders",     "format": "number",       "align": "center"},
            {"id": "growers",   "label": "Growers",    "format": "number",       "align": "center"},
        ],
        "groupBy": {
            "column": "state",
            "subtotals": {"columns": ["revenue", "orders"], "function": "sum"},
        },
        "totalsRow": {
            "columns": ["revenue", "orders", "growers"],
            "function": "sum",
            "label": "Grand Total",
        },
        "conditionalFormatting": {
            "rules": [
                {"column": "revenue", "condition": ">500000", "style": {"bg": "#d4edda", "bold": True}},
                {"column": "revenue", "condition": "<400000", "style": {"bg": "#f8d7da"}},
            ]
        },
        "interactivity": {
            "searchable": True,
            "exportable": True,
        },
    },
}


def _fetch_from_cache(cache_id: str):
    """Fetch payload from FastAPI sidecar by cache_id. Returns dict or None."""
    try:
        r = requests.get(f"{CACHE_API_URL}/api/cache/{cache_id}", timeout=5)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            st.error(f"Cache ID `{cache_id}` not found or expired (30-min TTL). "
                     "Ask Agentforce to generate a new link.")
    except requests.exceptions.ConnectionError:
        st.error("Cache API is not reachable. Make sure the FastAPI sidecar is running.")
    except Exception as e:
        st.error(f"Cache fetch error: {e}")
    return None


def _parse_payload():
    """
    Priority:
      1. URL param `id`      — cache_id → fetch full payload from FastAPI sidecar
      2. URL param `payload` — full JSON with `data` + `config` keys (small payloads)
      3. Legacy URL params: `data` (JSON array) + individual chart params
      4. Fall back to sample payload
    Returns (data: list, config: dict, is_sample: bool)
    """
    params = st.query_params

    # --- Priority 1: cache_id from FastAPI ---
    cache_id = params.get("id")
    if cache_id:
        payload = _fetch_from_cache(cache_id)
        if payload:
            return payload.get("data", []), payload.get("config", {}), False
        return [], {}, False          # error already shown above

    # --- Priority 2: full payload ---
    raw_payload = params.get("payload")
    if raw_payload:
        try:
            payload = json.loads(urllib.parse.unquote(raw_payload))
            return payload.get("data", []), payload.get("config", {}), False
        except Exception as e:
            st.error(f"Failed to parse `payload` parameter: {e}")

    # --- Priority 2: legacy `data` array param ---
    raw_data = params.get("data")
    if raw_data:
        try:
            data = json.loads(urllib.parse.unquote(raw_data))
            config = {
                "title":     params.get("title", "Data Visualization"),
                "theme":     params.get("theme", "default"),
                "chartType": params.get("chartType", "bar"),
                "columns": [
                    {"id": k, "label": k}
                    for k in (data[0].keys() if data else [])
                ],
                "interactivity": {"exportable": True},
                "_legacy_chart": {
                    "chartType": params.get("chartType", "bar"),
                    "x": params.get("x"),
                    "y": params.get("y"),
                },
            }
            return data, config, False
        except Exception as e:
            st.error(f"Failed to parse `data` parameter: {e}")

    return SAMPLE_PAYLOAD["data"], SAMPLE_PAYLOAD["config"], True


# ---------------------------------------------------------------------------
# Chart renderer — handles both config.chart and legacy _legacy_chart
# ---------------------------------------------------------------------------

def render_chart(df, chart_cfg, title):
    # Normalise keys — config.chart uses "type", legacy uses "chartType"
    chart_type = (chart_cfg.get("type") or chart_cfg.get("chartType") or "bar").lower()
    x_col = chart_cfg.get("x") or df.columns[0]
    numeric_cols = df.select_dtypes(include=["number"]).columns

    # y can be a list, a comma-separated string, or a plain string
    y_raw = chart_cfg.get("y") or (list(numeric_cols) if len(numeric_cols) > 0 else [df.columns[1]])
    if isinstance(y_raw, list):
        y_cols = y_raw
    elif isinstance(y_raw, str) and "," in y_raw:
        y_cols = [c.strip() for c in y_raw.split(",")]
    else:
        y_cols = [y_raw]

    # Single y column for chart types that don't support multiple series
    y_single = y_cols[0]

    size_col  = chart_cfg.get("size")   # bubble only
    color_col = chart_cfg.get("color")  # optional colour dimension
    hover_col = chart_cfg.get("hover")  # extra column shown on hover

    try:
        if chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_single, title=title,
                         color=color_col or x_col)

        elif chart_type == "grouped_bar":
            fig = px.bar(df, x=x_col, y=y_cols, title=title, barmode="group")

        elif chart_type == "stacked_bar":
            fig = px.bar(df, x=x_col, y=y_cols, title=title, barmode="stack")

        elif chart_type == "horizontal_bar":
            fig = px.bar(df, x=y_single, y=x_col, title=title,
                         orientation="h", color=color_col or x_col)

        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_cols if len(y_cols) > 1 else y_single,
                          title=title, markers=True)

        elif chart_type == "area":
            fig = px.area(df, x=x_col, y=y_cols if len(y_cols) > 1 else y_single,
                          title=title)

        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_single, title=title)

        elif chart_type == "donut":
            fig = px.pie(df, names=x_col, values=y_single, title=title, hole=0.45)

        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_single, title=title,
                             color=color_col, hover_name=hover_col)

        elif chart_type == "bubble":
            # requires size column; falls back to y_single if not provided
            fig = px.scatter(df, x=x_col, y=y_single, title=title,
                             size=size_col or y_single,
                             color=color_col or x_col,
                             hover_name=hover_col,
                             size_max=60)

        elif chart_type == "heatmap":
            # pivot: x = columns, y = rows, values = y_single
            z_col = chart_cfg.get("z") or y_single
            pivot = df.pivot(index=x_col, columns=color_col or df.columns[1], values=z_col)
            import plotly.graph_objects as go
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale="Greens",
            ))
            fig.update_layout(title=title)

        elif chart_type == "funnel":
            fig = px.funnel(df, x=y_single, y=x_col, title=title)

        elif chart_type == "histogram":
            fig = px.histogram(df, x=y_single, title=title, nbins=chart_cfg.get("bins", 20))

        elif chart_type == "box":
            fig = px.box(df, x=x_col, y=y_single, title=title,
                         color=color_col or x_col)

        elif chart_type == "waterfall":
            import plotly.graph_objects as go
            fig = go.Figure(go.Waterfall(
                x=df[x_col].tolist(),
                y=df[y_single].tolist(),
                name=y_single,
            ))
            fig.update_layout(title=title)

        else:
            # Unknown type — fall back to bar
            st.warning(f"Unknown chart type '{chart_type}', falling back to bar chart.")
            fig = px.bar(df, x=x_col, y=y_single, title=title, color=x_col)

        fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            height=400,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Chart rendering error: {e}")
        st.info(f"Available columns: {list(df.columns)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

data, config, is_sample = _parse_payload()

if is_sample:
    st.caption("⚠ Showing sample data — pass a `payload` URL parameter to render your own data.")

title = config.get("title", "Data Visualization")
subtitle = config.get("subtitle", "")

if title:
    st.markdown(f"### {title}")
if subtitle:
    st.caption(subtitle)

# --- Table ---
render_dynamic_table(data, config)

# --- Chart ---
chart_cfg = config.get("chart") or config.get("_legacy_chart")
if chart_cfg:
    st.markdown("---")
    render_chart(pd.DataFrame(data), chart_cfg, title)

import streamlit as st
import plotly.express as px
from utils.data_handler import get_data_from_params, get_sample_data, get_chart_config_from_params

# --- Page Configuration ---
st.set_page_config(
    page_title="Salesforce Data Viz",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Hide Streamlit chrome for clean iframe embed ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
</style>
""", unsafe_allow_html=True)

# --- Load Data ---
df = get_data_from_params()
config = get_chart_config_from_params()

if df is None:
    df = get_sample_data()
    st.caption("Showing sample data (no data parameter in URL)")

# --- Title ---
st.markdown(f"### {config['title']}")
if config["subtitle"]:
    st.caption(config["subtitle"])

# --- Data Table ---
st.markdown("**Data Table**")
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    height=min(len(df) * 40 + 50, 400),
)

# --- Chart ---
st.markdown("**Chart**")

x_col = config["x_column"] or df.columns[0]
numeric_cols = df.select_dtypes(include=["number"]).columns
y_col = config["y_column"] or (numeric_cols[0] if len(numeric_cols) > 0 else df.columns[1])

chart_type = config["chart_type"].lower()

try:
    if chart_type == "bar":
        fig = px.bar(df, x=x_col, y=y_col, title=config["title"], color=x_col)
    elif chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col, title=config["title"])
    elif chart_type == "pie":
        fig = px.pie(df, names=x_col, values=y_col, title=config["title"])
    elif chart_type == "scatter":
        fig = px.scatter(df, x=x_col, y=y_col, title=config["title"])
    elif chart_type == "grouped_bar":
        y_cols = y_col.split(",") if "," in str(y_col) else [y_col]
        fig = px.bar(df, x=x_col, y=y_cols, title=config["title"], barmode="group")
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=config["title"], color=x_col)

    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )

    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Chart rendering error: {e}")
    st.info(f"Available columns: {list(df.columns)}")

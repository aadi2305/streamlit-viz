import json
import urllib.parse
import pandas as pd
import streamlit as st


def get_data_from_params():
    """
    Reads data from URL query parameters.

    Expected URL format:
    http://localhost:8501/?data=[{"territory":"AP","revenue":450000}...]&title=My+Dashboard&chartType=bar&x=territory&y=revenue

    For Salesforce/Agentforce integration:
    - Apex constructs this URL with query results encoded as JSON
    - LWC loads this URL in an iframe
    """
    params = st.query_params

    raw_data = params.get("data", None)
    if raw_data is None:
        return None

    try:
        decoded = urllib.parse.unquote(raw_data)
        records = json.loads(decoded)
        df = pd.DataFrame(records)
        return df
    except (json.JSONDecodeError, ValueError) as e:
        st.error(f"Failed to parse data parameter: {e}")
        return None


def get_sample_data():
    """
    Returns sample data for development/demo purposes.
    Simulates what Salesforce would send.
    """
    return pd.DataFrame([
        {"territory": "Andhra Pradesh", "revenue": 450000, "orders": 120, "growers": 45},
        {"territory": "Telangana",      "revenue": 380000, "orders": 98,  "growers": 38},
        {"territory": "Karnataka",      "revenue": 520000, "orders": 145, "growers": 52},
        {"territory": "Tamil Nadu",     "revenue": 410000, "orders": 110, "growers": 41},
        {"territory": "Maharashtra",    "revenue": 680000, "orders": 190, "growers": 67},
    ])


def get_chart_config_from_params():
    """
    Reads chart configuration from URL parameters.
    """
    params = st.query_params
    return {
        "title":      params.get("title",     "Data Visualization"),
        "chart_type": params.get("chartType", "bar"),
        "x_column":   params.get("x",         None),
        "y_column":   params.get("y",         None),
        "subtitle":   params.get("subtitle",  ""),
    }

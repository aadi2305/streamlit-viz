"""
Dynamic table renderer.
Supports: column config, formatting, conditional formatting, totals row,
groupBy + subtotals, multi-level headers, themes, search, export.
Complex layouts (merged cells, multi-level headers) render as raw HTML.
Simple tables render via st.dataframe.
"""

import re
import io
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _fmt_inr(v):
    """Indian number formatting with lakhs separator."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    negative = v < 0
    v = abs(v)
    s = f"{v:.0f}"
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        parts.reverse()
        s = ",".join(parts) + "," + last3
    return ("−" if negative else "") + "₹" + s


def format_value(value, fmt):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    fmt = (fmt or "").lower()
    try:
        if fmt == "currency_inr":
            return _fmt_inr(value)
        if fmt == "currency_usd":
            return f"${float(value):,.0f}"
        if fmt == "percent":
            return f"{float(value):.1f}%"
        if fmt == "number":
            v = float(value)
            if v == int(v):
                return f"{int(v):,}"
            return f"{v:,.2f}"
        if fmt == "decimal_2":
            return f"{float(value):.2f}"
        if fmt == "date":
            return pd.to_datetime(value).strftime("%-d %b %Y") if value else ""
        if fmt == "date_short":
            return pd.to_datetime(value).strftime("%d/%m/%y") if value else ""
        if fmt == "boolean":
            return "✓" if value else "✗"
        if fmt == "bar":
            try:
                pct = min(max(float(value) / 100, 0), 1)
                filled = round(pct * 8)
                return "█" * filled + "░" * (8 - filled)
            except Exception:
                return str(value)
    except Exception:
        pass
    return str(value)


# ---------------------------------------------------------------------------
# Conditional formatting
# ---------------------------------------------------------------------------

def _eval_condition(value, condition):
    """Returns True if `value` matches the condition string like '>500000' or '==Overdue'."""
    condition = condition.strip()
    m = re.match(r"^(>=|<=|!=|>|<|==)\s*(.+)$", condition)
    if not m:
        return False
    op, raw = m.group(1), m.group(2).strip()
    try:
        threshold = float(raw)
        v = float(value)
        return eval(f"{v}{op}{threshold}")
    except (ValueError, TypeError):
        return str(value) == raw


def cell_style_from_rules(value, column_id, rules):
    """Returns inline CSS string for a cell given the conditional rules list."""
    for rule in rules:
        if rule.get("column") != column_id:
            continue
        if _eval_condition(value, rule.get("condition", "")):
            s = rule.get("style", {})
            css_parts = []
            if s.get("bg"):
                css_parts.append(f"background-color:{s['bg']}")
            if s.get("color"):
                css_parts.append(f"color:{s['color']}")
            if s.get("bold"):
                css_parts.append("font-weight:bold")
            if s.get("italic"):
                css_parts.append("font-style:italic")
            return "; ".join(css_parts)
    return ""


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES = {
    "default": {
        "header_bg": "#f0f2f6", "header_color": "#262730", "header_bold": True,
        "border": "1px solid #e0e0e0", "stripe_bg": "#f9f9f9",
    },
    "minimal": {
        "header_bg": "#ffffff", "header_color": "#262730", "header_bold": True,
        "border": "none", "border_bottom": "2px solid #262730", "stripe_bg": "transparent",
    },
    "striped": {
        "header_bg": "#f0f2f6", "header_color": "#262730", "header_bold": True,
        "border": "1px solid #e0e0e0", "stripe_bg": "#f5f5f5",
    },
    "bordered": {
        "header_bg": "#f0f2f6", "header_color": "#262730", "header_bold": True,
        "border": "1px solid #bbb", "stripe_bg": "transparent",
    },
    "syngenta": {
        "header_bg": "#00A651", "header_color": "#ffffff", "header_bold": True,
        "border": "1px solid #d0e8d8", "stripe_bg": "#f0faf4",
    },
}

DENSITY_PADDING = {"compact": "4px 8px", "default": "8px 12px", "comfortable": "12px 16px"}
FONT_SIZE = {"small": "12px", "medium": "14px", "large": "16px"}


# ---------------------------------------------------------------------------
# Calculated columns
# ---------------------------------------------------------------------------

def apply_calculated_columns(df, calc_cols):
    for cc in (calc_cols or []):
        formula = cc.get("formula", "")
        col_id = cc.get("id")
        if not col_id or not formula:
            continue
        try:
            df[col_id] = df.eval(formula)
        except Exception as e:
            st.warning(f"Calculated column '{col_id}' error: {e}")
    return df


# ---------------------------------------------------------------------------
# Totals / averages
# ---------------------------------------------------------------------------

def build_totals_row(df, totals_cfg, label="Grand Total"):
    row = {}
    fn = (totals_cfg.get("function") or "sum").lower()
    cols = totals_cfg.get("columns", [])
    first_col = True
    for col in df.columns:
        if first_col:
            row[col] = label
            first_col = False
        elif col in cols:
            try:
                row[col] = df[col].sum() if fn == "sum" else df[col].mean()
            except Exception:
                row[col] = ""
        else:
            row[col] = ""
    return row


# ---------------------------------------------------------------------------
# GroupBy renderer
# ---------------------------------------------------------------------------

def render_grouped_html(df, col_defs, group_cfg, totals_cfg, cf_rules, theme_key,
                        density, font_size_key, header_levels):
    theme = THEMES.get(theme_key, THEMES["default"])
    pad = DENSITY_PADDING.get(density, DENSITY_PADDING["default"])
    fs = FONT_SIZE.get(font_size_key, FONT_SIZE["medium"])
    group_col = group_cfg.get("column")
    sub_cfg = group_cfg.get("subtotals", {})

    visible_cols = [c for c in col_defs if not c.get("hidden")]

    html = _table_open(theme, fs)
    html += _render_header_rows(header_levels, visible_cols, theme, pad)

    for group_val, group_df in df.groupby(group_col, sort=False):
        # Group header row
        html += f'<tr style="background:{theme["header_bg"]};font-weight:bold;">'
        html += f'<td colspan="{len(visible_cols)}" style="padding:{pad};border-bottom:{theme.get("border","")};color:{theme["header_color"]};">'
        html += f"▸ {group_val}</td></tr>"

        # Data rows
        for i, (_, row) in enumerate(group_df.iterrows()):
            bg = theme["stripe_bg"] if i % 2 == 1 else "transparent"
            html += f'<tr style="background:{bg};">'
            for col in visible_cols:
                cid = col["id"]
                raw = row.get(cid, "")
                cell_css = cell_style_from_rules(raw, cid, cf_rules)
                val = format_value(raw, col.get("format"))
                align = col.get("align", "left")
                html += f'<td style="padding:{pad};text-align:{align};{cell_css};border-bottom:{theme.get("border","1px solid #e0e0e0")};">{val}</td>'
            html += "</tr>"

        # Subtotals row
        if sub_cfg:
            sub_fn = sub_cfg.get("function", "sum").lower()
            sub_cols = sub_cfg.get("columns", [])
            html += f'<tr style="background:{theme["header_bg"]};font-style:italic;">'
            first = True
            for col in visible_cols:
                cid = col["id"]
                if first:
                    html += f'<td style="padding:{pad};font-weight:bold;">Subtotal</td>'
                    first = False
                elif cid in sub_cols:
                    try:
                        v = group_df[cid].sum() if sub_fn == "sum" else group_df[cid].mean()
                        html += f'<td style="padding:{pad};text-align:{col.get("align","left")};">{format_value(v, col.get("format"))}</td>'
                    except Exception:
                        html += "<td></td>"
                else:
                    html += "<td></td>"
            html += "</tr>"

    # Grand totals
    if totals_cfg:
        t = build_totals_row(df, totals_cfg, totals_cfg.get("label", "Grand Total"))
        html += f'<tr style="background:{theme["header_bg"]};font-weight:bold;border-top:2px solid #aaa;">'
        for col in visible_cols:
            cid = col["id"]
            val = format_value(t.get(cid, ""), col.get("format"))
            html += f'<td style="padding:{pad};text-align:{col.get("align","left")};">{val}</td>'
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# ---------------------------------------------------------------------------
# Multi-level header builder
# ---------------------------------------------------------------------------

def _render_header_rows(header_levels, visible_cols, theme, pad):
    hdr_bg = theme["header_bg"]
    hdr_color = theme["header_color"]
    bold = "font-weight:bold;" if theme.get("header_bold") else ""
    html = "<thead>"
    if header_levels:
        for level in header_levels:
            html += "<tr>"
            for cell in level.get("cells", []):
                cs = cell.get("colSpan", 1)
                rs = cell.get("rowSpan", 1)
                label = cell.get("label", "")
                html += (f'<th colspan="{cs}" rowspan="{rs}" '
                         f'style="background:{hdr_bg};color:{hdr_color};{bold}padding:{pad};'
                         f'text-align:center;white-space:nowrap;">{label}</th>')
            html += "</tr>"
    else:
        html += "<tr>"
        for col in visible_cols:
            align = col.get("align", "left")
            w = f'width:{col["width"]};' if col.get("width") else ""
            html += (f'<th style="background:{hdr_bg};color:{hdr_color};{bold}padding:{pad};'
                     f'text-align:{align};{w}white-space:nowrap;">{col.get("label", col["id"])}</th>')
        html += "</tr>"
    html += "</thead><tbody>"
    return html


def _table_open(theme, fs):
    border = theme.get("border", "1px solid #e0e0e0")
    return (
        f'<div style="overflow-x:auto;font-size:{fs};">'
        f'<table style="width:100%;border-collapse:collapse;border:{border};">'
    )


# ---------------------------------------------------------------------------
# Main HTML table renderer (flat, no grouping)
# ---------------------------------------------------------------------------

def render_html_table(df, col_defs, totals_cfg, cf_rules, theme_key,
                      density, font_size_key, header_levels, alternate_rows):
    theme = THEMES.get(theme_key, THEMES["default"])
    pad = DENSITY_PADDING.get(density, DENSITY_PADDING["default"])
    fs = FONT_SIZE.get(font_size_key, FONT_SIZE["medium"])
    visible_cols = [c for c in col_defs if not c.get("hidden")]

    html = _table_open(theme, fs)
    html += _render_header_rows(header_levels, visible_cols, theme, pad)

    for i, (_, row) in enumerate(df.iterrows()):
        use_stripe = alternate_rows and i % 2 == 1
        bg = theme["stripe_bg"] if use_stripe else "transparent"
        html += f'<tr style="background:{bg};">'
        for col in visible_cols:
            cid = col["id"]
            raw = row.get(cid, "")
            cell_css = cell_style_from_rules(raw, cid, cf_rules)
            val = format_value(raw, col.get("format"))
            align = col.get("align", "left")
            border_b = theme.get("border", "1px solid #e0e0e0")
            html += (f'<td style="padding:{pad};text-align:{align};'
                     f'{cell_css};border-bottom:{border_b};">{val}</td>')
        html += "</tr>"

    # Totals row
    if totals_cfg:
        t = build_totals_row(df, totals_cfg, totals_cfg.get("label", "Grand Total"))
        html += f'<tr style="background:{theme["header_bg"]};font-weight:bold;border-top:2px solid #aaa;">'
        for col in visible_cols:
            cid = col["id"]
            val = format_value(t.get(cid, ""), col.get("format"))
            html += f'<td style="padding:{pad};text-align:{col.get("align","left")};">{val}</td>'
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# ---------------------------------------------------------------------------
# Search / filter helper
# ---------------------------------------------------------------------------

def apply_search(df, query):
    if not query:
        return df
    mask = df.apply(
        lambda col: col.astype(str).str.contains(query, case=False, na=False)
    ).any(axis=1)
    return df[mask]


# ---------------------------------------------------------------------------
# Export helper
# ---------------------------------------------------------------------------

def render_export_button(df, col_defs):
    visible = [c["id"] for c in col_defs if not c.get("hidden") and c["id"] in df.columns]
    export_df = df[visible].copy()
    buf = io.BytesIO()
    export_df.to_csv(buf, index=False)
    st.download_button(
        label="⬇ Export CSV",
        data=buf.getvalue(),
        file_name="table_export.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

def render_dynamic_table(data: list, config: dict):
    """
    Main entry point called from app.py.
    `data`   — list of row dicts
    `config` — full config object from the JSON payload
    """
    if not data:
        st.warning("No data provided.")
        return

    df = pd.DataFrame(data)

    # --- Column definitions: fill in defaults for any column not in config ---
    col_defs_raw = config.get("columns") or [{"id": c, "label": c} for c in df.columns]
    col_defs = []
    for c in col_defs_raw:
        if "label" not in c:
            c["label"] = c["id"]
        col_defs.append(c)

    # Ensure every defined column exists in df (calculated columns may add them)
    calc_cols = config.get("calculatedColumns", [])
    df = apply_calculated_columns(df, calc_cols)

    # Add any new calc columns to col_defs if not already there
    existing_ids = {c["id"] for c in col_defs}
    for cc in calc_cols:
        if cc.get("id") and cc["id"] not in existing_ids:
            col_defs.append({"id": cc["id"], "label": cc.get("label", cc["id"]),
                             "format": cc.get("format", "")})

    theme_key     = config.get("theme", "default")
    density       = config.get("density", "default")
    font_size_key = config.get("fontSize", "medium")
    alternate     = config.get("alternateRows", theme_key in ("striped", "syngenta"))
    group_cfg     = config.get("groupBy")
    totals_cfg    = config.get("totalsRow")
    cf            = config.get("conditionalFormatting", {})
    cf_rules      = cf.get("rules", []) if isinstance(cf, dict) else []
    header_levels = config.get("headerLevels")
    interactivity = config.get("interactivity", {})
    max_height    = config.get("maxHeight", "500px")

    # --- Search bar ---
    query = ""
    if interactivity.get("searchable"):
        query = st.text_input("🔍 Search", placeholder="Type to filter rows…", key="tbl_search")
        df = apply_search(df, query)

    # --- Export button ---
    if interactivity.get("exportable"):
        render_export_button(df, col_defs)

    # --- Decide render path ---
    needs_html = bool(group_cfg or header_levels or cf_rules or totals_cfg or alternate)

    if needs_html:
        if group_cfg:
            html = render_grouped_html(
                df, col_defs, group_cfg, totals_cfg, cf_rules,
                theme_key, density, font_size_key, header_levels,
            )
        else:
            html = render_html_table(
                df, col_defs, totals_cfg, cf_rules,
                theme_key, density, font_size_key, header_levels, alternate,
            )
        st.markdown(
            f'<div style="max-height:{max_height};overflow-y:auto;">{html}</div>',
            unsafe_allow_html=True,
        )
    else:
        # Simple path — use st.dataframe with column config
        visible = [c for c in col_defs if not c.get("hidden") and c["id"] in df.columns]
        st.dataframe(
            df[[c["id"] for c in visible]].rename(
                columns={c["id"]: c.get("label", c["id"]) for c in visible}
            ),
            use_container_width=True,
            hide_index=True,
            height=min(len(df) * 40 + 50, int(max_height.replace("px", "") or 400)),
        )

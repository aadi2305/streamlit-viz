# Streamlit Viz — API Documentation

## Overview

Two services work together:

| Service | URL | Purpose |
|---------|-----|---------|
| **FastAPI** | `https://streamlit-viz.onrender.com` | Receives POST from Apex, stores payload, returns cache ID |
| **Streamlit** | `https://vivekm2305.streamlit.app` | Reads payload by ID, renders table/chart |

**Flow:**
```
Apex POST /api/cache → { cache_id, url }
                              ↓
          Streamlit /?id=<cache_id> → renders table
```

---

## FastAPI Endpoints

### `POST /api/cache`

Stores a data + config payload and returns a ready-to-use Streamlit URL.

**Request body:**
```json
{
  "data": [ ...array of row objects... ],
  "config": { ...table config object... }
}
```

**Response (201):**
```json
{
  "cache_id": "a3f7c912",
  "url": "https://vivekm2305.streamlit.app/?id=a3f7c912",
  "expires_in_seconds": 1800
}
```

**Notes:**
- Cache TTL is 30 minutes (configurable via `CACHE_TTL_SECONDS` env var)
- The `url` field is ready to use directly as an iframe `src`

---

### `GET /api/cache/{cache_id}`

Retrieves a stored payload by ID.

**Response (200):**
```json
{
  "data": [ ...row objects... ],
  "config": { ...config object... }
}
```

**Response (404):** Cache ID not found or expired.

---

### `GET /api/health`

Health check.

**Response:**
```json
{
  "status": "ok",
  "entries": 3,
  "ttl_seconds": 1800
}
```

---

### `DELETE /api/cache/{cache_id}`

Removes a cache entry before TTL expiry.

**Response:** 204 No Content

---

### API Docs (interactive)

```
https://streamlit-viz.onrender.com/api/docs
```

---

## Streamlit URL Parameters

### `?id=<cache_id>` (recommended)

Fetches the full payload from FastAPI by cache ID. No data size limit.

```
https://vivekm2305.streamlit.app/?id=a3f7c912
```

### `?payload=<url-encoded JSON>` (small payloads only)

Pass the full `{data, config}` JSON directly in the URL. Limited to ~2000 characters.

```
https://vivekm2305.streamlit.app/?payload=%7B%22data%22%3A...%7D
```

### Legacy params (backwards compatible)

```
?data=[...]&title=My+Title&chartType=bar&x=territory&y=revenue&theme=syngenta
```

---

## Full Payload Schema

```json
{
  "data": [
    { "field1": "value", "field2": 12345 }
  ],
  "config": {
    "title": "string",
    "subtitle": "string",
    "theme": "syngenta | default | minimal | striped | bordered",
    "density": "compact | default | comfortable",
    "fontSize": "small | medium | large",
    "alternateRows": true,
    "maxHeight": "500px",
    "columns": [ ...see Column Config... ],
    "calculatedColumns": [ ...see Calculated Columns... ],
    "groupBy": { ...see GroupBy... },
    "totalsRow": { ...see Totals Row... },
    "conditionalFormatting": { ...see Conditional Formatting... },
    "headerLevels": [ ...see Multi-Level Headers... ],
    "interactivity": { ...see Interactivity... },
    "chart": { ...see Chart Config... }
  }
}
```

---

## Config Reference

### Column Config

```json
"columns": [
  {
    "id": "revenue",
    "label": "Revenue (INR)",
    "format": "currency_INR",
    "align": "right",
    "width": "150px",
    "hidden": false
  }
]
```

| Property | Values | Description |
|----------|--------|-------------|
| `id` | string | Field name in the data rows |
| `label` | string | Header display text |
| `format` | see Format Presets | How to render the cell value |
| `align` | `left` `center` `right` | Text alignment |
| `width` | `150px` `20%` `auto` | Column width |
| `hidden` | boolean | Exclude from render (data still present) |

---

### Format Presets

| Key | Output | Example |
|-----|--------|---------|
| `currency_INR` | ₹X,XX,XXX | ₹4,50,000 |
| `currency_USD` | $X,XXX | $450,000 |
| `percent` | X.X% | 45.2% |
| `number` | X,XXX | 1,20,000 |
| `decimal_2` | X.XX | 450.00 |
| `date` | D MMM YYYY | 15 Jun 2026 |
| `date_short` | DD/MM/YY | 15/06/26 |
| `boolean` | ✓ / ✗ | ✓ |
| `bar` | █████░░░ | Progress bar (0–100 scale) |

---

### Conditional Formatting

```json
"conditionalFormatting": {
  "rules": [
    {
      "column": "revenue",
      "condition": ">500000",
      "style": {
        "bg": "#d4edda",
        "color": "#155724",
        "bold": true,
        "italic": false
      }
    },
    {
      "column": "revenue",
      "condition": "<400000",
      "style": { "bg": "#f8d7da" }
    },
    {
      "column": "status",
      "condition": "==Overdue",
      "style": { "color": "red", "bold": true }
    }
  ]
}
```

**Supported operators:** `>` `<` `>=` `<=` `==` `!=`

**Style properties:**

| Property | Type | Description |
|----------|------|-------------|
| `bg` | hex / CSS color | Cell background color |
| `color` | hex / CSS color | Text color |
| `bold` | boolean | Bold text |
| `italic` | boolean | Italic text |

---

### GroupBy

```json
"groupBy": {
  "column": "state",
  "subtotals": {
    "columns": ["revenue", "orders"],
    "function": "sum"
  }
}
```

| Property | Values | Description |
|----------|--------|-------------|
| `column` | string | Column to group rows by |
| `subtotals.columns` | array of strings | Which columns to aggregate |
| `subtotals.function` | `sum` `avg` | Aggregation function |

---

### Totals Row

```json
"totalsRow": {
  "columns": ["revenue", "orders", "growers"],
  "function": "sum",
  "label": "Grand Total"
}
```

| Property | Values | Description |
|----------|--------|-------------|
| `columns` | array of strings | Columns to sum/average |
| `function` | `sum` `avg` | Aggregation function |
| `label` | string | Label in first cell (default: `"Grand Total"`) |

---

### Calculated Columns

```json
"calculatedColumns": [
  {
    "id": "revenue_per_grower",
    "label": "Rev / Grower",
    "formula": "revenue / growers",
    "format": "currency_INR"
  }
]
```

Formulas use `pandas.DataFrame.eval()` syntax. Reference any column by its `id`.

---

### Multi-Level Headers

For tables with grouped/merged column headers:

```json
"headerLevels": [
  {
    "cells": [
      { "label": "",               "colSpan": 1 },
      { "label": "Q1 Performance", "colSpan": 2 },
      { "label": "Q2 Performance", "colSpan": 2 }
    ]
  },
  {
    "cells": [
      { "label": "Territory" },
      { "label": "Revenue"  },
      { "label": "Orders"   },
      { "label": "Revenue"  },
      { "label": "Orders"   }
    ]
  }
]
```

Each level is a row. `colSpan` merges cells horizontally. `rowSpan` merges vertically.

---

### Chart Config

Add a `chart` block to render a Plotly chart below the table. If omitted, only the table is shown.

```json
"chart": {
  "type": "bar",
  "x": "territory",
  "y": "revenue",
  "title": "Revenue by Territory"
}
```

| Property | Type | Description |
|----------|------|-------------|
| `type` | string | Chart type to render (see table below) |
| `x` | string | Column id to use as x-axis / category labels |
| `y` | string or array | Column id(s) for y-axis. Comma-separated string or JSON array both work. Multi-value supported on `line`, `area`, `grouped_bar`, `stacked_bar` |
| `title` | string | Chart title (defaults to config `title`) |
| `color` | string | Column id to use as a colour dimension (optional) |
| `size` | string | Column id to control bubble size — `bubble` chart only |
| `hover` | string | Column id shown in hover tooltip |
| `z` | string | Column id used as heatmap cell value — `heatmap` only |
| `bins` | integer | Number of histogram bins — `histogram` only (default 20) |

**Supported chart types:**

| Type | Description | Best for | Multi-y? |
|------|-------------|----------|----------|
| `bar` | Vertical bar, each bar coloured by x value | Revenue by territory | No |
| `grouped_bar` | Side-by-side bars for multiple y columns | Revenue vs target | Yes |
| `stacked_bar` | Stacked bars for multiple y columns | Category composition | Yes |
| `horizontal_bar` | Horizontal bar, good for long category names | Top-N rankings | No |
| `line` | Line chart with markers | Trends over time | Yes |
| `area` | Filled line chart | Cumulative trends | Yes |
| `pie` | Pie chart showing proportions | Market share | No |
| `donut` | Donut/ring chart | Proportions with centre space | No |
| `scatter` | One dot per row | Correlation analysis | No |
| `bubble` | Scatter with sized bubbles | 3-variable comparison | No |
| `heatmap` | Colour matrix — requires pivot-able data | Performance matrices | No |
| `funnel` | Funnel / conversion stages | Pipeline / funnel analysis | No |
| `histogram` | Distribution of a numeric column | Score/value distribution | No |
| `box` | Box-and-whisker showing spread + outliers | Statistical summaries | No |
| `waterfall` | Incremental cumulative change | Variance / bridge charts | No |

**Examples:**

*Bar chart:*
```json
"chart": { "type": "bar", "x": "territory", "y": "revenue" }
```

*Grouped bar — compare two metrics side by side:*
```json
"chart": { "type": "grouped_bar", "x": "territory", "y": ["revenue", "target"] }
```

*Stacked bar — composition over categories:*
```json
"chart": { "type": "stacked_bar", "x": "quarter", "y": ["product_a", "product_b", "product_c"] }
```

*Horizontal bar — ranking:*
```json
"chart": { "type": "horizontal_bar", "x": "state", "y": "revenue" }
```

*Line chart — trend:*
```json
"chart": { "type": "line", "x": "month", "y": "revenue" }
```

*Multi-series line:*
```json
"chart": { "type": "line", "x": "month", "y": ["revenue", "cost", "profit"] }
```

*Area chart:*
```json
"chart": { "type": "area", "x": "month", "y": "revenue" }
```

*Pie chart:*
```json
"chart": { "type": "pie", "x": "state", "y": "revenue" }
```

*Donut chart:*
```json
"chart": { "type": "donut", "x": "product", "y": "sales" }
```

*Scatter — correlation:*
```json
"chart": { "type": "scatter", "x": "orders", "y": "revenue" }
```

*Bubble chart — 3-variable:*
```json
"chart": { "type": "bubble", "x": "orders", "y": "revenue", "size": "growers", "color": "state" }
```

*Heatmap — requires a column to pivot on (set `color` to the column name):*
```json
"chart": { "type": "heatmap", "x": "state", "color": "quarter", "z": "revenue" }
```

*Funnel — pipeline stages:*
```json
"chart": { "type": "funnel", "x": "stage", "y": "count" }
```

*Histogram — value distribution:*
```json
"chart": { "type": "histogram", "y": "revenue", "bins": 15 }
```

*Box plot — spread and outliers:*
```json
"chart": { "type": "box", "x": "state", "y": "revenue" }
```

*Waterfall — incremental changes:*
```json
"chart": { "type": "waterfall", "x": "category", "y": "delta" }
```

---

### Interactivity

```json
"interactivity": {
  "searchable": true,
  "exportable": true
}
```

| Property | Type | Description |
|----------|------|-------------|
| `searchable` | boolean | Shows a search bar that filters rows across all columns |
| `exportable` | boolean | Shows a "⬇ Export CSV" download button |

---

## Complete Example Payload

```json
{
  "data": [
    { "state": "Andhra Pradesh", "territory": "Guntur",    "revenue": 450000, "orders": 120, "growers": 45 },
    { "state": "Andhra Pradesh", "territory": "Krishna",   "revenue": 520000, "orders": 145, "growers": 52 },
    { "state": "Telangana",      "territory": "Hyderabad", "revenue": 680000, "orders": 190, "growers": 67 },
    { "state": "Telangana",      "territory": "Warangal",  "revenue": 380000, "orders": 98,  "growers": 38 },
    { "state": "Karnataka",      "territory": "Bangalore", "revenue": 590000, "orders": 160, "growers": 58 }
  ],
  "config": {
    "title": "Territory Performance",
    "theme": "syngenta",
    "density": "default",
    "alternateRows": true,
    "columns": [
      { "id": "state",     "label": "State",     "width": "130px" },
      { "id": "territory", "label": "Territory",  "width": "150px" },
      { "id": "revenue",   "label": "Revenue",    "format": "currency_INR", "align": "right"  },
      { "id": "orders",    "label": "Orders",     "format": "number",       "align": "center" },
      { "id": "growers",   "label": "Growers",    "format": "number",       "align": "center" }
    ],
    "groupBy": {
      "column": "state",
      "subtotals": { "columns": ["revenue", "orders"], "function": "sum" }
    },
    "totalsRow": {
      "columns": ["revenue", "orders", "growers"],
      "function": "sum",
      "label": "Grand Total"
    },
    "conditionalFormatting": {
      "rules": [
        { "column": "revenue", "condition": ">500000", "style": { "bg": "#d4edda", "bold": true } },
        { "column": "revenue", "condition": "<400000", "style": { "bg": "#f8d7da" } }
      ]
    },
    "interactivity": {
      "searchable": true,
      "exportable": true
    }
  }
}
```

---

## Salesforce Integration

### Apex — calling the API

```apex
String body = '{"data":' + dataJson + ',"config":' + configJson + '}';

HttpRequest req = new HttpRequest();
req.setEndpoint('https://streamlit-viz.onrender.com/api/cache');
req.setMethod('POST');
req.setHeader('Content-Type', 'application/json');
req.setBody(body);
req.setTimeout(10000);

HttpResponse res = new Http().send(req);
Map<String, Object> parsed = (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
String iframeUrl = (String) parsed.get('url');
```

### Remote Site Settings required

Add `https://streamlit-viz.onrender.com` to:
**Setup → Security → Remote Site Settings**

### LWC — embedding the iframe

The `dynamicChart` LWC subscribes to the `VisualizationReady__e` Platform Event.
When Apex calls `EventBus.publish(event)`, the LWC automatically updates its iframe.

Manual usage:
```html
<c-dynamic-chart chart-url="https://vivekm2305.streamlit.app/?id=a3f7c912"
                 chart-title="Territory Performance">
</c-dynamic-chart>
```

---

## Environment Variables

### FastAPI (Render.com)

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | `1800` | How long cache entries live (seconds) |
| `STREAMLIT_URL` | `http://localhost:8501` | Base URL prepended to `/?id=` in POST response |

### Streamlit (Community Cloud)

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_API_URL` | `http://localhost:8000` | URL of the FastAPI service |

Set via **Streamlit Cloud → app settings → Secrets:**
```toml
CACHE_API_URL = "https://streamlit-viz.onrender.com"
```

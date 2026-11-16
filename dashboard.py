import json
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

REPORTS_DIR = Path("reports")
OPEN_BROWSER = True


class KPI(BaseModel):
    label: str = Field(description="Metric name, e.g. 'Clicks'.")
    value: str = Field(description="Formatted value, e.g. '1,200' or '4.1%'.")
    change: str = Field("", description="Change vs previous period, e.g. '+26%'.")
    status: Literal["good", "bad", "neutral"] = Field(
        "neutral", description="Whether the change is good or bad for the site."
    )


class Chart(BaseModel):
    title: str
    type: Literal["line", "bar"] = "line"
    labels: list[str] = Field(description="X-axis labels, e.g. dates or keywords.")
    values: list[float] = Field(description="One number per label.")
    reverse_y: bool = Field(False, description="True for position, where lower is better.")


class Table(BaseModel):
    title: str
    columns: list[str]
    rows: list[list[str]] = Field(description="Each row has one cell per column.")


class Recommendation(BaseModel):
    title: str
    detail: str = Field(description="What to do and why, based on the data.")
    priority: Literal["high", "medium", "low"]


class Dashboard(BaseModel):
    title: str
    period: str = Field(description="Date range covered, e.g. '2026-10-08 to 2026-11-06'.")
    summary: str = Field(description="Executive summary in 3-5 sentences.")
    kpis: list[KPI] = []
    charts: list[Chart] = []
    tables: list[Table] = []
    recommendations: list[Recommendation] = []
    direction: Literal["ltr", "rtl"] = Field("ltr", description="'rtl' for Persian or Arabic.")


STYLE = """
body { font-family: system-ui, Tahoma, sans-serif; background: #f5f6f8; color: #1f2933; margin: 0; padding: 32px; }
.wrap { max-width: 1100px; margin: auto; }
h1 { margin: 0 0 4px; font-size: 26px; }
h2 { font-size: 18px; margin: 32px 0 12px; }
h3 { font-size: 15px; margin: 0 0 12px; }
.period { color: #6b7280; }
.card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0, 0, 0, .06); }
.summary { margin-top: 24px; line-height: 1.8; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
.charts { grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }
.label { color: #6b7280; font-size: 13px; }
.value { font-size: 28px; font-weight: 700; margin: 6px 0; }
.good { color: #15803d; }
.bad { color: #b91c1c; }
.neutral { color: #6b7280; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px; border-bottom: 1px solid #eee; text-align: start; }
th { color: #6b7280; font-weight: 600; }
.tag { font-size: 12px; padding: 2px 10px; border-radius: 999px; margin-inline-start: 8px; }
.tag.high { background: #fee2e2; color: #b91c1c; }
.tag.medium { background: #fef3c7; color: #92400e; }
.tag.low { background: #e0f2fe; color: #075985; }
.rec { margin-bottom: 12px; }
.rec p { margin: 8px 0 0; line-height: 1.7; }
"""


def render_kpi(kpi):
    change = f'<div class="{kpi.status}">{escape(kpi.change)}</div>' if kpi.change else ""
    return f"""
    <div class="card">
      <div class="label">{escape(kpi.label)}</div>
      <div class="value">{escape(kpi.value)}</div>
      {change}
    </div>"""


def render_chart(index, chart):
    config = {
        "type": chart.type,
        "data": {
            "labels": chart.labels,
            "datasets": [
                {
                    "data": chart.values,
                    "borderColor": "#2563eb",
                    "backgroundColor": "rgba(37, 99, 235, 0.2)",
                    "tension": 0.3,
                }
            ],
        },
        "options": {
            "plugins": {"legend": {"display": False}},
            "scales": {"y": {"reverse": chart.reverse_y}},
        },
    }
    config_json = json.dumps(config).replace("</", "<\\/")
    return f"""
    <div class="card">
      <h3>{escape(chart.title)}</h3>
      <canvas id="chart{index}"></canvas>
      <script>new Chart(document.getElementById("chart{index}"), {config_json});</script>
    </div>"""


def render_table(table):
    header = "".join(f"<th>{escape(column)}</th>" for column in table.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in table.rows
    )
    return f"""
    <h2>{escape(table.title)}</h2>
    <div class="card"><table><tr>{header}</tr>{rows}</table></div>"""


def render_recommendation(recommendation):
    return f"""
    <div class="card rec">
      <strong>{escape(recommendation.title)}</strong>
      <span class="tag {recommendation.priority}">{recommendation.priority}</span>
      <p>{escape(recommendation.detail)}</p>
    </div>"""


def render_dashboard(dashboard):
    kpis = "".join(render_kpi(kpi) for kpi in dashboard.kpis)
    charts = "".join(render_chart(i, chart) for i, chart in enumerate(dashboard.charts))
    tables = "".join(render_table(table) for table in dashboard.tables)
    recommendations = "".join(render_recommendation(r) for r in dashboard.recommendations)

    return f"""<!DOCTYPE html>
<html dir="{dashboard.direction}">
<head>
  <meta charset="utf-8">
  <title>{escape(dashboard.title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>{STYLE}</style>
</head>
<body>
  <div class="wrap">
    <h1>{escape(dashboard.title)}</h1>
    <div class="period">{escape(dashboard.period)}</div>
    <div class="card summary">{escape(dashboard.summary)}</div>
    {f'<h2>Key metrics</h2><div class="grid">{kpis}</div>' if kpis else ""}
    {f'<div class="grid charts" style="margin-top: 24px">{charts}</div>' if charts else ""}
    {tables}
    {f'<h2>Recommendations</h2>{recommendations}' if recommendations else ""}
  </div>
</body>
</html>"""


@tool(args_schema=Dashboard)
def create_dashboard(**fields) -> str:
    """Build an HTML dashboard from data you already collected and open it in the browser.

    Call this only after gathering real data with the other tools. Use KPIs for the
    headline numbers, charts for trends over time, tables for lists of keywords or
    pages, and recommendations for prioritized, data-backed actions.
    """
    dashboard = Dashboard(**fields)
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"dashboard-{datetime.now():%Y-%m-%d-%H%M%S}.html"
    path.write_text(render_dashboard(dashboard), encoding="utf-8")
    if OPEN_BROWSER:
        webbrowser.open(path.resolve().as_uri())
    return f"Dashboard saved to {path}"
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import google.auth
from dotenv import load_dotenv
from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
PAGE_SIZE = 25000
DATA_DELAY_DAYS = 3
GOOGLE_TIMEZONE = ZoneInfo("America/Los_Angeles")

METRICS = ["clicks", "impressions", "ctr", "position"]
NO_DATA = {"clicks": 0, "impressions": 0, "ctr": 0, "position": None}

Dimension = Literal["query", "page", "country", "device", "date", "searchAppearance"]


class Filter(BaseModel):
    dimension: Literal["query", "page", "country", "device", "searchAppearance"]
    operator: Literal["contains", "equals", "notContains", "notEquals"] = "contains"
    expression: str


def get_service():
    credentials, project = google.auth.default(scopes=SCOPES)
    return build("searchconsole", "v1", credentials=credentials)


def format_row(dimensions, row):
    result = dict(zip(dimensions, row.get("keys", [])))
    result["clicks"] = row["clicks"]
    result["impressions"] = row["impressions"]
    result["ctr"] = round(row["ctr"], 4)
    result["position"] = round(row["position"], 1)
    return result


def run_query(
    site_url,
    start_date,
    end_date,
    dimensions=[],
    filters=[],
    row_limit=100,
    aggregation_type="auto",
):
    service = get_service()
    rows = []

    while row_limit is None or len(rows) < row_limit:
        page_size = PAGE_SIZE if row_limit is None else min(PAGE_SIZE, row_limit - len(rows))
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": page_size,
            "startRow": len(rows),
            "aggregationType": aggregation_type,
        }
        if filters:
            body["dimensionFilterGroups"] = [{"filters": filters}]

        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        page = response.get("rows", [])
        rows.extend(page)

        if len(page) < page_size:
            break

    return [format_row(dimensions, row) for row in rows]


def date_range(days, days_before=0):
    today = datetime.now(GOOGLE_TIMEZONE).date()
    end = today - timedelta(days=DATA_DELAY_DAYS + days_before)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def only_metrics(row):
    return {name: row[name] for name in METRICS}


def difference(current, previous):
    change = {}
    for name in METRICS:
        if current[name] is None or previous[name] is None:
            change[name] = None
        else:
            change[name] = round(current[name] - previous[name], 4)
    return change


def totals(site_url, start_date, end_date, filters=[]):
    rows = run_query(site_url, start_date, end_date, filters=filters)
    return only_metrics(rows[0]) if rows else NO_DATA


@tool
def list_sites() -> list[dict]:
    """List the Search Console properties this account can access.

    Use this first to find the exact `site_url` the other tools need,
    e.g. 'https://example.com/' or 'sc-domain:example.com'.
    """
    response = get_service().sites().list().execute()
    return response.get("siteEntry", [])


@tool(parse_docstring=True)
def search_analytics_query(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[Dimension] = [],
    filters: list[Filter] = [],
    row_limit: int = 100,
    aggregation_type: Literal["auto", "byPage", "byProperty"] = "auto",
) -> list[dict]:
    """Query Google Search performance: clicks, impressions, CTR and average position.

    Rows come back sorted by clicks, highest first. Dates are in Pacific time,
    and the last 2-3 days are usually incomplete.

    Args:
        site_url: Property exactly as returned by list_sites.
        start_date: First day of the range, YYYY-MM-DD.
        end_date: Last day of the range (inclusive), YYYY-MM-DD.
        dimensions: How to group the rows, e.g. ['query'] for keywords, ['page'] for
            pages, ['date'] for a trend, ['query', 'page'] to combine. Empty for totals.
        filters: Conditions that must all match. Country is a 3-letter code like 'usa',
            device is 'DESKTOP', 'MOBILE' or 'TABLET'.
        row_limit: Maximum number of rows to return. More than 25000 is fetched in pages.
        aggregation_type: 'byPage' counts each URL separately, 'byProperty' counts
            the site once per search result. Leave as 'auto' unless asked.
    """
    filter_dicts = [f.model_dump() for f in filters]
    return run_query(
        site_url, start_date, end_date, dimensions, filter_dicts, row_limit, aggregation_type
    )


@tool(parse_docstring=True)
def inspect_url(site_url: str, url: str) -> dict:
    """Inspect how Google sees one URL: index status, crawl, canonicals, mobile and rich results.

    The result includes the index verdict and coverage state, last crawl time,
    page fetch and robots.txt state, the Google-selected and user-declared
    canonicals, plus mobile usability and rich results when Google reports them.

    Args:
        site_url: Property exactly as returned by list_sites.
        url: Full URL of the page, e.g. 'https://example.com/pricing'.
            It must belong to the property.
    """
    body = {"inspectionUrl": url, "siteUrl": site_url}
    response = get_service().urlInspection().index().inspect(body=body).execute()
    return response["inspectionResult"]


@tool(parse_docstring=True)
def list_sitemaps(site_url: str) -> list[dict]:
    """List the sitemaps submitted for a property.

    Each entry has the sitemap path, type, last submitted and last downloaded
    times, whether it is still pending, and its error and warning counts.

    Args:
        site_url: Property exactly as returned by list_sites.
    """
    response = get_service().sitemaps().list(siteUrl=site_url).execute()
    return response.get("sitemap", [])


@tool(parse_docstring=True)
def get_sitemap_details(site_url: str, sitemap_url: str) -> dict:
    """Get the processing details of one sitemap.

    Shows whether it was processed, when Google last read it, errors and
    warnings, and how many URLs it contains per content type. The `submitted`
    count is URLs discovered in the sitemap, NOT the number of indexed pages.

    Args:
        site_url: Property exactly as returned by list_sites.
        sitemap_url: Full sitemap URL, e.g. 'https://example.com/sitemap.xml'.
    """
    return get_service().sitemaps().get(siteUrl=site_url, feedpath=sitemap_url).execute()


@tool(parse_docstring=True)
def compare_search_periods(
    site_url: str,
    days: int = 30,
    dimension: Literal["query", "page"] | None = None,
    row_limit: int = 50,
) -> dict:
    """Compare search performance of the last N days with the N days before that.

    Without a dimension it compares the site totals. With 'page' or 'query' it lists
    the pages or keywords whose clicks changed the most, up or down.
    For position, a negative change is an improvement (closer to rank 1).
    A position of None means the item had no impressions in that period.

    Args:
        site_url: Property exactly as returned by list_sites.
        days: Length of each period in days.
        dimension: Leave empty for site totals, or 'page' / 'query' for a breakdown.
        row_limit: Maximum number of pages or keywords to return.
    """
    current_start, current_end = date_range(days)
    previous_start, previous_end = date_range(days, days_before=days)

    result = {
        "current_period": {"start_date": current_start, "end_date": current_end},
        "previous_period": {"start_date": previous_start, "end_date": previous_end},
    }

    if dimension is None:
        current = totals(site_url, current_start, current_end)
        previous = totals(site_url, previous_start, previous_end)
        result["current"] = current
        result["previous"] = previous
        result["change"] = difference(current, previous)
        return result

    current_rows = run_query(site_url, current_start, current_end, [dimension], row_limit=None)
    previous_rows = run_query(site_url, previous_start, previous_end, [dimension], row_limit=None)
    current_by_key = {row[dimension]: row for row in current_rows}
    previous_by_key = {row[dimension]: row for row in previous_rows}

    items = []
    for key in current_by_key.keys() | previous_by_key.keys():
        current = only_metrics(current_by_key.get(key, NO_DATA))
        previous = only_metrics(previous_by_key.get(key, NO_DATA))
        items.append(
            {
                dimension: key,
                "current": current,
                "previous": previous,
                "change": difference(current, previous),
            }
        )

    items.sort(key=lambda item: abs(item["change"]["clicks"]), reverse=True)
    result["items"] = items[:row_limit]
    return result


@tool(parse_docstring=True)
def get_keyword_opportunities(
    site_url: str,
    days: int = 30,
    min_impressions: int = 100,
    max_ctr: float = 0.03,
    min_position: float = 3,
    max_position: float = 20,
    row_limit: int = 50,
) -> list[dict]:
    """Find keywords with many impressions but few clicks that already rank fairly well.

    These are good candidates for improving the title, meta description or content
    of the ranking page. All keywords Google returns are scanned, then sorted by
    impressions, highest first.

    Args:
        site_url: Property exactly as returned by list_sites.
        days: How many recent days to analyze.
        min_impressions: Ignore keywords with fewer impressions than this.
        max_ctr: Keep keywords with a CTR at or below this, as a fraction (0.03 = 3%).
        min_position: Best average position to include.
        max_position: Worst average position to include.
        row_limit: Maximum number of keywords to return.
    """
    start_date, end_date = date_range(days)
    rows = run_query(site_url, start_date, end_date, ["query"], row_limit=None)

    opportunities = [
        row
        for row in rows
        if row["impressions"] >= min_impressions
        and row["ctr"] <= max_ctr
        and min_position <= row["position"] <= max_position
    ]
    opportunities.sort(key=lambda row: row["impressions"], reverse=True)
    return opportunities[:row_limit]


@tool(parse_docstring=True)
def get_page_performance(
    site_url: str,
    page_url: str,
    days: int = 30,
    row_limit: int = 20,
) -> dict:
    """Analyze one page: its totals plus its top keywords, countries and devices.

    Args:
        site_url: Property exactly as returned by list_sites.
        page_url: Full URL of the page, e.g. 'https://example.com/blog/post'.
        days: How many recent days to analyze.
        row_limit: Maximum number of keywords and countries to return.
    """
    start_date, end_date = date_range(days)
    page_filter = [{"dimension": "page", "operator": "equals", "expression": page_url}]

    return {
        "page": page_url,
        "start_date": start_date,
        "end_date": end_date,
        "totals": totals(site_url, start_date, end_date, page_filter),
        "queries": run_query(site_url, start_date, end_date, ["query"], page_filter, row_limit),
        "countries": run_query(site_url, start_date, end_date, ["country"], page_filter, row_limit),
        "devices": run_query(site_url, start_date, end_date, ["device"], page_filter),
    }


@tool(parse_docstring=True)
def get_keyword_performance(site_url: str, keyword: str, days: int = 30) -> dict:
    """Analyze one keyword: its totals, the pages shown for it, and its daily trend.

    If several pages appear for the same keyword it may hint at cannibalization,
    but that alone does not prove it.

    Args:
        site_url: Property exactly as returned by list_sites.
        keyword: The search query exactly as users typed it, e.g. 'best vpn for iran'.
        days: How many recent days to analyze.
    """
    start_date, end_date = date_range(days)
    keyword_filter = [{"dimension": "query", "operator": "equals", "expression": keyword}]

    trend = run_query(site_url, start_date, end_date, ["date"], keyword_filter, row_limit=days)
    trend.sort(key=lambda row: row["date"])

    return {
        "keyword": keyword,
        "start_date": start_date,
        "end_date": end_date,
        "totals": totals(site_url, start_date, end_date, keyword_filter),
        "pages": run_query(site_url, start_date, end_date, ["page"], keyword_filter),
        "daily_trend": trend,
    }


@tool(parse_docstring=True)
def get_device_performance(site_url: str, days: int = 30) -> list[dict]:
    """Compare performance on desktop, mobile and tablet.

    Each row also has click_share: that device's fraction of all clicks (0.7 = 70%).

    Args:
        site_url: Property exactly as returned by list_sites.
        days: How many recent days to analyze.
    """
    start_date, end_date = date_range(days)
    rows = run_query(site_url, start_date, end_date, ["device"])

    total_clicks = sum(row["clicks"] for row in rows)
    for row in rows:
        row["click_share"] = round(row["clicks"] / total_clicks, 4) if total_clicks else 0
    return rows


@tool(parse_docstring=True)
def google_search(
    query: str,
    country: str = "us",
    language: str = "en",
    num_results: int = 10,
) -> dict:
    """Search Google live (via Serper) to see who ranks right now for a query.

    Returns the organic results (position, title, link, snippet) plus, when present,
    People Also Ask questions, related searches, the AI answer box and the knowledge
    graph. Use it to find competitors, study SERP features, and compare a site's
    real rankings with Search Console data. Results are a snapshot for one country
    and language, not personalized.

    Args:
        query: The search query, e.g. 'best vpn for iran'.
        country: 2-letter Google country code, e.g. 'us', 'gb', 'ir'.
        language: 2-letter language code, e.g. 'en', 'fa'.
        num_results: How many organic results to return (max 100).
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {"error": "SERPER_API_KEY is not set in .env"}

    payload = json.dumps(
        {"q": query, "gl": country, "hl": language, "num": min(num_results, 100)}
    ).encode()
    request = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        return {"error": f"Serper returned HTTP {error.code}: {error.reason}"}
    except urllib.error.URLError as error:
        return {"error": f"Could not reach Serper: {error.reason}"}

    result = {
        "query": query,
        "organic": [
            {
                "position": item.get("position"),
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            }
            for item in data.get("organic", [])
        ],
    }
    for key in ("answerBox", "knowledgeGraph", "peopleAlsoAsk", "relatedSearches"):
        if data.get(key):
            result[key] = data[key]
    return result


TOOLS = [
    list_sites,
    search_analytics_query,
    inspect_url,
    list_sitemaps,
    get_sitemap_details,
    compare_search_periods,
    get_keyword_opportunities,
    get_page_performance,
    get_keyword_performance,
    get_device_performance,
    google_search,
]
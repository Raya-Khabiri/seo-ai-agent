# SEO Agent

SEO Agent is an AI assistant that answers SEO questions using your real data. You chat with it in a web page (or in the terminal), and it reads your Google Search Console and Google Analytics data, checks live pages with a browser, plans bigger jobs with a to-do list, and can build a shareable HTML dashboard. It speaks English and Persian.


### Live Demo

Explore an interactive SEO performance dashboard generated
using the project's reporting architecture.

**[View Interactive Dashboard](https://raya-khabiri.github.io/seo-ai-agent/seo-agent-demo-dashboard.html)**

> **Note:** This demo uses synthetic data to illustrate
> the agent's reporting capabilities. No private analytics
> data is included.

### Build Status

[![Python Tests](https://github.com/Raya-Khabiri/seo-ai-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/Raya-Khabiri/seo-ai-agent/actions/workflows/tests.yml)


## Features

- **Search Console tools** – clicks, impressions, CTR, rankings, keyword opportunities, URL inspection and sitemaps.
- **Google Analytics (GA4) via MCP** – users, sessions, engagement and traffic sources.
- **Live Google results via Serper** – see what ranks right now and who your competitors are (see the note under [Available tools](#available-tools)).
- **Playwright browser** – opens pages and checks titles, meta tags, headings and content.
- **Memory** – the agent remembers the conversation. "New chat" starts a fresh one.
- **To-do planning** – for multi-step work the agent writes a plan and ticks it off as it goes.
- **HTML dashboards** – KPIs, charts, tables and recommendations in one downloadable file.
- **Gradio web UI** – streaming answers, tool steps you can expand, a live to-do panel, light and dark mode.

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.14 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (installs and runs the project)
- [Node.js](https://nodejs.org/) (provides `npx`, used to start the Playwright MCP server)
- An API key for an OpenAI-compatible model
- A [Serper](https://serper.dev) API key
- A Google Cloud service account (setup below)

## Google service account setup

The agent signs in to Google as a **service account**, a robot account with its own email address. You create it once and then give that email read access to your Search Console and Analytics.

### 1. Create or choose a Google Cloud project

1. Open the [Google Cloud console](https://console.cloud.google.com/).
2. Use the project picker at the top to choose a project, or create a new one.
3. Copy the **Project ID** (it is not the same as the project name). You will need it for `GOOGLE_CLOUD_PROJECT`.

Docs: [Creating and managing projects](https://cloud.google.com/resource-manager/docs/creating-managing-projects)

### 2. Enable the APIs

Open each link below with your project selected and click **Enable**:

- [Google Search Console API](https://console.cloud.google.com/apis/library/searchconsole.googleapis.com)
- [Google Analytics Data API](https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com)
- [Google Analytics Admin API](https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com)

Docs: [Enabling APIs](https://cloud.google.com/apis/docs/getting-started#enabling_apis)

### 3. Create the service account and a JSON key

1. In the console go to **IAM & Admin → Service accounts** and click **Create service account**. Give it a name such as `seo-agent`. You do not need to grant it any Google Cloud roles.
2. Click the new service account's email, open the **Keys** tab, then choose **Add key → Create new key → JSON → Create**.
3. A JSON file downloads. Move it into this project as `credentials/google-service-account.json`.

You can only download the key once. If you lose it, create a new one. If "Create new key" is blocked, your organization may have a policy that disables key creation, so ask your Google Cloud admin.

Docs: [Create service accounts](https://cloud.google.com/iam/docs/service-accounts-create) · [Create and delete service account keys](https://cloud.google.com/iam/docs/keys-create-delete)

### 4. Copy the service account email

Open the JSON file and copy the value of `client_email`. It looks like `seo-agent@your-project-id.iam.gserviceaccount.com`.

### 5. Give the service account access in Search Console

1. Open [Search Console](https://search.google.com/search-console) and pick your property.
2. Go to **Settings → Users and permissions**. You must be a property **owner** to see this page.
3. Click **Add user**, paste the service account email and choose **Restricted**. The agent only reads data, so Restricted is enough.

Docs: [Managing owners, users, and permissions](https://support.google.com/webmasters/answer/7687615)

### 6. Give the service account access in Google Analytics 4

1. Open [Google Analytics](https://analytics.google.com/) and go to **Admin**.
2. Under **Property**, click **Property access management**.
3. Click **+** and choose **Add users**, paste the service account email, and give it the **Viewer** role.

You need the Administrator role to add users.

Docs: [Access and data-restriction management](https://support.google.com/analytics/answer/9305587) · [Add, edit, and delete Analytics users](https://support.google.com/analytics/answer/9305788)

### Common errors and fixes

| Problem | Likely cause and fix |
| --- | --- |
| `list_sites` returns an empty list | The service account email was not added to the Search Console property. Repeat step 5. |
| `403` error | The API is not enabled in your project (step 2), or the email has no access to that property (steps 5 and 6). |
| "User does not have sufficient permission for site" | The `site_url` is wrong. Copy it exactly from `list_sites`. |
| Wrong `site_url` format | A URL-prefix property looks like `https://example.com/` (with the trailing slash). A domain property looks like `sc-domain:example.com`. Use the one `list_sites` shows. |
| Analytics returns no properties | The email was not added in Property access management (step 6), or the Analytics APIs are not enabled. |

## Getting a Serper API key

1. Sign up at [serper.dev](https://serper.dev).
2. Open your dashboard and copy your API key.
3. Put it in `.env` as `SERPER_API_KEY`.

## Installation and running

```bash
uv sync
cp .env.example .env
```

Edit `.env` with your own values (see the table below), then start the app:

```bash
uv run python app.py
```

Open http://127.0.0.1:7860 in your browser. To use the terminal version instead:

```bash
uv run python main.py
```

The first start takes a few seconds while the Google Analytics and Playwright servers launch. They stay open while the app runs and close when you stop it.

## Report approval

The agent never creates a dashboard on its own. Before `create_dashboard` runs, it pauses and shows you the draft with three choices:

- **Approve** – create the dashboard exactly as drafted.
- **Edit** – change the draft, then create it.
- **Reject** – the agent asks what to change, then revises the report and asks again.

**In the web UI**, the draft appears in the chat with **Approve**, **Edit** and **Reject** buttons. Edit opens a box with the draft as JSON. Change what you want and click **Save and approve**. If the JSON is not valid, it tells you what to fix. You can also just type what you want changed (for example "add a weekly trend chart") instead of clicking, and the agent will revise the report.

**In the terminal**, the agent prints a short summary and asks `[a]pprove / [e]dit / [r]eject`. Choosing `e` writes the draft to `reports/draft.json`. Edit it in any editor, save it, and press Enter. If the file is not valid, you will see the error and can fix it and press Enter again.

## Environment variables

| Variable | What it is | Example |
| --- | --- | --- |
| `MODEL_NAME` | Name of the chat model to use. | `gpt-4.1` |
| `OPENAI_API_KEY` | API key for your OpenAI-compatible provider. | `your-api-key-here` |
| `OPENAI_BASE_URL` | API address of your provider. | `https://api.openai.com/v1` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the service account JSON key. | `credentials/google-service-account.json` |
| `GOOGLE_CLOUD_PROJECT` | Your Google Cloud project ID. | `your-google-cloud-project-id` |
| `SERPER_API_KEY` | Serper key for live Google results. | `your-serper-api-key-here` |

## Available tools

| Tool | What it does |
| --- | --- |
| `list_sites` | Lists the Search Console properties the account can access. |
| `search_analytics_query` | Queries clicks, impressions, CTR and position, grouped by query, page, country, device or date. |
| `inspect_url` | Shows how Google sees one URL: index status, canonical, crawl and mobile info. |
| `list_sitemaps` | Lists the sitemaps submitted for a property. |
| `get_sitemap_details` | Shows the processing details, errors and warnings of one sitemap. |
| `compare_search_periods` | Compares the last N days with the N days before, for totals, pages or keywords. |
| `get_keyword_opportunities` | Finds keywords with many impressions, low CTR and a decent ranking. |
| `get_page_performance` | Analyzes one page: totals, top keywords, countries and devices. |
| `get_keyword_performance` | Analyzes one keyword: totals, ranking pages and daily trend. |
| `get_device_performance` | Compares desktop, mobile and tablet. |
| `create_dashboard` | Builds an HTML dashboard from the data the agent collected. |
| Google Analytics tools (MCP) | Account and property info and GA4 reports (`run_report`, `run_realtime_report` and more). |
| Playwright tools (MCP) | Open pages, read content, click and take snapshots in a headless browser. |
| To-do list | The agent plans multi-step work with `write_todos`. |
| `google_search` | Retrieves live Google search results through the Serper API. |

## Example prompts

- "List my Search Console sites."
- "Compare the last 28 days with the previous 28 days for my main site."
- "Find keyword opportunities for https://example.com/."
- "Which pages lost the most clicks this month?"
- "Open my homepage and check its title, meta description and headings."
- "Build a full SEO dashboard for my main site."
- "سایت من در ۲۸ روز گذشته چطور عمل کرده است؟"

## Project structure

```
app.py          Gradio web UI (streaming chat, tool steps, to-do panel, dashboard tab)
main.py         Builds the agent (shared by the UI) and runs the terminal chat
tools.py        Search Console tools
dashboard.py    create_dashboard tool that writes the HTML report
reports/        Generated dashboards (ignored by git)
credentials/    Your Google service account key (ignored by git)
.env.example    Template for your .env file
pyproject.toml  Project dependencies
```

## Security

Never commit `.env` or anything in `credentials/`. They contain secrets that give access to your data and your paid APIs. The included `.gitignore` already excludes them. If a key ever leaks, delete it in its provider's console and create a new one.


## Testing

This project uses **pytest** for automated testing.

Run the test suite locally:

```bash
uv sync
uv run pytest -q
```

The tests cover:

- SEO metric change calculations
- Google SERP response parsing using mocked Serper API responses

### Continuous Integration

GitHub Actions automatically runs the test suite on every push and pull request.

The CI workflow is defined in `.github/workflows/tests.yml`.

[![Python Tests](https://github.com/Raya-Khabiri/seo-ai-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/Raya-Khabiri/seo-ai-agent/actions/workflows/tests.yml)


## Evaluation

The project includes a lightweight evaluation framework
for assessing SEO analysis quality.

Evaluation dimensions include:
- Factual accuracy
- Evidence groundedness
- Actionability
- Uncertainty calibration
- Hallucination detection

A documented case study identified an incorrect
interpretation of Google Search Console average position.

The system prompt was revised, and a regression test
was added to detect the known error pattern.

A qualitative follow-up review showed improved ranking
interpretation and uncertainty communication.

See:
- [Evaluation methodology](evaluation/README.md)
- [Evaluation results](evaluation/results.md)
- [Evaluation cases](evaluation/cases.json)

**Limitation:** This evaluation is a qualitative case
study, not a statistically validated accuracy benchmark.

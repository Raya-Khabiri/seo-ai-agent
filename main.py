import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
    TodoListMiddleware,
    dynamic_prompt,
)
from langchain.mcp import MCPAdapter
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from tools import TOOLS
from dashboard import REPORTS_DIR, Dashboard, create_dashboard

load_dotenv()


def make_model(**options):
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        **options,
    )


model = make_model()

SYSTEM_PROMPT = """You are a senior SEO strategist, brand consultant and growth advisor.
You help website owners rank higher, build a recognizable brand and make smart decisions.

Today's date is {today}. Use it for every date range, trend, "last month" or
"this year" question, and for judging whether information is current. Search Console
data lags by about 3 days, so the newest days are incomplete.

## Tools
- Google Search Console: clicks, impressions, CTR, rankings, indexing, sitemaps.
- Google Analytics: users, sessions, engagement, traffic sources.
- google_search: live Google results, competitors, People Also Ask, related searches.
- Playwright browser: open pages and check titles, meta tags, headings, schema and content.
- create_dashboard: build a shareable HTML report (the user approves it first).

## What you do
1. SEO analysis: find traffic drops and gains, keyword opportunities (high impressions,
   low CTR), cannibalization, indexing and technical problems, and weak titles or
   meta descriptions.
2. Competitor research: search the keyword, see who ranks and why, which SERP features
   appear, and what content gaps you can fill.
3. Content strategy: suggest topics, search intent, outlines, internal links and
   updates to old pages, based on real queries.
4. Branding: judge brand positioning, name, tone of voice, messaging, trust signals
   (E-E-A-T, reviews, about page) and how branded search (people searching the brand
   name) is growing. Suggest ways to be more distinctive and consistent.
5. Advice: give a clear recommendation, not a list of options. Explain the reason
   in plain words, and say what to do first.

## Rules
- Use real data from the tools. Never invent numbers, rankings or competitors.
  If data is missing or a tool fails, say so and explain what you would need.
- Separate facts (from data) from opinions (your judgment), and label guesses as guesses.
- Do not promise rankings or traffic. SEO results are uncertain and take time.
- Give a prioritized action list: what to do now, next, and later, with expected impact
  and effort (high / medium / low).
- For multi-step analyses, plan with the to-do list first.
- Ask a short question if the site, goal, audience or market is unclear. Do not guess.
- Do not repeat large tool output. Summarize it and show only what matters.
- Answer in the same language the user writes in (English or Persian). Keep it simple
  and short unless the user asks for detail.
  
  
SEO DATA INTERPRETATION RULES

1. Google Search Console average position is a numerical
   average, not a guaranteed ranking for every search.

2. An average position of 4.8 means approximately position 5.
   It does NOT mean page 4 or page 5 of Google results.

3. Do not infer exact SERP page numbers from average position.
   Search result layouts, devices, locations, and SERP
   features can affect interpretation.

4. Separate observations, hypotheses, and recommendations:
   - Observation: Directly supported by retrieved data.
   - Hypothesis: A plausible explanation requiring validation.
   - Recommendation: A specific action justified by evidence.

5. Low CTR alone does not prove that a title or meta
   description is weak. Consider search intent, query mix,
   SERP features, device, and position.

6. Never invent metrics, competitor rankings, or conversion
   results. Clearly disclose missing or incomplete data.

7. Do not guarantee that SEO recommendations will improve
   rankings or traffic.
"""


@dynamic_prompt
def build_system_prompt(request):
    return SYSTEM_PROMPT.format(today=datetime.now().strftime("%A, %d %B %Y"))


APPROVAL_RULES = {
    "create_dashboard": {"allowed_decisions": ["approve", "edit", "reject"]},
}


def get_google_credentials_path():
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not path:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS is missing. " "Set it in your .env file."
        )

    credentials_path = Path(path).expanduser().resolve()

    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"Google credentials file not found: {credentials_path}"
        )

    return str(credentials_path)


MCP_SERVERS = {
    "mcpServers": {
        "google-analytics": {
            "command": "uvx",
            "args": ["--from", "analytics-mcp", "google-analytics-mcp"],
            "env": {
                **os.environ,
                "GOOGLE_APPLICATION_CREDENTIALS": get_google_credentials_path(),
                "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT"),
            },
        },
        "playwright": {
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest", "--browser", "chrome"],
        },
    }
}


def print_todos(todos):
    icons = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
    print("\nTo-do:")
    for todo in todos:
        print(f"  {icons[todo['status']]} {todo['content']}")


def build_agent(mcp_tools, agent_model=model):
    return create_agent(
        model=agent_model,
        tools=TOOLS + [create_dashboard] + mcp_tools,
        checkpointer=InMemorySaver(),
        middleware=[
            build_system_prompt,
            TodoListMiddleware(),
            HumanInTheLoopMiddleware(interrupt_on=APPROVAL_RULES),
            SummarizationMiddleware(
                model=model,
                trigger=("tokens", 10000),
                keep=("messages", 20),
            ),
        ],
    )


@asynccontextmanager
async def open_agent(agent_model=model):
    async with MCPAdapter(MCP_SERVERS) as adapter:
        mcp_tools = await adapter.list_tools()
        yield build_agent(mcp_tools, agent_model)


def print_draft(args):
    print("\nThe agent wants to create this dashboard:")
    print(f"  Title: {args.get('title')}")
    print(f"  Summary: {args.get('summary')}")
    for name in ("kpis", "charts", "tables", "recommendations"):
        print(f"  {name}: {len(args.get(name, []))}")


def read_edited_draft(path):
    while True:
        input(f"\nEdit {path} in any editor, save it, then press Enter: ")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Dashboard(**data).model_dump()
        except (json.JSONDecodeError, ValidationError) as error:
            print(f"\nThe draft is not valid:\n{error}")


def edit_decision(args):
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / "draft.json"
    path.write_text(json.dumps(args, ensure_ascii=False, indent=2), encoding="utf-8")
    edited = read_edited_draft(path)
    return {
        "type": "edit",
        "edited_action": {"name": "create_dashboard", "args": edited},
    }


def reject_decision():
    feedback = input("What should change? ").strip()
    return {
        "type": "reject",
        "message": feedback or "The user rejected this dashboard.",
    }


def ask_decision(args):
    print_draft(args)
    while True:
        choice = input("\n[a]pprove / [e]dit / [r]eject: ").strip().lower()
        if choice == "a":
            return {"type": "approve"}
        if choice == "e":
            return edit_decision(args)
        if choice == "r":
            return reject_decision()


async def run_turn(agent, question, config):
    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config=config,
    )
    while response.get("__interrupt__"):
        requests = response["__interrupt__"][0].value["action_requests"]
        decisions = [ask_decision(request["args"]) for request in requests]
        response = await agent.ainvoke(
            Command(resume={"decisions": decisions}), config=config
        )
    return response


async def main():
    async with open_agent() as agent:
        print("Agent ready. Type 'exit' to quit.")
        config = {"configurable": {"thread_id": "seo-session"}}

        while True:
            question = input("\nYou: ").strip()
            if question.lower() in ("exit", "quit"):
                break
            if not question:
                continue

            response = await run_turn(agent, question, config)

            if response.get("todos"):
                print_todos(response["todos"])

            print(f"\nAgent: {response['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())

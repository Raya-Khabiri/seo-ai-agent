import json
import time
import uuid
from types import SimpleNamespace
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

import gradio as gr
import uvicorn
from fastapi import FastAPI
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command
from pydantic import ValidationError

import dashboard
from dashboard import Dashboard
from main import make_model, open_agent

dashboard.OPEN_BROWSER = False

RUNTIME = {}
ui = SimpleNamespace()
EXTRA_REJECTION = {"type": "reject", "message": "Please create one report at a time."}
REJECT_MESSAGE = "The user rejected this report. Ask them briefly what to change, then wait for their answer."
APPROVAL_OPTIONS = [
    {"value": "approve", "label": "✅ Approve"},
    {"value": "edit", "label": "✏️ Edit"},
    {"value": "reject", "label": "❌ Reject"},
]
STREAMING_SAFE = {"parallel_tool_calls": False}
PREVIEW_LENGTH = 700

EXAMPLES = {
    "List my sites": "List my Search Console sites.",
    "Compare 28 days": "Compare the last 28 days with the previous 28 days for my main site.",
    "Keyword opportunities": "Find keyword opportunities for my main site.",
    "Full SEO dashboard": "Build a full SEO dashboard for my main site.",
}

NO_TODOS = '<div class="todo-empty">No plan yet. The agent adds one for bigger tasks.</div>'
NO_DASHBOARD = '<div class="todo-empty">No dashboard yet. Ask the agent to build one.</div>'

TODO_ICONS = {"pending": "○", "in_progress": "◐", "completed": "✓"}
TODO_LABELS = {"pending": "Pending", "in_progress": "In progress", "completed": "Done"}

THEME = gr.themes.Soft(
    primary_hue="indigo",
    neutral_hue="slate",
    radius_size="lg",
    font=[gr.themes.GoogleFont("Inter"), gr.themes.GoogleFont("Vazirmatn"), "system-ui", "sans-serif"],
)

CSS = """
.app-header { display: flex; align-items: center; gap: 14px; padding: 8px 4px 16px; }
.app-logo { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center;
  font-size: 22px; color: white; background: linear-gradient(135deg, #6366f1, #8b5cf6); }
.app-title { font-size: 24px; font-weight: 700; line-height: 1.2; }
.app-subtitle { color: var(--body-text-color-subdued); font-size: 14px; }

.message p, .message li, .message td, .message th, .message h1, .message h2, .message h3 {
  unicode-bidi: plaintext; text-align: start; }
textarea { unicode-bidi: plaintext; text-align: start; }

.side-card { border: 1px solid var(--border-color-primary); border-radius: 14px; padding: 14px;
  background: var(--background-fill-secondary); }
.todo-title { font-weight: 600; margin-bottom: 10px; }
.todo-empty { color: var(--body-text-color-subdued); font-size: 14px; padding: 8px 2px; }
.todo-item { display: flex; gap: 10px; align-items: flex-start; padding: 9px 10px; margin-bottom: 8px;
  border-radius: 10px; border: 1px solid var(--border-color-primary); background: var(--background-fill-primary);
  unicode-bidi: plaintext; }
.todo-icon { font-size: 16px; line-height: 1.4; width: 18px; text-align: center; flex-shrink: 0; }
.todo-text { flex: 1; font-size: 14px; line-height: 1.5; }
.todo-state { font-size: 11px; color: var(--body-text-color-subdued); white-space: nowrap; }
.todo-item.in_progress { border-color: #6366f1; box-shadow: 0 0 0 1px #6366f1 inset; }
.todo-item.in_progress .todo-icon { color: #6366f1; animation: spin 1.6s linear infinite; }
.todo-item.completed .todo-icon { color: #16a34a; }
.todo-item.completed .todo-text { color: var(--body-text-color-subdued); text-decoration: line-through; }
@keyframes spin { to { transform: rotate(360deg); } }

.dashboard-frame { width: 100%; height: 75vh; border: 1px solid var(--border-color-primary);
  border-radius: 12px; background: white; }
"""

HEADER = """
<div class="app-header">
  <div class="app-logo">🔍</div>
  <div>
    <div class="app-title">SEO Agent</div>
    <div class="app-subtitle">Search Console, Analytics and live research in one chat</div>
  </div>
</div>
"""


def new_thread_id():
    return str(uuid.uuid4())


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def short_preview(text):
    text = text.replace("```", "'''")
    if len(text) > PREVIEW_LENGTH:
        return text[:PREVIEW_LENGTH] + "\n… (shortened)"
    return text


def render_todos(todos):
    if not todos:
        return NO_TODOS
    items = ""
    for todo in todos:
        status = todo["status"]
        items += (
            f'<div class="todo-item {status}">'
            f'<span class="todo-icon">{TODO_ICONS[status]}</span>'
            f'<span class="todo-text">{escape(todo["content"])}</span>'
            f'<span class="todo-state">{TODO_LABELS[status]}</span>'
            "</div>"
        )
    return f'<div class="todo-title">Agent plan</div>{items}'



def frame(page, css_class):
    return f'<iframe class="{css_class}" sandbox="allow-scripts" srcdoc="{escape(page, quote=True)}"></iframe>'


def render_dashboard_frame(path):
    return frame(Path(path).read_text(encoding="utf-8"), "dashboard-frame")


def format_validation_error(error):
    lines = []
    for item in error.errors():
        place = ".".join(str(part) for part in item["loc"])
        lines.append(f"- **{place}**: {item['msg']}")
    return "\n".join(lines)


def step_body(args, result=None):
    body = "**Arguments**\n````json\n" + json.dumps(args, ensure_ascii=False, indent=2) + "\n````"
    if result is not None:
        body += "\n\n**Result**\n````\n" + short_preview(result) + "\n````"
    return body


def approval_message(args):
    counts = ", ".join(
        f"{len(args.get(name, []))} {name}" for name in ("kpis", "charts", "tables", "recommendations")
    )
    text = (
        "### ✋ Approval needed\n"
        "The agent wants to create this dashboard:\n\n"
        f"**{args.get('title', '')}**  \n{args.get('period', '')}\n\n"
        f"{args.get('summary', '')}\n\n"
        f"_{counts}_\n\n"
        "Choose below, or just type what to change."
    )
    return gr.ChatMessage(role="assistant", content=text, options=APPROVAL_OPTIONS)


def to_chat_messages(history):
    messages = []
    for item in history:
        if isinstance(item, gr.ChatMessage):
            messages.append(item)
        else:
            messages.append(
                gr.ChatMessage(
                    role=item["role"],
                    content=text_of(item["content"]),
                    metadata=item.get("metadata") or {},
                )
            )
    return messages


def hide_editor():
    return {ui.editor: gr.Column(visible=False)}


def show_editor(args):
    return {
        ui.editor: gr.Column(visible=True),
        ui.edit_json: json.dumps(args, ensure_ascii=False, indent=2),
        ui.edit_error: "",
    }


class Turn:
    def __init__(self, history, question=None):
        self.history = to_chat_messages(history)
        if question:
            self.history.append(gr.ChatMessage(role="user", content=question))
        self.text_message = None
        self.steps = {}
        self.seen_ids = set()
        self.changes = {}
        self.shown_args = {}

    def add_text(self, text):
        if not text:
            return
        if self.text_message is None:
            self.text_message = gr.ChatMessage(role="assistant", content="")
            self.history.append(self.text_message)
        self.text_message.content += text

    def end_text(self):
        self.text_message = None

    def add_step(self, call_id, name, args):
        message = gr.ChatMessage(
            role="assistant",
            content=step_body(args),
            metadata={"title": f"🔧 {name}", "id": call_id, "status": "pending"},
        )
        self.steps[call_id] = (message, args, time.time())
        self.history.append(message)

    def add_tool_calls(self, tool_calls):
        for call in tool_calls:
            if call["name"] != "create_dashboard":
                self.add_step(call["id"], call["name"], call["args"])

    def finish_tool_call(self, tool_message):
        if tool_message.tool_call_id not in self.steps and tool_message.name == "create_dashboard":
            self.add_step(tool_message.tool_call_id, "create_dashboard", self.shown_args)
        entry = self.steps.get(tool_message.tool_call_id)
        if entry is None:
            return
        message, args, started = entry
        result = text_of(tool_message.content)
        failed = tool_message.status == "error"
        name = message.metadata["title"].removeprefix("🔧 ").removeprefix("❌ ").removesuffix(" failed")
        message.content = step_body(args, result)
        message.metadata["title"] = f"❌ {name} failed" if failed else f"🔧 {name}"
        message.metadata["status"] = "done"
        message.metadata["duration"] = round(time.time() - started, 1)
        if tool_message.name == "create_dashboard" and not failed:
            self.show_dashboard(result)

    def show_dashboard(self, result):
        path = result.removeprefix("Dashboard saved to").strip()
        if not Path(path).exists():
            return
        self.changes[ui.dashboard_panel] = render_dashboard_frame(path)
        self.changes[ui.download] = gr.DownloadButton(
            "Download dashboard (.html)", value=str(Path(path).resolve()), interactive=True
        )
        self.history.append(
            gr.ChatMessage(role="assistant", content="📊 Dashboard ready. Open the **Dashboard** tab to see it.")
        )
        self.end_text()

    def ask_for_approval(self, requests):
        self.end_text()
        self.history.append(approval_message(requests[0]["args"]))
        self.changes[ui.draft] = {"args": requests[0]["args"], "count": len(requests)}

    def add_error(self, error):
        self.end_text()
        self.history.append(
            gr.ChatMessage(role="assistant", content=f"⚠️ Something went wrong:\n\n`{error}`")
        )

    def handle_update(self, update):
        if "__interrupt__" in update:
            self.ask_for_approval(update["__interrupt__"][0].value["action_requests"])
            return
        for node_update in update.values():
            if not isinstance(node_update, dict):
                continue
            if "todos" in node_update:
                self.changes[ui.todo_panel] = render_todos(node_update["todos"])
            for message in node_update.get("messages", []):
                self.handle_message(message)

    def handle_message(self, message):
        if message.id in self.seen_ids:
            return
        self.seen_ids.add(message.id)
        if isinstance(message, AIMessage) and message.tool_calls:
            self.end_text()
            self.add_tool_calls(message.tool_calls)
        elif isinstance(message, AIMessage):
            if self.text_message is None and text_of(message.content):
                self.add_text(text_of(message.content))
            self.end_text()
        elif isinstance(message, ToolMessage):
            self.finish_tool_call(message)

    def handle_token(self, chunk, metadata):
        if isinstance(chunk, AIMessageChunk) and metadata.get("langgraph_node") == "model":
            self.add_text(text_of(chunk.content))

    def snapshot(self):
        changes = {ui.chatbot: self.history, **self.changes}
        self.changes = {}
        return changes


async def stream_turn(turn, agent_input, thread_id):
    turn.changes[ui.draft] = None
    turn.changes.update(hide_editor())
    yield turn.snapshot()

    config = {"configurable": {"thread_id": thread_id}}
    try:
        async for mode, data in RUNTIME["agent"].astream(
            agent_input, config=config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                turn.handle_token(*data)
            else:
                turn.handle_update(data)
            yield turn.snapshot()
    except Exception as error:
        turn.add_error(error)
    yield turn.snapshot()


async def answer_approval(turn, decision, shown_args, draft, thread_id):
    turn.shown_args = shown_args
    decisions = [decision] + [EXTRA_REJECTION] * (draft["count"] - 1)
    command = Command(resume={"decisions": decisions})
    async for changes in stream_turn(turn, command, thread_id):
        yield changes


async def chat(question, history, draft, thread_id):
    question = (question or "").strip()
    if not question:
        yield {ui.box: gr.skip()}
        return

    turn = Turn(history or [], question)
    turn.changes[ui.box] = ""

    if draft:
        decision = {"type": "reject", "message": question}
        async for changes in answer_approval(turn, decision, draft["args"], draft, thread_id):
            yield changes
        return

    agent_input = {"messages": [{"role": "user", "content": question}]}
    async for changes in stream_turn(turn, agent_input, thread_id):
        yield changes


async def choose_option(event: gr.SelectData, draft, history, thread_id):
    choice = str(event.value).lower()
    if not draft:
        yield {ui.chatbot: gr.skip()}
        return

    turn = Turn(history or [])
    if "edit" in choice:
        yield {ui.chatbot: turn.history, **show_editor(draft["args"])}
        return

    if "approve" in choice:
        decision = {"type": "approve"}
    else:
        decision = {"type": "reject", "message": REJECT_MESSAGE}
    async for changes in answer_approval(turn, decision, draft["args"], draft, thread_id):
        yield changes


async def save_edit(edited_json, draft, history, thread_id):
    if not draft:
        yield {ui.edit_error: "Nothing to approve right now."}
        return
    try:
        args = Dashboard(**json.loads(edited_json)).model_dump()
    except json.JSONDecodeError as error:
        yield {ui.edit_error: f"⚠️ This is not valid JSON: {error}"}
        return
    except (ValidationError, TypeError) as error:
        message = format_validation_error(error) if isinstance(error, ValidationError) else str(error)
        yield {ui.edit_error: f"⚠️ Please fix this first:\n\n{message}"}
        return

    decision = {"type": "edit", "edited_action": {"name": "create_dashboard", "args": args}}
    async for changes in answer_approval(Turn(history or []), decision, args, draft, thread_id):
        yield changes


def start_new_chat():
    empty_download = gr.DownloadButton("Download dashboard (.html)", value=None, interactive=False)
    return {
        ui.chatbot: [],
        ui.thread_id: new_thread_id(),
        ui.draft: None,
        ui.todo_panel: NO_TODOS,
        ui.dashboard_panel: NO_DASHBOARD,
        ui.download: empty_download,
        ui.box: "",
        **hide_editor(),
    }


def build_editor():
    with gr.Column(visible=False, elem_classes="side-card") as ui.editor:
        gr.Markdown("**Edit the dashboard**, then save. Change any text or number below.")
        ui.edit_json = gr.Code(language="json", lines=16, show_label=False)
        ui.edit_error = gr.Markdown()
        ui.save_button = gr.Button("Save and approve", variant="primary")


def build_chat_area():
    with gr.Row(equal_height=False):
        with gr.Column(scale=3):
            ui.chatbot = gr.Chatbot(
                height="62vh",
                placeholder="Ask about your site's search performance, keywords, pages or traffic.",
                buttons=["copy_all"],
                show_label=False,
            )
            build_editor()
            with gr.Row():
                ui.box = gr.Textbox(
                    placeholder="Type your question in English or Persian…",
                    show_label=False,
                    container=False,
                    scale=6,
                    lines=1,
                    max_lines=6,
                    autofocus=True,
                )
                ui.send = gr.Button("Send", variant="primary", scale=1)
                ui.new_chat = gr.Button("New chat", scale=1)
            with gr.Row():
                ui.example_buttons = [gr.Button(label, size="sm") for label in EXAMPLES]
        with gr.Column(scale=1, min_width=280, elem_classes="side-card"):
            ui.todo_panel = gr.HTML(NO_TODOS)


def build_dashboard_tab():
    ui.download = gr.DownloadButton(
        "Download dashboard (.html)", value=None, interactive=False, variant="secondary"
    )
    ui.dashboard_panel = gr.HTML(NO_DASHBOARD)


def all_outputs():
    return [
        ui.chatbot, ui.thread_id, ui.draft, ui.todo_panel, ui.dashboard_panel, ui.download,
        ui.box, ui.editor, ui.edit_json, ui.edit_error,
    ]


def connect_events():
    outputs = all_outputs()
    chat_inputs = [ui.box, ui.chatbot, ui.draft, ui.thread_id]
    approval_inputs = [ui.draft, ui.chatbot, ui.thread_id]
    running = [
        ui.box.submit(chat, chat_inputs, outputs),
        ui.send.click(chat, chat_inputs, outputs),
        ui.chatbot.option_select(choose_option, approval_inputs, outputs),
        ui.save_button.click(save_edit, [ui.edit_json] + approval_inputs, outputs),
    ]
    for button, prompt in zip(ui.example_buttons, EXAMPLES.values()):
        running.append(
            button.click(lambda prompt=prompt: prompt, outputs=ui.box).then(chat, chat_inputs, outputs)
        )
    ui.new_chat.click(start_new_chat, outputs=outputs, cancels=running)


def build_ui():
    with gr.Blocks(title="SEO Agent", fill_width=True) as demo:
        ui.thread_id = gr.State()
        ui.draft = gr.State()

        gr.HTML(HEADER)
        with gr.Tabs():
            with gr.Tab("Chat"):
                build_chat_area()
            with gr.Tab("Dashboard"):
                build_dashboard_tab()

        demo.load(new_thread_id, outputs=ui.thread_id)
        connect_events()
    return demo


@asynccontextmanager
async def lifespan(app):
    # The API proxy never closes streamed responses, so the chat hangs on "queue".
    # Get each model reply in one piece instead of token by token.
    model = make_model(model_kwargs=STREAMING_SAFE, disable_streaming=True)
    async with open_agent(model) as agent:
        RUNTIME["agent"] = agent
        yield
    RUNTIME.clear()


def create_app():
    app = FastAPI(lifespan=lifespan)
    return gr.mount_gradio_app(app, build_ui(), path="/", theme=THEME, css=CSS)


if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=7860)

import os
import re
import json
from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent_helpers import (
    mcp_tools,
    get_available_files,
    normalize_tool_args,
    extract_result_text,
    create_file_response,
    delete_file_response,
    get_file_content_response,
    handle_slash_command,
    continue_pending_resolution,
    set_pending_resolution,
    answer_question_from_file,
    FileSuggestionError,
)


# ── Configuration ──────────────────────────────────────────────────────────────

MCP_client = os.environ.get("MCP_URL", "http://127.0.0.1:8080/mcp")
OLLAMA_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_model = os.environ.get("OLLAMA_MODEL", "llama3.1")

print("Using model:", OLLAMA_model)

llm = ChatOllama(
    model=OLLAMA_model,
    base_url=OLLAMA_url,
    temperature=0,
)


# ── State ──────────────────────────────────────────────────────────────────────

class State(TypedDict):
    messages: Annotated[list, add_messages]
    pending_action: list[Dict[str, Any]]


# ── Session / cache state ──────────────────────────────────────────────────────

file_content_cache: dict[str, str] = {}
summary_cache: dict[tuple[str, str], str] = {}
last_output_by_thread: dict[str, str] = {}
CURRENT_THREAD_ID: str | None = None

_sessions: dict[str, dict] = {}


# ── Core tools for normal chat flow ────────────────────────────────────────────

@tool
async def get_os_info() -> str:
    """Retrieves information about the operating system."""
    result = await mcp_tools(MCP_client, "get_os_info", {})

    if isinstance(result, dict):
        os_name = result.get("os_name", "unknown")
        platform = result.get("platform", "unknown")
        cwd = result.get("cwd", "unknown")
        source_dir = result.get("source_dir", "unknown")

        return (
            "Operating system information:\n\n"
            f"OS name: {os_name}\n"
            f"Platform: {platform}\n"
            f"Current working directory: {cwd}\n"
            f"Source directory: {source_dir}"
        )

    return extract_result_text(result)


@tool
async def list_files() -> str:
    """Lists files in a specified directory."""
    files = await get_available_files(MCP_client)
    if not files:
        return "No files found."
    return "\n".join(files)


@tool
async def create_file(file_name: str, content: str = "") -> str:
    """Creates a file with the specified content."""
    return await create_file_response(MCP_client, file_name, content)


@tool
async def delete_file(file_name: str) -> str:
    """Deletes a specified file."""
    try:
        return await delete_file_response(MCP_client, file_name)
    except FileSuggestionError as e:
        if CURRENT_THREAD_ID is not None:
            set_pending_resolution(_sessions, CURRENT_THREAD_ID, {"action": "delete"})
        return str(e)


@tool
async def get_file_content(file_name: str) -> str:
    """Reads and returns the contents of a file."""
    try:
        return await get_file_content_response(MCP_client, file_name, file_content_cache)
    except FileSuggestionError as e:
        if CURRENT_THREAD_ID is not None:
            set_pending_resolution(_sessions, CURRENT_THREAD_ID, {"action": "read"})
        return str(e)


TOOLS = [get_os_info, list_files, create_file, delete_file, get_file_content]
TOOL_NAMES = {tool.name for tool in TOOLS}
tool_node = ToolNode(TOOLS)
llm_with_tools = llm.bind_tools(TOOLS)


# ── Confirmation helpers ───────────────────────────────────────────────────────

Confirmation_words = ["yes", "y", "confirm", "ok", "okay"]
Denial_words = ["no", "n", "deny", "cancel", "stop"]


def confirmation_check(user_input: str) -> str:
    """Normalize yes/no confirmation replies."""
    user_input = user_input.strip().lower()
    if user_input in Confirmation_words:
        return "confirm"
    if user_input in Denial_words:
        return "deny"
    return "invalid"


def get_tool_call_id(tool_call: dict) -> str:
    """Generate a stable id for the tool call."""
    name = tool_call.get("name", "")
    args = tool_call.get("args", {}) or {}

    file_name = args.get("file_name")
    if isinstance(file_name, str):
        folder = os.path.dirname(file_name) or os.path.sep
        folder = os.path.normpath(folder)
        return f"{name}_folder_{folder}"

    return f"{name}_{hash(frozenset(args.items()))}"


confirmed_tool_calls: dict = {}


def add_tool_confirmation_to_dict(id: str, args: dict, user_confirmation: str):
    """Remember the user's confirmation decision for a tool call."""
    if confirmed_tool_calls.get(id):
        return
    confirmed_tool_calls[id] = {
        "tool_call": {"id": id, "args": args},
        "user_confirmation": user_confirmation,
    }


# ── Graph nodes ────────────────────────────────────────────────────────────────

def should_allow_tools(user_text: str) -> bool:
    """Decide whether the tool-enabled path should be used."""
    user_text = user_text.lower().strip()

    keywords = [
        "list", "show files", "list files",
        "read", "open",
        "delete", "remove",
        "create", "make",
        "save",
        "os", "system", "info", "contents",
        "based on", "what does", "what is in", "about", "from", "compare"
    ]

    file_extensions = [
        ".pdf", ".docx", ".doc", ".txt", ".csv",
        ".pptx", ".ppt", ".xlsx", ".xls", ".md", ".json"
    ]

    has_file_reference = any(ext in user_text for ext in file_extensions)

    return has_file_reference or any(k in user_text for k in keywords)


def should_answer_from_file(user_text: str) -> bool:
    """Return True when the user appears to be asking a question about a file."""
    text = user_text.lower().strip()

    question_markers = [
        "what", "who", "when", "where", "why", "how",
        "define", "definition", "according to", "based on",
        "does it say", "what does", "tell me about", "explain"
    ]

    file_extensions = [
        ".pdf", ".docx", ".doc", ".txt", ".csv",
        ".pptx", ".ppt", ".xlsx", ".xls", ".md", ".json"
    ]

    has_question_marker = any(marker in text for marker in question_markers)
    has_file_reference = any(ext in text for ext in file_extensions)

    return has_question_marker and has_file_reference


def get_last_user_message(messages) -> str:
    """Get the most recent user message content."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            return msg.content
    return ""


def get_last_tool_message_content(messages) -> str:
    """Get the most recent tool output as plain text."""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip().startswith("The content of the file "):
            return content
    return ""


def is_simple_question(text: str) -> bool:
    """Return True for simple conversational follow-ups that do not need tools."""
    text = text.lower().strip()

    simple_patterns = [
        "did you",
        "are you",
        "what did you",
        "where did you",
        "how did you",
        "is that from",
        "was that from",
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "what's my name",
        "what is my name",
    ]

    return any(p in text for p in simple_patterns)


def sanitize_tool_args(tool_name: str, tool_args: dict | None) -> dict:
    """Clean tool arguments so all tools behave consistently."""
    args = dict(tool_args or {})

    if tool_name in {"get_file_content", "delete_file", "create_file"}:
        args.pop("directory", None)

    if tool_name in {"get_os_info", "list_files"}:
        args = {}

    return args


def extract_json_tool_call(raw_text: str) -> dict | None:
    """Extract a tool call from raw JSON-like model output."""
    raw_text = raw_text.strip()
    if not raw_text:
        return None

    candidates = []

    if raw_text.startswith("{"):
        candidates.append(raw_text)

    candidates.extend(match.group(0) for match in re.finditer(r"\{.*?\}", raw_text, re.DOTALL))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue

        if not isinstance(parsed, dict):
            continue

        tool_name = parsed.get("name")
        if tool_name not in TOOL_NAMES:
            continue

        tool_args = parsed.get("parameters", parsed.get("args", {})) or {}
        tool_args = sanitize_tool_args(tool_name, tool_args)

        return {
            "name": tool_name,
            "args": tool_args,
            "id": f"fixed_{tool_name}",
        }

    return None


def tool_calling_llm(state: State):
    user_text = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_text = msg.content
            break

    if is_simple_question(user_text):
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    if not should_allow_tools(user_text):
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    response = llm_with_tools.invoke(state["messages"])

    if isinstance(response.content, str):
        recovered_tool_call = extract_json_tool_call(response.content)
        if recovered_tool_call is not None:
            fixed_response = AIMessage(content="", tool_calls=[recovered_tool_call])
            return {"messages": [fixed_response]}

    return {"messages": [response]}


def tools_condition_node(state: State):
    """Check whether a tool call can skip confirmation because it was already approved."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)

    if not tool_calls:
        return {}

    user_text = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            user_text = msg.content
            break

    for tc in tool_calls:
        normalized_args = normalize_tool_args(tc["name"], tc.get("args", {}), user_text)
        confirm_id = get_tool_call_id({"name": tc["name"], "args": normalized_args})
        record = confirmed_tool_calls.get(confirm_id)

        if tc["name"] != "delete_file" and record and record["user_confirmation"] == "confirm":
            pending_action = []
            for tc2 in tool_calls:
                normalized_args_2 = normalize_tool_args(tc2["name"], tc2.get("args", {}), user_text)
                pending_action.append({
                    "confirm_id": get_tool_call_id({"name": tc2["name"], "args": normalized_args_2}),
                    "tool_call_id": tc2.get("id", get_tool_call_id(tc2)),
                    "tool_name": tc2["name"],
                    "tool_args": normalized_args_2,
                    "confirmed": "true",
                })
            return {"pending_action": pending_action}

    return {}


def user_confirmation(state: State):
    """Ask the user whether to run the requested tool."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)

    if not tool_calls:
        return {}

    user_text = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            user_text = msg.content
            break

    queue = []
    for tc in tool_calls:
        normalized_args = normalize_tool_args(tc["name"], tc.get("args", {}), user_text)
        queue.append({
            "confirm_id": get_tool_call_id({"name": tc["name"], "args": normalized_args}),
            "tool_call_id": tc.get("id", get_tool_call_id(tc)),
            "tool_name": tc["name"],
            "tool_args": normalized_args,
            "confirmed": "false",
        })

    first_call = queue[0]
    return {
        "messages": [
            AIMessage(content=f"Run '{first_call['tool_name']}' with {first_call['tool_args']}? (yes/no)")
        ],
        "pending_action": queue,
    }


async def execute_tool(state: State):
    """Execute the confirmed tool call."""
    queue = state.get("pending_action", [])
    if not queue:
        return {}

    tool_confirmation = confirmed_tool_calls.get(queue[0]["confirm_id"])
    user_text = state["messages"][-1].content
    if user_text == "" and tool_confirmation is not None:
        user_text = tool_confirmation["user_confirmation"]

    decision = confirmation_check(user_text)
    add_tool_confirmation_to_dict(queue[0]["confirm_id"], queue[0]["tool_args"], decision)

    if decision == "deny":
        return {
            "messages": [AIMessage(content="Canceled. No further tools executed.")],
            "pending_action": [],
        }

    if decision == "invalid":
        return {
            "messages": [AIMessage(content="Reply yes to confirm or no to cancel.")],
            "pending_action": queue,
        }

    action = queue.pop(0)
    tool_calling_msg = AIMessage(
        content="Executing confirmed tool call.",
        tool_calls=[{
            "name": action["tool_name"],
            "args": action["tool_args"],
            "id": action["tool_call_id"],
        }],
    )
    return {"messages": [tool_calling_msg], "pending_action": queue}


def confirm_next(state: State):
    """If more confirmed tools are queued, ask about the next one."""
    queue = state.get("pending_action", [])
    if not queue:
        return {}

    next_action = queue[0]
    return {
        "messages": [
            AIMessage(content=f"Run next tool '{next_action['tool_name']}' with {next_action['tool_args']}? (yes/no)")
        ],
        "pending_action": queue,
    }


async def answer_from_file_content_async(state: State):
    """Async wrapper for answering from retrieved file content."""
    user_text = get_last_user_message(state["messages"])
    file_content = get_last_tool_message_content(state["messages"])

    if not file_content:
        return {}

    cleaned_content = file_content
    prefix_match = " is:\n\n"
    if prefix_match in file_content:
        cleaned_content = file_content.split(prefix_match, 1)[1]

    answer = await answer_question_from_file(llm, user_text, cleaned_content)
    return {"messages": [AIMessage(content=answer)]}


# ── Routing ────────────────────────────────────────────────────────────────────

def route_to_tool_or_llm(state: State) -> str:
    """Go straight to execution if a tool is already pending, otherwise ask the LLM."""
    return "execute_tool" if state.get("pending_action") else "tool_calling_llm"


def route_confirmation_check(state: State) -> str:
    """If the LLM proposed a tool call, enter confirmation flow."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "confirmation_required" if tool_calls else END


def route_to_confirmation_or_tool(state: State) -> str:
    """Choose confirmation or execution based on pending action status."""
    pending_action = state.get("pending_action", [])
    action = pending_action[0] if pending_action else None
    confirmed = action.get("confirmed") if action else None
    return "execute_tool" if confirmed == "true" else "user_confirmation"


def route_after_execute(state: State) -> str:
    """If a tool call message was produced, send it to the ToolNode."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "tools" if tool_calls else END


def route_after_execution(state: State) -> str:
    """After tools run, continue queued tools or answer questions from retrieved file content."""
    if state.get("pending_action"):
        return "confirm_next"

    user_text = get_last_user_message(state["messages"])
    last_tool_output = get_last_tool_message_content(state["messages"])

    if should_answer_from_file(user_text) and last_tool_output:
        return "answer_from_file_content"

    return END


# ── Graph construction ─────────────────────────────────────────────────────────

graph_builder = StateGraph(State)
graph_builder.add_node("tool_calling_llm", tool_calling_llm)
graph_builder.add_node("confirmation_required", tools_condition_node)
graph_builder.add_node("user_confirmation", user_confirmation)
graph_builder.add_node("execute_tool", execute_tool)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("confirm_next", confirm_next)
graph_builder.add_node("answer_from_file_content", answer_from_file_content_async)

graph_builder.add_conditional_edges(START, route_to_tool_or_llm, {
    "execute_tool": "execute_tool",
    "tool_calling_llm": "tool_calling_llm",
})
graph_builder.add_conditional_edges("tool_calling_llm", route_confirmation_check, {
    "confirmation_required": "confirmation_required",
    END: END,
})
graph_builder.add_conditional_edges("confirmation_required", route_to_confirmation_or_tool, {
    "execute_tool": "execute_tool",
    "user_confirmation": "user_confirmation",
})
graph_builder.add_edge("user_confirmation", END)
graph_builder.add_conditional_edges("execute_tool", route_after_execute, {
    "tools": "tools",
    END: END,
})
graph_builder.add_conditional_edges("tools", route_after_execution, {
    "confirm_next": "confirm_next",
    "answer_from_file_content": "answer_from_file_content",
    END: END,
})
graph_builder.add_edge("confirm_next", END)
graph_builder.add_edge("answer_from_file_content", END)

graph = graph_builder.compile()


# ── Chat ───────────────────────────────────────────────────────────────────────

SYSTEM_MESSAGE = SystemMessage(content=(
    "You are a helpful assistant that can use tools when needed. "
    "If the user greets you or makes small talk, respond naturally and conversationally. "
    "Do not mention tools, function calls, or your reasoning unless the user explicitly asks. "
    "Only use tools for file or operating system actions such as listing files, reading files, creating files, deleting files, or getting OS information. "
    "Never invent filenames, file contents, or directory contents. "
    "When listing files, only show the exact files returned by the tool. "
    "When reading files, only use the exact content returned by the tool. "
    "When the user asks about a specific file, retrieve that file before answering. "
    "When calling get_file_content or delete_file, always include file_name. "
    "When calling create_file, always include file_name and content. "
    "Return tool calls using the tool system rather than raw JSON."
))


async def chat(thread_id: str, user_text: str) -> dict:
    """Main chat entrypoint for both slash-command flow and normal chat/tool flow."""
    global CURRENT_THREAD_ID
    CURRENT_THREAD_ID = thread_id

    session = _sessions.get(thread_id)
    if session is None:
        session = {
            "messages": [SYSTEM_MESSAGE],
            "pending_action": [],
            "pending_save": None,
            "pending_resolution": None,
        }
        _sessions[thread_id] = session

    if session.get("pending_save") is not None:
        file_name = user_text.strip()

        if not file_name.lower().endswith((".txt", ".docx", ".pdf")):
            return {
                "reply": "Please provide a valid file name ending in .txt, .docx, or .pdf",
                "pendingAction": False,
            }

        content = session["pending_save"]
        session["pending_save"] = None

        reply = await create_file_response(MCP_client, file_name, content)
        last_output_by_thread[thread_id] = reply
        return {"reply": reply, "pendingAction": False}

    slash_result = await handle_slash_command(
        _sessions,
        thread_id,
        user_text,
        MCP_client,
        llm,
        file_content_cache,
        summary_cache,
        last_output_by_thread,
    )
    if slash_result is not None:
        return slash_result

    resolution_result = await continue_pending_resolution(
        _sessions,
        thread_id,
        user_text,
        MCP_client,
        llm,
        file_content_cache,
        summary_cache,
        last_output_by_thread,
    )
    if resolution_result is not None:
        return resolution_result

    session["messages"].append(HumanMessage(content=user_text))

    result = await graph.ainvoke(
        {"messages": session["messages"], "pending_action": session["pending_action"]}
    )

    session["messages"] = result["messages"]
    session["pending_action"] = result.get("pending_action", [])

    last = result["messages"][-1]
    content = getattr(last, "content", "")

    if isinstance(content, str):
        reply = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            else:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(str(text))
                else:
                    parts.append(str(item))
        reply = "\n".join(parts).strip()
    else:
        reply = str(content)

    if reply and not reply.startswith("Run ") and "Reply yes to confirm" not in reply:
        last_output_by_thread[thread_id] = reply

    return {
        "reply": reply,
        "pendingAction": len(session["pending_action"]) > 0,
    }

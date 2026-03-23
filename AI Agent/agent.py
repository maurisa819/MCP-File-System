import os
import asyncio
from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from fastmcp import Client
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ── Configuration (env-configurable) ───────────────────────────────────────────

MCP_client = os.environ.get("MCP_URL", "http://127.0.0.1:8080/mcp")
OLLAMA_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_model = os.environ.get("OLLAMA_MODEL", "llama3.1")


# ── State definition ───────────────────────────────────────────────────────────

class State(TypedDict):
    messages: Annotated[list, add_messages]
    pending_action: list[Dict[str, Any]]


memory = MemorySaver()

llm = ChatOllama(
    model=OLLAMA_model,
    base_url=OLLAMA_url,
    temperature=0,
)


# ── MCP client helper ──────────────────────────────────────────────────────────

async def mcp_tools(tool_name: str, args: dict | None = None):
    """Calls a tool on the MCP server."""
    args = args or {}
    async with Client(MCP_client) as client:
        return await client.call_tool(tool_name, args)


# ── Tool definitions ───────────────────────────────────────────────────────────

@tool
async def get_os_info() -> dict:
    """Retrieves information about the operating system."""
    return await mcp_tools("get_os_info", {})

@tool
async def list_files() -> list:
    """Lists files in a specified directory."""
    return await mcp_tools("list_files", {})

@tool
async def create_file(file_name: str, content: str = "") -> str:
    """Creates a file with the specified content."""
    return await mcp_tools("create_file", {"file_name": file_name, "content": content})

@tool
async def delete_file(file_name: str) -> str:
    """Deletes a specified file."""
    return await mcp_tools("delete_file", {"file_name": file_name})

@tool
async def get_file_content(file_name: str) -> str:
    """Reads and returns the contents of a file."""
    return await mcp_tools("get_file_content", {"file_name": file_name})


TOOLS = [get_os_info, list_files, create_file, delete_file, get_file_content]
tool_node = ToolNode(TOOLS)
llm_with_tools = llm.bind_tools(TOOLS)


# ── Helpers ─────────────────────────────────────────────────────────────────────

Confirmation_words = ["yes", "y", "confirm", "ok", "okay"]
Denial_words = ["no", "n", "deny", "cancel", "stop"]


def confirmation_check(user_input: str) -> str:
    user_input = user_input.strip().lower()
    if user_input in Confirmation_words:
        return "confirm"
    if user_input in Denial_words:
        return "deny"
    return "invalid"


def get_tool_call_id(tool_call: dict) -> str:
    """Generates a stable id for the tool call.

    For file-related tools, we key the confirmation by *folder* instead of the
    full file path so that permission is asked only the first time a folder is
    accessed.
    """
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
    if confirmed_tool_calls.get(id):
        return
    confirmed_tool_calls[id] = {
        "tool_call": {"id": id, "args": args},
        "user_confirmation": user_confirmation,
    }


# ── Graph nodes ─────────────────────────────────────────────────────────────────

def tool_calling_llm(state: State):
    """LLM reads the user message and decides which tool to call."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": state["messages"] + [response]}


def tools_condition_node(state: State):
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)

    if not tool_calls:
        return state

    for tc in tool_calls:
        tool_call_id = get_tool_call_id(tc)
        record = confirmed_tool_calls.get(tool_call_id)
        if record and record["user_confirmation"] == "confirm":
            pending_action = []
            for tc2 in tool_calls:
                pending_action.append({
                    "id": get_tool_call_id(tc2),
                    "tool_name": tc2["name"],
                    "tool_args": tc2.get("args", {}),
                    "confirmed": "true",
                })
            return {"pending_action": pending_action}

    return {"messages": state["messages"]}


def user_confirmation(state: State):
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)

    if not tool_calls:
        return state

    queue = []
    for tc in tool_calls:
        queue.append({
            "id": get_tool_call_id(tc),
            "tool_name": tc["name"],
            "tool_args": tc.get("args", {}),
            "confirmed": "false",
        })

    first_call = queue[0]

    return {
        "messages": state["messages"] + [
            AIMessage(content=f"Run '{first_call['tool_name']}' with {first_call['tool_args']}? (yes/no)")
        ],
        "pending_action": queue,
    }


async def execute_tool(state: State):
    queue = state.get("pending_action", [])
    if not queue:
        return state

    tool_confirmation = confirmed_tool_calls.get(queue[0]["id"])
    user_text = state["messages"][-1].content
    if user_text == "" and tool_confirmation is not None:
        user_text = tool_confirmation["user_confirmation"]

    decision = confirmation_check(user_text)
    add_tool_confirmation_to_dict(queue[0]["id"], queue[0]["tool_args"], decision)

    if decision == "deny":
        return {
            "messages": state["messages"] + [AIMessage(content="Canceled. No further tools executed.")],
            "pending_action": [],
        }

    if decision == "invalid":
        return {
            "messages": state["messages"] + [AIMessage(content="Reply yes to confirm or no to cancel.")],
            "pending_action": queue,
        }

    # confirmed
    action = queue.pop(0)
    tool_calling_msg = AIMessage(
        content="Executing confirmed tool call.",
        tool_calls=[{"name": action["tool_name"], "args": action["tool_args"], "id": "confirmed_call_1"}],
    )
    return {"messages": state["messages"] + [tool_calling_msg], "pending_action": queue}


def confirm_next(state: State):
    queue = state.get("pending_action", [])
    if not queue:
        return state

    next_action = queue[0]
    return {
        "messages": state["messages"] + [
            AIMessage(content=f"Run next tool '{next_action['tool_name']}' with {next_action['tool_args']}? (yes/no)")
        ],
        "pending_action": queue,
    }


# ── Routing ─────────────────────────────────────────────────────────────────────

def route_to_tool_or_llm(state: State) -> str:
    return "execute_tool" if state.get("pending_action") else "tool_calling_llm"


def route_confirmation_check(state: State) -> str:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "confirmation_required" if tool_calls else END


def route_to_confirmation_or_tool(state: State) -> str:
    pending_action = state.get("pending_action", [])
    action = pending_action[0] if pending_action else None
    confirmed = action.get("confirmed") if action else None
    return "execute_tool" if confirmed == "true" else "user_confirmation"


def route_after_execute(state: State) -> str:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "tools" if tool_calls else END


def route_after_execution(state: State) -> str:
    return "confirm_next" if state.get("pending_action") else "tool_calling_llm"


# ── Graph construction ──────────────────────────────────────────────────────────

graph_builder = StateGraph(State)
graph_builder.add_node("tool_calling_llm", tool_calling_llm)
graph_builder.add_node("confirmation_required", tools_condition_node)
graph_builder.add_node("user_confirmation", user_confirmation)
graph_builder.add_node("execute_tool", execute_tool)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("confirm_next", confirm_next)

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
    "tool_calling_llm": "tool_calling_llm",
})
graph_builder.add_edge("confirm_next", END)

graph = graph_builder.compile(checkpointer=memory)


# ── Session management & chat function ──────────────────────────────────────────

SYSTEM_MESSAGE = SystemMessage(content=(
    "You are an assistant that can use tools. "
    "Only call tools when the user explicitly asks for file or OS actions "
    "(list/read/create/delete/get os info). "
    "If the user says hello or small talk, respond normally and do NOT call tools."
))

_sessions: dict[str, dict] = {}


async def chat(thread_id: str, user_text: str) -> dict:
    """Send a message to the agent and get a response.

    Returns:
        dict with "reply" (str) and "pendingAction" (bool)
    """
    session = _sessions.get(thread_id)
    if session is None:
        session = {"messages": [SYSTEM_MESSAGE], "pending_action": []}
        _sessions[thread_id] = session

    session["messages"].append(HumanMessage(content=user_text))

    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": session["messages"], "pending_action": session["pending_action"]},
        config=config,
    )

    session["messages"] = result["messages"]
    session["pending_action"] = result.get("pending_action", [])

    last = result["messages"][-1]
    reply = getattr(last, "content", str(last))
    if not isinstance(reply, str):
        reply = str(reply)

    return {
        "reply": reply,
        "pendingAction": len(session["pending_action"]) > 0,
    }

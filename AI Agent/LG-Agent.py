from ast import main
import asyncio


from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from fastmcp import Client
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


MCP_client = "http://127.0.0.1:8080/mcp"
OLLAMA_url = "http://localhost:11434" #This will be the base URL for the Ollama server, e.g. "http://
OLLAMA_model= "llama3.1"  #This will be the name of the model running in Ollama


#Defining the structure of the agent 
class State(TypedDict):
    # conversation history
    messages: Annotated[list, add_messages]

    pending_action: list[Dict[str, Any]] #This will hold the pending action that the agent needs to confirm with the user


memory = MemorySaver() #This saves the state of the conversation, please note if the app is closed the memory will be lost, we can use sqlite to save


llm = ChatOllama(
    model=OLLAMA_model,
    base_url=OLLAMA_url,
    temperature = 0
)


async def mcp_tools(tool_name: str, args: dict | None = None):
    """Calls a tool on the MCP server."""
    args = args or {}
    async with Client(MCP_client) as client:
        return await client.call_tool(tool_name, args)


#Calls MCP Server tools
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
tool_node = ToolNode(TOOLS) #This node will be responsible for calling the tools based on the LLM's decision
llm_with_tools = llm.bind_tools(TOOLS) #This creates a version of the LLM that can call the tools when needed

#User helper
Confirmation_words = ["yes", "y", "confirm",  "ok", "okay"]
Denial_words = ["no", "n", "deny", "cancel", "stop"]

#Converts the words to lowercase if they were not already
def confirmation_check(user_input: str) -> str:
    """
    Returns:
        "confirm" if user confirmed
        "deny" if user denied
        "invalid" otherwise
    """
    user_input = user_input.strip().lower()

    if user_input in Confirmation_words:
        return "confirm"

    if user_input in Denial_words:
        return "deny"

    return "invalid"

#Nodes in Graph
def tool_calling_llm(state:State)-> str:
    """ LLM reads the message from the user and decides which tool to call, 
    It does not execute the tool at this stage,"""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages":state["messages"]+[response]}

def user_confirmation(state:State) -> str:
    """The agent asks the user for confirmation before executing the tool, 
    and waits for the user's response."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)

    #No tool calls -> No confirmation needed
    if not tool_calls:
        return state
    
    #For one or multiple tool calls
    queue = []
    for tc in tool_calls:
        queue.append({
        "tool_name": tc["name"],
        "tool_args": tc.get("args", {}),
        "confirmation_message": f"The agent wants to execute the tool '{tc['name']}' with arguments {tc.get('args', {})}. Do you confirm? (yes/no)"
        })
    
    first_call = queue[0]

    return {
        "messages": state["messages"] +[
            AIMessage(content=f"Run '{first_call['tool_name']}'? (yes/no)")
        ],
        "pending_action": queue
    }

async def execute_tool(state:State) -> str:
    """If the user confirms, the agent executes the tool and returns the result to the user."""
    queue = state.get("pending_action", [])
    if not queue:
        return state

    user_text = state["messages"][-1].content
    decision = confirmation_check(user_text)

    if decision == "deny":
        return {"messages": state["messages"] + [AIMessage(content="Canceled. No further tools executed.")], "pending_action": []}

    if decision == "invalid":
        return {"messages": state["messages"] + [AIMessage(content="Reply yes to confirm or no to cancel.")], "pending_action": queue}

    # confirmed
    action = queue.pop(0)
    tool_name = action["tool_name"]
    tool_args = action["tool_args"]

    tool_calling_msg = AIMessage(
        content="Executing confirmed tool call.",
        tool_calls=[{"name": tool_name, "args": tool_args, "id": "confirmed_call_1"}],
    )

    # If more calls remain, they will be processed in the next iteration after user confirmation
    return {"messages": state["messages"] +[tool_calling_msg], "pending_action": queue}

def confirm_next(state: State) -> str:
    """Checks the user's response to the confirmation message and routes accordingly."""
    queue = state.get("pending_action", [])
    if not queue:
        return state
    
    next_action = queue[0] #Peek at the next action in the queue

    return {
        "messages": state["messages"] +[AIMessage(content=f"Run next tool '{next_action['tool_name']}' with {next_action['tool_args']}? (yes/no)")],
        "pending_action": queue
}

#Langgraph instructions for the agent
def route_start(state: State) -> str:
    """If tools are waiting for confirmation route to execute_tool, otherwise route to tool_calling_llm."""
    return "execute_tool" if state.get("pending_action") else "tool_calling_llm"

def route_after_tool_call(state: State) -> str:
    """After the LLM calls a tool, route to user_confirmation to ask the user for confirmation before executing the tool."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "user_confirmation" if tool_calls else END

def route_after_execute_tool(state: State) -> str:
    """After asking the user for confirmation, route to execute_tool to either execute the tool or cancel based on user's response."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "tools" if tool_calls else END

def route_after_execution(state: State) -> str:
    """After executing the tool, route back to the LLM to read the user's next message , if there are more tools
    ask a confirmation for the next one and decide on the next tool call."""
    return "confirm_next" if state.get("pending_action") else "tool_calling_llm"


    


#Graph construction
graph = StateGraph(State)
graph.add_node("tool_calling_llm", tool_calling_llm)
graph.add_node("user_confirmation", user_confirmation)
graph.add_node("execute_tool", execute_tool)
graph.add_node("tools", tool_node)
graph.add_node("confirm_next", confirm_next)

#The LLM calls the tools based on the user's message, 
#A tool may not be called in every iteration, making these edges conditional based on whether the LLM decided to call a tool or not
graph.add_conditional_edges(START, route_start, {"execute_tool": "execute_tool", "tool_calling_llm": "tool_calling_llm"})
graph.add_conditional_edges("tool_calling_llm", route_after_tool_call, {"user_confirmation": "user_confirmation", END: END})

#After the LLM calls a tool, if there is a tool call, ask the user for confirmation, otherwise go back to waiting for the user's message
graph.add_edge("user_confirmation", END)

#After asking the user for confirmation, if there is a tool call, execute the tool, otherwise go back to waiting for the user's message
graph.add_conditional_edges("execute_tool", route_after_execute_tool, {"tools": "tools", END: END})
graph.add_conditional_edges("tools", route_after_execution,{"confirm_next": "confirm_next", "tool_calling_llm": "tool_calling_llm"})

#After asking for confirmation wait for the user's response
graph.add_edge("confirm_next", END)

#After tool execution LLM can decide to call another tool or respond naturally to the user without calling a tool
graph.add_edge("tool_calling_llm", END)

#Compile the graph with all nodes and edges to create the agent, and use the MemorySaver to save the state of the conversation
graph = graph.compile(checkpointer=memory)

async def main():
    print("LG-Agent running. Type 'quit' to exit.")
    config = {"configurable": {"thread_id": "1"}}

    state = {
        "messages": [
            SystemMessage(content=(
                "You are an assistant that can use tools. "
                "Only call tools when the user explicitly asks for file or OS actions "
                "(list/read/create/delete/get os info). "
                "If the user says hello or small talk, respond normally and do NOT call tools."
            ))
        ],
        "pending_action": []
    }

    while True:
        user_text = input("User: ").strip()
        if user_text.lower() in {"quit", "exit"}:
            print("Bye")
            break

        # Add the new human message to the running conversation
        state["messages"].append(HumanMessage(content=user_text))

        # send full state (system + history), not just the latest message
        result = await graph.ainvoke(
            {"messages": state["messages"], "pending_action": state["pending_action"]},
            config=config,
        )

        last = result["messages"][-1]
        print("Assistant:", getattr(last, "content", last))
        print()

        # Update the state with the new messages and pending actions for the next iteration
        state["messages"] = result["messages"]
        state["pending_action"] = result.get("pending_action", [])


if __name__ == "__main__":
    asyncio.run(main())
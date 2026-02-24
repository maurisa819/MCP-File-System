import asyncio
import json
from typing import Annotated
from typing_extensions import TypedDict

from fastmcp import Client

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama


MCP_client = "http://127.0.0.1:8080/mcp"
OLLAMA_url = "" #This will be the base URL for the Ollama server, e.g. "http://
OLLAMA_model= ""  #This will be the name of the model running in Ollama


#Defining the structure of the agent 
class State(TypedDict):
    # conversation history
    messages: Annotated[list, add_messages]

    # last tool output 
    last_tool_result: str | None

    # last tool name
    last_tool: str | None


memory = MemorySaver() #This saves the state of the conversation


llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL
)


async def mcp_tools(tool_name: str, args: dict | None = None):
    """Calls a tool on the MCP server."""
    args = args or {}
    client = Client(MCP_client)
    async with client:
        return await client.call_tool(tool_name, args)


---
name: mcp-file-agent
description: Guides development and behavior of the MCP file-system LG-Agent. Use when editing the agent, adding tools, or improving how the model interprets user file/OS requests and chooses tools.
---

# MCP File-System Agent

## Project layout

- **AI Agent/LG-Agent.py** – LangGraph agent: tool-calling LLM, user confirmation flow, MCP client.
- **MCP-server/src/server.py** – FastMCP server exposing file/OS tools (get_os_info, list_files, create_file, delete_file, get_file_content).
- **AI Agent/agent_skills.md** – In-agent instructions loaded into the system prompt for accurate demand→tool mapping.

## Agent behavior

- Tools are called only when the user explicitly requests file or OS actions.
- Before executing any tool, the agent asks for confirmation (yes/no). Permission is remembered per folder so the same folder is not re-prompted.
- Tool call IDs for file tools are keyed by folder (see `get_tool_call_id` in LG-Agent.py).

## When editing the agent

1. **System prompt**: Keep core rules in `main()` and detailed demand→tool rules in `agent_skills.md`; load skills in `main()` and inject into the first `SystemMessage`.
2. **New MCP tools**: Add `@tool` in LG-Agent.py, add to `TOOLS`, and document in agent_skills.md (when to call, required args).
3. **Confirmation**: File tools use folder-based IDs; other tools use hash of (name, args). Do not change this without updating both `get_tool_call_id` and the confirmation flow.

## Tool contracts (MCP server)

| Tool | Typical user demand | Args |
|------|----------------------|-----|
| get_os_info | "What OS?", "system info" | (none) |
| list_files | "list files", "what's in this folder" | directory (optional) |
| get_file_content | "read X", "show content of X" | file_name, directory (optional) |
| create_file | "create file X", "write X with content Y" | file_name, content (optional) |
| delete_file | "delete X", "remove X" | file_name, directory (optional) |

When adding or changing tools, update both server.py and LG-Agent.py, and keep agent_skills.md in sync so the model stays accurate.

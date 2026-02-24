# LangGraph AI Agent (MCP + Ollama)

This agent is a LangGraph-based chatbot that can call tools from our FastMCP server
(e.g., list files, read file content, create/delete files).  
The LLM runs locally via Ollama (Docker).

---

## Prerequisites

- Python 3.13 or higher
- MCP Server running on HTTP (default: http://127.0.0.1:8080/mcp)
- Ollama running (default: http://localhost:11434)

---

## Setup (pip / venv)

### 1. Navigate to the agent folder

```bash
cd /path/to/AI Agent
```

### 2. Create and activate a virtual environment (if not already present)

#### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Agent

```bash
python LG-Agent.py
```

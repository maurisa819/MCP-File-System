# LangGraph AI Agent (MCP + Ollama via Docker Compose)

This project runs:

- MCP Server (FastMCP)
- Ollama (LLM backend)
- LangGraph Agent (Python)

Both the MCP server and Ollama run inside Docker using `docker-compose`.

---

# Architecture

Terminal 1 → Docker Compose (MCP + Ollama)  
Terminal 2 → LangGraph Agent (Python)

Everything runs locally.

---

# Prerequisites

Install:

- Python 3.10+ (3.13 recommended)
- Docker Desktop (must be running)


---

# Step 1 — Start MCP + Ollama (Docker Compose)

Open **Terminal 1** in the root project folder (where `docker-compose.yml` is located).

## Build containers (first time only)

```bash
docker compose build
```
## Build containers (first time only) and Start Docker
```bash
docker compose up -d --build
```
## Load the Ollama model
```bash
docker exec -it ollama ollama pull llama3.1
```
You can verify its pulled by typing:
```bash
docker exec -it ollama ollama list
```
and it should show:
llama3.1


# Step 2 — Run AI Agent
Open **Terminal 2** in the root project folder (where `LG-Agent.py` is located)

# Create and Activate a virtual environment
macOS / Linux 
```bash
python3 -m venv .venv
source .venv/bin/activate
```
Windows 
```bash
python -m venv .venv
.venv\Scripts\activate
```

## Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Run the Agent
```bash
python LG-Agent.py
```

#Example Usage
User: hello
Assistant: Hi there! How can I help?

User: list files
Assistant: Run 'list_files'? (yes/no)

User: yes
Assistant: You have a file named "test.txt" in your home directory.


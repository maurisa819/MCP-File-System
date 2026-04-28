# MCP-File-System

Model Context Protocol (MCP) integration for controlled file system access with four main pieces

1. MCP Server (Docker) — file system tools
2. Ollama — local LLM
3. Agent Server (Python) — logic + tool orchestration
4. React UI — chat interface

---

# Project Structure

```
project-root/
│
├── MCP-server/
├── AI Agent/
│   ├── api.py
│   ├── agent.py
│   ├── agent_helpers.py
│   ├── requirements.txt
│   └── venv/
│
├── UI/
│   ├── package.json
│   └── src/
│
├── run-all.js
└── package.json
```

---

# 1. Prerequisites

Install the following:

## Docker

```bash
docker --version
docker compose version
```

## Ollama

```bash
ollama --version
```

## Node.js + npm

```bash
node -v
npm -v
```

## Python

```bash
python3 --version
```

---

# 2. Install Ollama Model

Start Ollama:

## Linux (recommended)

```bash
sudo systemctl start ollama
```

## macOS/Windows/manual

```bash
ollama serve
```

Then pull model:

```bash
ollama pull llama3.1
```

---

# 3. Setup Agent (Python)

```bash
cd "AI Agent"
python3 -m venv venv
```

### macOS/Linux

```bash
source venv/bin/activate
```

### Windows

```powershell
venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 4. Setup UI

```bash
cd UI
npm install
```

---

# 5. Root package.json

Create this in project root (This should already be created if not follow steps below):

```json
{
  "name": "file-assistant-runner",
  "private": true,
  "scripts": {
    "run-all": "node run-all.js"
  }
}
```

---

# 6. Run Everything (One Command)

```bash
npm run run-all
```

This starts (automatically):

- MCP server (Docker, detached)
- Ollama (auto-detected or started if needed)
- Agent (local)
- UI (local)

Press **Ctrl + C** to stop ALL services (including MCP).

---

# 7. Manual Run (Alternative)

## Terminal 1 — MCP

```bash
cd MCP-server
docker compose up mcp-server
```

## Terminal 2 — Ollama

```bash
ollama serve
```

## Terminal 3 — Agent

```bash
cd "AI Agent"
source venv/bin/activate
uvicorn api:app --port 3001 --reload
```

## Terminal 4 — UI

```bash
cd UI
npm run ui
```

---

# 8. Ports

| Service | Port  |
| ------- | ----- |
| MCP     | 8080  |
| Ollama  | 11434 |
| Agent   | 3001  |
| UI      | 5174  |

---

# 9. Example Commands

```
Hi
list my files
read sample1.docx
```

### Slash Commands

```
/summarize file.pdf
/summarize file.pdf -> summary.docx #this summarizes the file and puts it into a new file
/compare file1.docx file2.pdf
/compare file1.docx file2.pdf -> result.docx
/save output.docx
```

---

# 10. Common Issues

## Port already in use

```bash
pkill -f uvicorn
pkill -f node
```

## Windows fix

```powershell
netstat -ano | findstr :3001
taskkill /PID <PID> /F
```

---

## Ollama not running

```bash
# Linux
sudo systemctl start ollama

# macOS / Windows
ollama serve
```

---

## Import errors (agent)

Ensure inside `AI Agent/`:

```
agent.py
agent_helpers.py
api.py
```

---

# 11. Stop Everything

If using runner:

```
Ctrl + C

(This will stop Agent, UI, Ollama (if started), and MCP automatically)
```

If manual:

```
Ctrl + C (each terminal)
docker compose down
```

---

# 12. Development Tips

- Always use:

```bash
uvicorn api:app --reload
```

- Keep agent files together
- MCP stays in Docker
- Agent + UI run locally

---

# 13. First-Time Setup Summary

1. Install Docker
2. Install Ollama
3. Install Node
4. Install Python
5. Pull model
6. Create venv + install requirements
7. Run `npm install` in UI
8. Run:

```bash
npm run run-all
```

---

# Done

Your system should now be fully running with:

```
UI → Agent → MCP → Filesystem
        ↓
     Ollama
```

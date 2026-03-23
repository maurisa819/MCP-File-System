# AI Chat UI

A React chat interface for the LangGraph AI agent.

## Prerequisites

- [Node.js](https://nodejs.org/) v20+
- The MCP server and Ollama running (see `MCP-server/` for setup)

## Project Structure

```
UI/
├── src/
│   ├── agent.ts        # LangGraph agent module (reusable)
│   ├── server.ts       # Express API server wrapping the agent
│   ├── lg-agent.ts     # Original CLI agent (standalone)
│   └── ui/
│       ├── App.tsx     # React chat component
│       └── main.tsx    # React entry point
├── index.html          # HTML shell for Vite
├── vite.config.ts      # Vite config with API proxy
├── Dockerfile          # Container image for the UI services
├── package.json
├── tsconfig.json       # TS config for server-side code
└── tsconfig.ui.json    # TS config for React code
```

## Running Locally

Make sure the MCP server is running on port 8080 and Ollama on port 11434 before starting.

### Option A: FastAPI backend (Python)

#### 1. Install Python dependencies

```bash
cd "AI Agent"
pip install -r requirements.txt
```

#### 2. Start the FastAPI server

```bash
uvicorn api:app --port 3001
```

This starts the FastAPI server on **http://localhost:3001**. It exposes a `POST /api/chat` endpoint that forwards messages to the LangGraph agent.

#### 3. Start the frontend (Vite dev server)

In a separate terminal:

```bash
cd UI
npm install
npm run ui
```

This starts the Vite dev server on **http://localhost:5173**. API requests to `/api` are automatically proxied to the backend on port 3001.

#### 4. Open the UI

Go to **http://localhost:5173** in your browser.

### Option B: Express backend (Node.js)

#### 1. Install dependencies

```bash
cd UI
npm install
```

#### 2. Start the Express API server

```bash
npm run server
```

This starts the Express server on **http://localhost:3001**.

#### 3. Start the frontend

In a separate terminal:

```bash
npm run ui
```

#### 4. Open the UI

Go to **http://localhost:5173** in your browser.

## Running with Docker Compose

All services (MCP server, Ollama, agent API, and UI) can be started together:

```bash
cd MCP-server
docker compose up --build
```

This starts:

| Service        | Port | Description                          |
|----------------|------|--------------------------------------|
| `mcp-server`   | 8080 | MCP tool server                      |
| `ollama`       | 11434| Ollama LLM server                    |
| `agent-server` | 3001 | FastAPI server wrapping the LangGraph agent |
| `ui`           | 5173 | Vite dev server (React frontend)     |

Open **http://localhost:5173** once the containers are up.

> NOTE: If you want to run the typescript version of the agent you will need to comment out the Python agent in the docker-compse.yaml file and un-comment the typescript version.

## Environment Variables

The agent server reads these env vars (with sensible defaults for local development):

| Variable       | Default                          | Description              |
|----------------|----------------------------------|--------------------------|
| `MCP_URL`      | `http://127.0.0.1:8080/mcp`     | MCP server endpoint      |
| `OLLAMA_URL`   | `http://localhost:11434`         | Ollama server URL        |
| `OLLAMA_MODEL` | `llama3.1`                       | Ollama model name        |
| `VITE_API_URL` | `http://localhost:3001`          | API proxy target (Vite)  |

## Available Scripts

### Python (AI Agent)

| Command | Description |
|---------|-------------|
| `uvicorn api:app --port 3001` | Start the FastAPI server |
| `python LG-Agent.py` | Run the CLI agent |

### Node.js (UI)

| Script          | Command              | Description                          |
|-----------------|----------------------|--------------------------------------|
| `npm run server`| `npx tsx src/server.ts` | Start the Express API server      |
| `npm run ui`    | `vite`               | Start the Vite dev server            |
| `npm run dev`   | `npx ts-node --esm src/lg-agent.ts` | Run the original CLI agent |
| `npm run build` | `tsc`                | Compile TypeScript                   |
| `npm run ui:build` | `vite build`      | Build the React UI for production    |

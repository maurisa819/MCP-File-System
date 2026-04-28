const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const net = require("net");

const ROOT_DIR = __dirname;

const MCP_DIR = path.join(ROOT_DIR, "MCP-server");
const AGENT_DIR = path.join(ROOT_DIR, "AI Agent");
const UI_DIR = path.join(ROOT_DIR, "UI");

const MCP_SERVICE_NAME = "mcp-server";

const MCP_PORT = 8080;
const OLLAMA_PORT = 11434;
const AGENT_PORT = 3001;
const UI_PORT = 5174; // change if needed

const isWindows = process.platform === "win32";
const isLinux = process.platform === "linux";

const children = [];
let startedOllama = false;
let startedMCP = false;
let cleaningUp = false;

function log(msg) {
  console.log(`[run-all] ${msg}`);
}

function commandExists(cmd) {
  try {
    if (isWindows) {
      execSync(`where ${cmd}`, { stdio: "ignore" });
    } else {
      execSync(`command -v ${cmd}`, {
        stdio: "ignore",
        shell: "/bin/bash",
      });
    }
    return true;
  } catch {
    return false;
  }
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(1000);

    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });

    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });

    socket.once("error", () => {
      socket.destroy();
      resolve(false);
    });

    socket.connect(port, "127.0.0.1");
  });
}

async function waitForPort(port, name, retries = 30, delayMs = 1000) {
  for (let i = 0; i < retries; i++) {
    if (await isPortOpen(port)) {
      log(`${name} is up on port ${port}`);
      return;
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  throw new Error(`${name} failed to start on port ${port}`);
}

function spawnProcess(name, cmd, args, cwd) {
  log(`Starting ${name}...`);

  const child = spawn(cmd, args, {
    cwd,
    stdio: "inherit",
    shell: false,
  });

  child.on("exit", (code, signal) => {
    log(`${name} exited (${signal || code})`);
  });

  children.push(child);
  return child;
}

function tryExec(command, options = {}) {
  try {
    execSync(command, options);
    return true;
  } catch {
    return false;
  }
}

async function ensureMCPRunning() {
  if (!commandExists("docker")) {
    throw new Error("Docker not installed");
  }

  if (await isPortOpen(MCP_PORT)) {
    log("MCP server already running");
    return;
  }

  log("Starting MCP server (detached)...");
  execSync(`docker compose up -d ${MCP_SERVICE_NAME}`, {
    cwd: MCP_DIR,
    stdio: "inherit",
  });

  startedMCP = true;
  await waitForPort(MCP_PORT, "MCP server");
}

async function ensureOllamaRunning() {
  if (await isPortOpen(OLLAMA_PORT)) {
    log("Ollama already running");
    return;
  }

  if (!commandExists("ollama")) {
    throw new Error("Ollama not installed");
  }

  if (isLinux && commandExists("systemctl")) {
    log("Trying to start Ollama via systemctl...");

    const ok = tryExec("systemctl start ollama", {
      stdio: "ignore",
      shell: "/bin/bash",
    });

    if (ok) {
      try {
        await waitForPort(OLLAMA_PORT, "Ollama");
        log("Ollama started via systemctl");
        return;
      } catch {
        log("systemctl start ollama did not bring Ollama up, falling back to ollama serve...");
      }
    } else {
      log("systemctl start ollama failed, falling back to ollama serve...");
    }
  }

  spawnProcess("Ollama", "ollama", ["serve"], ROOT_DIR);
  startedOllama = true;
  await waitForPort(OLLAMA_PORT, "Ollama");
}

function getPythonPath() {
  const linuxMacPython = path.join(AGENT_DIR, "venv", "bin", "python");
  const windowsPython = path.join(AGENT_DIR, "venv", "Scripts", "python.exe");

  if (fs.existsSync(linuxMacPython)) return linuxMacPython;
  if (fs.existsSync(windowsPython)) return windowsPython;

  throw new Error("Could not find agent virtual environment Python");
}

function getNpmCommand() {
  return isWindows ? "npm.cmd" : "npm";
}

function stopChildProcesses() {
  for (const child of children) {
    try {
      if (!child || child.exitCode !== null) continue;

      if (isWindows) {
        spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
          stdio: "ignore",
          shell: false,
        });
      } else {
        child.kill("SIGTERM");
      }
    } catch {}
  }
}

function stopStartedOllama() {
  if (!startedOllama) return;

  log("Stopping Ollama started by this script...");

  try {
    if (isWindows) {
      execSync("taskkill /IM ollama.exe /F", { stdio: "ignore" });
    } else {
      execSync("pkill -f 'ollama serve'", {
        stdio: "ignore",
        shell: "/bin/bash",
      });
    }
  } catch {}
}

function stopMCP() {
  if (!startedMCP) return;

  log("Stopping MCP server...");

  try {
    execSync("docker compose down", {
      cwd: MCP_DIR,
      stdio: "inherit",
    });
  } catch {}
}

function cleanupAndExit(exitCode = 0) {
  if (cleaningUp) return;
  cleaningUp = true;

  log("Stopping all started services...");

  stopChildProcesses();
  stopStartedOllama();
  stopMCP();

  process.exit(exitCode);
}

process.on("SIGINT", () => cleanupAndExit(0));
process.on("SIGTERM", () => cleanupAndExit(0));

process.on("uncaughtException", (err) => {
  console.error(err);
  cleanupAndExit(1);
});

process.on("unhandledRejection", (err) => {
  console.error(err);
  cleanupAndExit(1);
});

async function main() {
  await ensureMCPRunning();
  await ensureOllamaRunning();

  if (await isPortOpen(AGENT_PORT)) {
    throw new Error(`Agent port ${AGENT_PORT} is already in use`);
  }

  if (await isPortOpen(UI_PORT)) {
    throw new Error(`UI port ${UI_PORT} is already in use`);
  }

  const python = getPythonPath();

  spawnProcess(
    "Agent",
    python,
    ["-m", "uvicorn", "api:app", "--port", String(AGENT_PORT), "--reload"],
    AGENT_DIR
  );

  await waitForPort(AGENT_PORT, "Agent");

  const npmCmd = getNpmCommand();

  spawnProcess(
    "UI",
    npmCmd,
    ["run", "ui", "--", "--port", String(UI_PORT)],
    UI_DIR
  );

  await waitForPort(UI_PORT, "UI");

  log("");
  log("Everything is running:");
  log(`MCP     → http://localhost:${MCP_PORT}`);
  log(`Ollama  → http://localhost:${OLLAMA_PORT}`);
  log(`Agent   → http://localhost:${AGENT_PORT}`);
  log(`UI      → http://localhost:${UI_PORT}`);
  log("");
  log("Press Ctrl+C to stop EVERYTHING");
}

main().catch((err) => {
  console.error(`[run-all] ${err.message}`);
  cleanupAndExit(1);
});
import { createInterface } from "readline/promises";
import { createHash } from "crypto";

import { Annotation, StateGraph, START, END, messagesStateReducer } from "@langchain/langgraph";
import { ToolNode } from "@langchain/langgraph/prebuilt";
import { MemorySaver } from "@langchain/langgraph";
import { ChatOllama } from "@langchain/ollama";
import { tool } from "@langchain/core/tools";
import { HumanMessage, AIMessage, SystemMessage, BaseMessage } from "@langchain/core/messages";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { z } from "zod";

// ── Configuration ──────────────────────────────────────────────────────────────

const MCP_URL = "http://127.0.0.1:8080/mcp";
const OLLAMA_URL = "http://localhost:11434"; // Base URL for the Ollama server
const OLLAMA_MODEL = "llama3.1"; // Name of the model running in Ollama

// ── State definition ───────────────────────────────────────────────────────────

interface PendingAction {
  id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  confirmed: string;
}

const AgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: messagesStateReducer,
  }),
  pending_action: Annotation<PendingAction[]>({
    reducer: (_prev, next) => next,
    default: () => [],
  }),
});

type AgentStateType = typeof AgentState.State;

// ── Memory / Checkpointer ──────────────────────────────────────────────────────

const memory = new MemorySaver();
// This saves the state of the conversation. If the app is closed the memory will
// be lost — you can swap in a SQLite-backed saver for persistence.

// ── LLM ────────────────────────────────────────────────────────────────────────

const llm = new ChatOllama({
  model: OLLAMA_MODEL,
  baseUrl: OLLAMA_URL,
  temperature: 0,
});

// ── MCP client helper ──────────────────────────────────────────────────────────

async function mcpTools(toolName: string, args: Record<string, unknown> = {}): Promise<unknown> {
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL));
  const client = new Client({ name: "lg-agent-ts", version: "1.0.0" });
  await client.connect(transport);
  try {
    const result = await client.callTool({ name: toolName, arguments: args });
    console.log(`Tool '${toolName}' returned:`, result);
    if (result && typeof result === "object" && "content" in result) {
      if (Array.isArray(result.content)) {
        return result.content.map((item) => (item.text ? item.text : item)).join("\n");
      }
      return result.content;
    }
    return result;
  } finally {
    await client.close();
  }
}

// ── Tool definitions (wrapping MCP server tools) ───────────────────────────────

const getOsInfo = tool(
  async () => {
    return JSON.stringify(await mcpTools("get_os_info", {}));
  },
  {
    name: "get_os_info",
    description: "Retrieves information about the operating system.",
    schema: z.object({}),
  }
);

const listFiles = tool(
  async () => {
    return JSON.stringify(await mcpTools("list_files", {}));
  },
  {
    name: "list_files",
    description: "Lists files in a specified directory.",
    schema: z.object({}),
  }
);

const createFile = tool(
  async ({ file_name, content }) => {
    return JSON.stringify(await mcpTools("create_file", { file_name, content }));
  },
  {
    name: "create_file",
    description: "Creates a file with the specified content.",
    schema: z.object({ file_name: z.string(), content: z.string().default("") }),
  }
);

const deleteFile = tool(
  async ({ file_name }) => {
    return JSON.stringify(await mcpTools("delete_file", { file_name }));
  },
  {
    name: "delete_file",
    description: "Deletes a specified file.",
    schema: z.object({ file_name: z.string() }),
  }
);

const getFileContent = tool(
  async ({ file_name }) => {
    return JSON.stringify(await mcpTools("get_file_content", { file_name }));
  },
  {
    name: "get_file_content",
    description: "Reads and returns the contents of a file.",
    schema: z.object({ file_name: z.string() }),
  }
);

const TOOLS = [getOsInfo, listFiles, createFile, deleteFile, getFileContent];
const toolNode = new ToolNode(TOOLS); // Responsible for calling tools based on LLM decision
const llmWithTools = llm.bindTools(TOOLS); // LLM version that can call tools when needed

// ── User-confirmation helpers ──────────────────────────────────────────────────

const CONFIRMATION_WORDS = ["yes", "y", "confirm", "ok", "okay"];
const DENIAL_WORDS = ["no", "n", "deny", "cancel", "stop"];

function confirmationCheck(userInput: string): "confirm" | "deny" | "invalid" {
  const trimmed = userInput.trim().toLowerCase();
  if (CONFIRMATION_WORDS.includes(trimmed)) return "confirm";
  if (DENIAL_WORDS.includes(trimmed)) return "deny";
  return "invalid";
}

// ── Tool-call ID helper ────────────────────────────────────────────────────────

interface ToolCall {
  name: string;
  args?: Record<string, unknown>;
  id?: string;
}

function getToolCallId(tc: ToolCall): string {
  const argsStr = JSON.stringify(tc.args ?? {}, Object.keys(tc.args ?? {}).sort());
  const hash = createHash("sha256").update(argsStr).digest("hex").slice(0, 12);
  return `${tc.name}_${hash}`;
}

// ── Confirmed tool calls registry ──────────────────────────────────────────────

interface ConfirmationRecord {
  tool_call: { id: string; args: Record<string, unknown> };
  user_confirmation: string;
}

const confirmedToolCalls = new Map<string, ConfirmationRecord>();

function addToolConfirmationToDict(
  id: string,
  args: Record<string, unknown>,
  userConfirmation: string
): void {
  if (confirmedToolCalls.has(id)) return;
  confirmedToolCalls.set(id, {
    tool_call: { id, args },
    user_confirmation: userConfirmation,
  });
}

// ── Graph Nodes ────────────────────────────────────────────────────────────────

/** LLM reads the user message and decides which tool to call (does not execute). */
async function toolCallingLlm(state: AgentStateType) {
  console.log("Assistant: LLM is processing user input...");
  const response = await llmWithTools.invoke(state.messages);
  return { messages: [...state.messages, response] };
}

/** Checks whether the LLM called a tool and whether it's already confirmed. */
function toolsConditionNode(state: AgentStateType) {
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  const toolCalls: ToolCall[] | undefined = (lastMessage as any).tool_calls;

  if (!toolCalls || toolCalls.length === 0) {
    return state;
  }

  for (const tc of toolCalls) {
    const toolCallId = getToolCallId(tc);
    const record = confirmedToolCalls.get(toolCallId);
    if (record && record.user_confirmation === "confirm") {
      const pendingAction: PendingAction[] = toolCalls.map((tc2) => ({
        id: getToolCallId(tc2),
        tool_name: tc2.name,
        tool_args: tc2.args ?? {},
        confirmed: "true",
      }));
      return { pending_action: pendingAction };
    }
  }

  return { messages: state.messages };
}

/** Asks the user for confirmation before executing the tool. */
function userConfirmation(state: AgentStateType) {
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  const toolCalls: ToolCall[] | undefined = (lastMessage as any).tool_calls;

  if (!toolCalls || toolCalls.length === 0) {
    console.log("Assistant: No tool calls detected. No confirmation needed.");
    return state;
  }

  console.log("Assistant: Asking user for confirmation before executing tool...");

  const queue: PendingAction[] = toolCalls.map((tc) => ({
    id: getToolCallId(tc),
    tool_name: tc.name,
    tool_args: tc.args ?? {},
    confirmed: "false",
  }));

  const firstCall = queue[0];

  return {
    messages: [
      ...state.messages,
      new AIMessage(
        `Run '${firstCall.tool_name}' with ${JSON.stringify(firstCall.tool_args)}? (yes/no)`
      ),
    ],
    pending_action: queue,
  };
}

/** If the user confirms, executes the tool; otherwise cancels. */
async function executeTool(state: AgentStateType) {
  const queue = [...(state.pending_action ?? [])];
  if (queue.length === 0) return state;

  const toolConfirmation = confirmedToolCalls.get(queue[0].id);
  let userText = (state.messages[state.messages.length - 1] as any).content as string;
  if (userText === "" && toolConfirmation) {
    userText = toolConfirmation.user_confirmation;
  }

  const decision = confirmationCheck(userText);
  addToolConfirmationToDict(queue[0].id, queue[0].tool_args, decision);

  if (decision === "deny") {
    return {
      messages: [...state.messages, new AIMessage("Canceled. No further tools executed.")],
      pending_action: [],
    };
  }

  if (decision === "invalid") {
    return {
      messages: [...state.messages, new AIMessage("Reply yes to confirm or no to cancel.")],
      pending_action: queue,
    };
  }

  // confirmed
  const action = queue.shift()!;
  const toolCallingMsg = new AIMessage({
    content: "Executing confirmed tool call.",
    tool_calls: [{ name: action.tool_name, args: action.tool_args, id: "confirmed_call_1" }],
  });

  return {
    messages: [...state.messages, toolCallingMsg],
    pending_action: queue,
  };
}

/** After tool execution, asks user to confirm the next queued tool. */
function confirmNext(state: AgentStateType) {
  const queue = state.pending_action ?? [];
  if (queue.length === 0) return state;

  const nextAction = queue[0];
  return {
    messages: [
      ...state.messages,
      new AIMessage(
        `Run next tool '${nextAction.tool_name}' with ${JSON.stringify(nextAction.tool_args)}? (yes/no)`
      ),
    ],
    pending_action: queue,
  };
}

// ── Routing functions ──────────────────────────────────────────────────────────

function routeToToolOrLlmForProcessing(state: AgentStateType): string {
  return state.pending_action && state.pending_action.length > 0
    ? "execute_tool"
    : "tool_calling_llm";
}

function routeConfirmationRequiredCheck(state: AgentStateType): string {
  const lastMessage = state.messages[state.messages.length - 1] as any;
  const toolCalls = lastMessage.tool_calls;
  return toolCalls && toolCalls.length > 0 ? "confirmation_required" : "__end__";
}

function routeToConfirmationOrTool(state: AgentStateType): string {
  const pendingAction = state.pending_action ?? [];
  const action = pendingAction.length > 0 ? pendingAction[0] : null;
  const confirmed = action?.confirmed;
  return confirmed === "true" ? "execute_tool" : "user_confirmation";
}

function routeAfterExecuteTool(state: AgentStateType): string {
  const lastMessage = state.messages[state.messages.length - 1] as any;
  const toolCalls = lastMessage.tool_calls;
  return toolCalls && toolCalls.length > 0 ? "tools" : "__end__";
}

function routeAfterExecution(state: AgentStateType): string {
  return state.pending_action && state.pending_action.length > 0
    ? "confirm_next"
    : "tool_calling_llm";
}

// ── Graph construction ─────────────────────────────────────────────────────────

const graphBuilder = new StateGraph(AgentState)
  .addNode("tool_calling_llm", toolCallingLlm)
  .addNode("confirmation_required", toolsConditionNode)
  .addNode("user_confirmation", userConfirmation)
  .addNode("execute_tool", executeTool)
  .addNode("tools", toolNode)
  .addNode("confirm_next", confirmNext);

// Conditional edges
graphBuilder.addConditionalEdges(START, routeToToolOrLlmForProcessing, {
  execute_tool: "execute_tool",
  tool_calling_llm: "tool_calling_llm",
});
graphBuilder.addConditionalEdges("tool_calling_llm", routeConfirmationRequiredCheck, {
  confirmation_required: "confirmation_required",
  [END]: END,
});
graphBuilder.addConditionalEdges("confirmation_required", routeToConfirmationOrTool, {
  execute_tool: "execute_tool",
  user_confirmation: "user_confirmation",
});

// After the LLM calls a tool, ask user for confirmation, otherwise wait for next message
graphBuilder.addEdge("user_confirmation", END);

// After confirmation, execute tool or cancel
graphBuilder.addConditionalEdges("execute_tool", routeAfterExecuteTool, {
  tools: "tools",
  [END]: END,
});
graphBuilder.addConditionalEdges("tools", routeAfterExecution, {
  confirm_next: "confirm_next",
  tool_calling_llm: "tool_calling_llm",
});

// After asking for confirmation wait for user's response
graphBuilder.addEdge("confirm_next", END);

// After tool execution LLM can decide to call another tool or respond naturally
//graphBuilder.addEdge("tool_calling_llm", END);

// Compile the graph with the MemorySaver checkpointer
const graph = graphBuilder.compile({ checkpointer: memory });

// ── Main loop ──────────────────────────────────────────────────────────────────

async function main() {
  console.log("LG-Agent running. Type 'quit' to exit.");
  const config = { configurable: { thread_id: "1" } };

  let state: { messages: BaseMessage[]; pending_action: PendingAction[] } = {
    messages: [
      new SystemMessage(
        "You are an assistant that can use tools." +
          "Only call tools when the user explicitly asks for file or OS actions " +
          "(list/read/create/delete/get os info). " +
          "If the user says hello or small talk, respond normally and do NOT call tools."
      ),
    ],
    pending_action: [],
  };

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  try {
    while (true) {
      const userText = (await rl.question("User: ")).trim();
      if (["quit", "exit"].includes(userText.toLowerCase())) {
        console.log("Bye");
        break;
      }

      // Add the new human message to the running conversation
      state.messages.push(new HumanMessage(userText));

      // Send full state (system + history), not just the latest message
      const result = await graph.invoke(
        { messages: state.messages, pending_action: state.pending_action },
        config
      );

      const last = result.messages[result.messages.length - 1];
      console.log("Assistant:", (last as any).content ?? last);
      console.log();

      // Update state with new messages and pending actions for the next iteration
      state.messages = result.messages;
      state.pending_action = result.pending_action ?? [];
    }
  } finally {
    rl.close();
  }
}

main().catch(console.error);

import { createHash } from "crypto";

import {
  Annotation,
  StateGraph,
  START,
  END,
  messagesStateReducer,
} from "@langchain/langgraph";
import { ToolNode } from "@langchain/langgraph/prebuilt";
import { MemorySaver } from "@langchain/langgraph";
import { ChatOllama } from "@langchain/ollama";
import { tool } from "@langchain/core/tools";
import {
  HumanMessage,
  AIMessage,
  SystemMessage,
  BaseMessage,
} from "@langchain/core/messages";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { z } from "zod";

// ── Configuration ──────────────────────────────────────────────────────────────

const MCP_URL = process.env.MCP_URL ?? "http://127.0.0.1:8080/mcp";
const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const OLLAMA_MODEL = process.env.OLLAMA_MODEL ?? "llama3.1";

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

// ── LLM ────────────────────────────────────────────────────────────────────────

const llm = new ChatOllama({
  model: OLLAMA_MODEL,
  baseUrl: OLLAMA_URL,
  temperature: 0,
});

// ── MCP client helper ──────────────────────────────────────────────────────────

async function mcpTools(
  toolName: string,
  args: Record<string, unknown> = {}
): Promise<unknown> {
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL));
  const client = new Client({ name: "lg-agent-ts", version: "1.0.0" });
  await client.connect(transport);
  try {
    const result = await client.callTool({ name: toolName, arguments: args });
    console.log(`Tool call result for ${toolName}:`, result);
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

// ── Tool definitions ───────────────────────────────────────────────────────────

const getOsInfo = tool(async () => JSON.stringify(await mcpTools("get_os_info", {})), {
  name: "get_os_info",
  description: "Retrieves information about the operating system.",
  schema: z.object({}),
});

const listFiles = tool(async () => JSON.stringify(await mcpTools("list_files", {})), {
  name: "list_files",
  description: "Lists files in a specified directory.",
  schema: z.object({}),
});

const createFile = tool(
  async ({ file_name, content }) =>
    JSON.stringify(await mcpTools("create_file", { file_name, content })),
  {
    name: "create_file",
    description: "Creates a file with the specified content.",
    schema: z.object({ file_name: z.string(), content: z.string().default("") }),
  }
);

const deleteFile = tool(
  async ({ file_name }) =>
    JSON.stringify(await mcpTools("delete_file", { file_name })),
  {
    name: "delete_file",
    description: "Deletes a specified file.",
    schema: z.object({ file_name: z.string() }),
  }
);

const getFileContent = tool(
  async ({ file_name }) =>
    JSON.stringify(await mcpTools("get_file_content", { file_name })),
  {
    name: "get_file_content",
    description: "Reads and returns the contents of a file.",
    schema: z.object({ file_name: z.string() }),
  }
);

const TOOLS = [getOsInfo, listFiles, createFile, deleteFile, getFileContent];
const toolNode = new ToolNode(TOOLS);
const llmWithTools = llm.bindTools(TOOLS);

// ── Helpers ────────────────────────────────────────────────────────────────────

const CONFIRMATION_WORDS = ["yes", "y", "confirm", "ok", "okay"];
const DENIAL_WORDS = ["no", "n", "deny", "cancel", "stop"];

function confirmationCheck(userInput: string): "confirm" | "deny" | "invalid" {
  const trimmed = userInput.trim().toLowerCase();
  if (CONFIRMATION_WORDS.includes(trimmed)) return "confirm";
  if (DENIAL_WORDS.includes(trimmed)) return "deny";
  return "invalid";
}

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

async function toolCallingLlm(state: AgentStateType) {
  const response = await llmWithTools.invoke(state.messages);
  return { messages: [...state.messages, response] };
}

function toolsConditionNode(state: AgentStateType) {
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  const toolCalls: ToolCall[] | undefined = (lastMessage as any).tool_calls;

  if (!toolCalls || toolCalls.length === 0) return state;

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

function userConfirmation(state: AgentStateType) {
  const lastMessage = state.messages[state.messages.length - 1] as AIMessage;
  const toolCalls: ToolCall[] | undefined = (lastMessage as any).tool_calls;

  if (!toolCalls || toolCalls.length === 0) return state;

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

  const action = queue.shift()!;
  const toolCallingMsg = new AIMessage({
    content: "Executing confirmed tool call.",
    tool_calls: [
      { name: action.tool_name, args: action.tool_args, id: "confirmed_call_1" },
    ],
  });

  return { messages: [...state.messages, toolCallingMsg], pending_action: queue };
}

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

// ── Routing ────────────────────────────────────────────────────────────────────

function routeToToolOrLlm(state: AgentStateType): string {
  return state.pending_action && state.pending_action.length > 0
    ? "execute_tool"
    : "tool_calling_llm";
}

function routeConfirmationCheck(state: AgentStateType): string {
  const last = state.messages[state.messages.length - 1] as any;
  return last.tool_calls?.length ? "confirmation_required" : "__end__";
}

function routeToConfirmOrTool(state: AgentStateType): string {
  const action = (state.pending_action ?? [])[0];
  return action?.confirmed === "true" ? "execute_tool" : "user_confirmation";
}

function routeAfterExecute(state: AgentStateType): string {
  const last = state.messages[state.messages.length - 1] as any;
  return last.tool_calls?.length ? "tools" : "__end__";
}

function routeAfterExecution(state: AgentStateType): string {
  return state.pending_action?.length ? "confirm_next" : "tool_calling_llm";
}

// ── Graph construction ─────────────────────────────────────────────────────────

const graphBuilder = new StateGraph(AgentState)
  .addNode("tool_calling_llm", toolCallingLlm)
  .addNode("confirmation_required", toolsConditionNode)
  .addNode("user_confirmation", userConfirmation)
  .addNode("execute_tool", executeTool)
  .addNode("tools", toolNode)
  .addNode("confirm_next", confirmNext);

graphBuilder.addConditionalEdges(START, routeToToolOrLlm, {
  execute_tool: "execute_tool",
  tool_calling_llm: "tool_calling_llm",
});
graphBuilder.addConditionalEdges("tool_calling_llm", routeConfirmationCheck, {
  confirmation_required: "confirmation_required",
  [END]: END,
});
graphBuilder.addConditionalEdges("confirmation_required", routeToConfirmOrTool, {
  execute_tool: "execute_tool",
  user_confirmation: "user_confirmation",
});
graphBuilder.addEdge("user_confirmation", END);
graphBuilder.addConditionalEdges("execute_tool", routeAfterExecute, {
  tools: "tools",
  [END]: END,
});
graphBuilder.addConditionalEdges("tools", routeAfterExecution, {
  confirm_next: "confirm_next",
  tool_calling_llm: "tool_calling_llm",
});
graphBuilder.addEdge("confirm_next", END);
//graphBuilder.addEdge("tool_calling_llm", END);

const graph = graphBuilder.compile({ checkpointer: memory });

// ── Exported chat function ─────────────────────────────────────────────────────

const SYSTEM_MESSAGE = new SystemMessage(
  "You are an assistant that can use tools. " +
    "Only call tools when the user explicitly asks for file or OS actions " +
    "(list/read/create/delete/get os info). " +
    "If the user says hello or small talk, respond normally and do NOT call tools."
);

interface SessionState {
  messages: BaseMessage[];
  pending_action: PendingAction[];
}

const sessions = new Map<string, SessionState>();

export async function chat(
  threadId: string,
  userText: string
): Promise<{ reply: string; pendingAction: boolean }> {
  let session = sessions.get(threadId);
  if (!session) {
    session = { messages: [SYSTEM_MESSAGE], pending_action: [] };
    sessions.set(threadId, session);
  }

  session.messages.push(new HumanMessage(userText));

  const config = { configurable: { thread_id: threadId } };
  const result = await graph.invoke(
    { messages: session.messages, pending_action: session.pending_action },
    config
  );

  session.messages = result.messages;
  session.pending_action = result.pending_action ?? [];

  const last = result.messages[result.messages.length - 1];
  const reply = (last as any).content ?? JSON.stringify(last);

  return {
    reply: typeof reply === "string" ? reply : JSON.stringify(reply),
    pendingAction: session.pending_action.length > 0,
  };
}

import React, { useState, useRef, useEffect, FormEvent } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
  timestamp: number;
}

type InteractiveMessage =
  | {
      type: "confirmation";
      displayText: string;
    }
  | {
      type: "suggestion";
      displayText: string;
      suggestions: string[];
    }
  | {
      type: "filename_prompt";
      displayText: string;
    };

const API_URL = "/api/chat";
const THREAD_ID = "ui-session-1";

function extractFileName(message: string) {
  const match = message.match(/'file_name': '(.+?)'/);
  return match ? match[1] : null;
}

function parseConfirmationMessage(message: string): InteractiveMessage | null {
  const isConfirmation =
    /^Run(?: next tool)? '(.+?)' with .*?\? \(yes\/no\)$/.exec(message);

  if (!isConfirmation) return null;

  const toolName = isConfirmation[1];
  const fileName = extractFileName(message);

  if (toolName === "delete_file" && fileName) {
    return {
      type: "confirmation",
      displayText: `Are you sure you want to delete ${fileName}?`,
    };
  }

  if (toolName === "create_file" && fileName) {
    return {
      type: "confirmation",
      displayText: `Do you want to create ${fileName}?`,
    };
  }

  if (toolName === "get_file_content" && fileName) {
    return {
      type: "confirmation",
      displayText: `Do you want the contents of ${fileName}?`,
    };
  }

  if (toolName === "list_files") {
    return {
      type: "confirmation",
      displayText: "Do you want to list the files?",
    };
  }

  if (toolName === "get_os_info") {
    return {
      type: "confirmation",
      displayText: "Do you want to view the operating system information?",
    };
  }

  return {
    type: "confirmation",
    displayText: message,
  };
}

function parseSuggestionMessage(message: string): InteractiveMessage | null {
  const match = message.match(
    /^File '(.+?)' not found\. Did you mean: (.+)\?$/,
  );
  if (!match) return null;

  const suggestions = match[2]
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  return {
    type: "suggestion",
    displayText: "That file was not found. Try one of these:",
    suggestions,
  };
}

function parseFilenamePrompt(message: string): InteractiveMessage | null {
  if (message.trim() === "What would you like to name the new file?") {
    return {
      type: "filename_prompt",
      displayText: message,
    };
  }

  return null;
}

function parseInteractiveMessage(message: string): InteractiveMessage | null {
  return (
    parseConfirmationMessage(message) ||
    parseSuggestionMessage(message) ||
    parseFilenamePrompt(message)
  );
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const lastAssistantMessage = [...messages]
    .reverse()
    .find((m) => m.role === "assistant");

  const filenamePrompt =
    lastAssistantMessage?.text.trim() ===
    "What would you like to name the new file?";

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", text, timestamp: Date.now() },
    ]);
    setLoading(true);

    try {

      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: THREAD_ID, message: text }),
      });

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.reply ?? "No response.",
          timestamp: Date.now(),
        },
      ]);
    } catch (error) {
      console.error("Error sending message to agent server:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Error: could not reach the agent server.",
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    await sendMessage(text);
  }

  async function sendQuickReply(text: "yes" | "no") {
    await sendMessage(text);
  }

  async function sendSuggestion(text: string) {
    await sendMessage(text);
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>File Assistant 📁</header>

      <div style={styles.messages}>
        {messages.length === 0 && (
          <p style={styles.placeholder}>Send a message to start chatting.</p>
        )}

        {messages.map((m, i) => {
          const interactive =
            m.role === "assistant" ? parseInteractiveMessage(m.text) : null;

          return (
            <div
              key={i}
              style={{
                ...styles.bubble,
                ...(m.role === "user"
                  ? styles.userBubble
                  : styles.assistantBubble),
              }}
            >
              <span style={styles.roleLabel}>
                {m.role === "user" ? "You" : "Agent"} •{" "}
                {new Date(m.timestamp).toLocaleTimeString()}
              </span>

              <p style={styles.bubbleText}>
                {interactive ? interactive.displayText : m.text}
              </p>

              {interactive?.type === "confirmation" && (
                <div style={styles.confirmationButtons}>
                  <button
                    type="button"
                    style={styles.confirmButton}
                    onClick={() => sendQuickReply("yes")}
                    disabled={loading}
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    style={styles.confirmButton}
                    onClick={() => sendQuickReply("no")}
                    disabled={loading}
                  >
                    No
                  </button>
                </div>
              )}

              {interactive?.type === "suggestion" && (
                <div style={styles.confirmationButtons}>
                  {interactive.suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      style={styles.suggestionButton}
                      onClick={() => sendSuggestion(suggestion)}
                      disabled={loading}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {interactive?.type === "filename_prompt" && (
                <div style={styles.promptHint}>
                  Supported file types: .txt, .docx, .pdf
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div style={{ ...styles.bubble, ...styles.assistantBubble }}>
            <span style={styles.roleLabel}>Agent</span>
            <p style={styles.bubbleText}>Thinking…</p>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} style={styles.form}>
        <input
          style={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            filenamePrompt
              ? "Enter a file name like summary.docx"
              : "Type a message…"
          }
          disabled={loading}
        />
        <button type="submit" style={styles.button} disabled={loading}>
          Send
        </button>
      </form>
    </div>
  );
}

/* ── Inline styles ────────────────────────────────────────────────────────── */

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "95vh",
    width: "60%",
    margin: "10px auto",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    background: "#1e1e2e",
    color: "#cdd6f4",
    borderRadius: "8px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
    overflow: "hidden",
  },
  header: {
    padding: "14px 20px",
    fontSize: "1.2rem",
    fontWeight: 600,
    borderBottom: "1px solid #313244",
    background: "#181825",
    borderRadius: "8px 8px 0 0",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  placeholder: {
    color: "#6c7086",
    textAlign: "center",
    marginTop: "40px",
  },
  bubble: {
    maxWidth: "75%",
    padding: "10px 14px",
    borderRadius: "12px",
    lineHeight: 1.45,
  },
  userBubble: {
    alignSelf: "flex-end",
    background: "#45475a",
  },
  assistantBubble: {
    alignSelf: "flex-start",
    background: "#313244",
  },
  roleLabel: {
    fontSize: "0.7rem",
    fontWeight: 700,
    textTransform: "uppercase",
    color: "#a6adc8",
    marginBottom: "2px",
    display: "block",
  },
  bubbleText: {
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  confirmationButtons: {
    marginTop: "8px",
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
  },
  confirmButton: {
    padding: "6px 14px",
    fontSize: "0.9rem",
    borderRadius: "8px",
    border: "none",
    background: "#89b4fa",
    color: "#1e1e2e",
    fontWeight: 600,
    cursor: "pointer",
  },
  suggestionButton: {
    padding: "6px 12px",
    fontSize: "0.9rem",
    borderRadius: "999px",
    border: "1px solid #89b4fa",
    background: "transparent",
    color: "#89b4fa",
    fontWeight: 600,
    cursor: "pointer",
  },
  promptHint: {
    marginTop: "8px",
    fontSize: "0.85rem",
    color: "#a6adc8",
  },
  form: {
    display: "flex",
    padding: "12px 20px",
    gap: "10px",
    borderTop: "1px solid #313244",
    background: "#181825",
    borderRadius: "0 0 8px 8px",
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    fontSize: "1rem",
    borderRadius: "8px",
    border: "1px solid #45475a",
    background: "#1e1e2e",
    color: "#cdd6f4",
    outline: "none",
  },
  button: {
    padding: "10px 20px",
    fontSize: "1rem",
    borderRadius: "8px",
    border: "none",
    background: "#89b4fa",
    color: "#1e1e2e",
    fontWeight: 600,
    cursor: "pointer",
  },
};

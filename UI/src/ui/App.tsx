import React, { useState, useRef, useEffect, FormEvent } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
}

const API_URL = "/api/chat";
const THREAD_ID = "ui-session-1";

function parseConfirmationMessage(message: string) {
  const deleteMatch = message.match(
    /^Run 'delete_file' with \{'file_name': '(.+?)'\}\? \(yes\/no\)$/,
  );

  if (deleteMatch) {
    return {
      displayText: `Are you sure you want to delete ${deleteMatch[1]}?`,
    };
  }

  const createMatch = message.match(
    /^Run 'create_file' with \{.*'file_name': '(.+?)'.*\}\? \(yes\/no\)$/,
  );

  if (createMatch) {
    return {
      displayText: `Do you want to create ${createMatch[1]}?`,
    };
  }

  const readMatch = message.match(
    /^Run 'get_file_content' with \{'file_name': '(.+?)'\}\? \(yes\/no\)$/,
  );

  if (readMatch) {
    return {
      displayText: `Do you want the contents of ${readMatch[1]}?`,
    };
  }

  const listMatch = message.match(/^Run 'list_files'.*\? \(yes\/no\)$/);

  if (listMatch) {
    return {
      displayText: "Do you want to list the files?",
    };
  }

  const osMatch = message.match(/^Run 'get_os_info'.*\? \(yes\/no\)$/);

  if (osMatch) {
    return {
      displayText: "Do you want to view the operating system information?",
    };
  }

  return null;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      console.log("API URL:", API_URL);
      console.log("Current thread ID:", THREAD_ID);
      console.log("Sending message to agent server:", text);
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: THREAD_ID, message: text }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: data.reply ?? "No response." },
      ]);
    } catch (error) {
      console.error("Error sending message to agent server:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Error: could not reach the agent server." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function sendQuickReply(text: "yes" | "no") {
    if (loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    try {
      console.log("API URL:", API_URL);
      console.log("Current thread ID:", THREAD_ID);
      console.log("Sending quick reply to agent server:", text);
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: THREAD_ID, message: text }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: data.reply ?? "No response." },
      ]);
    } catch (error) {
      console.error("Error sending quick reply to agent server:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Error: could not reach the agent server." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>File Assistant 📁</header>

      <div style={styles.messages}>
        {messages.length === 0 && (
          <p style={styles.placeholder}>Send a message to start chatting.</p>
        )}
        {messages.map((m, i) => {
          const confirmation =
            m.role === "assistant" ? parseConfirmationMessage(m.text) : null;

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
                {m.role === "user" ? "You" : "Agent"}
              </span>
              <p style={styles.bubbleText}>
                {confirmation ? confirmation.displayText : m.text}
              </p>

              {confirmation && (
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
          placeholder="Type a message…"
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
    textTransform: "uppercase" as const,
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

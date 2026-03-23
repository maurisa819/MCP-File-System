import React, { useState, useRef, useEffect, FormEvent } from "react";

interface Message {
  role: "user" | "assistant";
  text: string;
}

const API_URL = "/api/chat";
const THREAD_ID = "ui-session-1";

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

  return (
    <div style={styles.container}>
      <header style={styles.header}>AI Chat</header>

      <div style={styles.messages}>
        {messages.length === 0 && (
          <p style={styles.placeholder}>Send a message to start chatting.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              ...styles.bubble,
              ...(m.role === "user" ? styles.userBubble : styles.assistantBubble),
            }}
          >
            <span style={styles.roleLabel}>
              {m.role === "user" ? "You" : "Agent"}
            </span>
            <p style={styles.bubbleText}>{m.text}</p>
          </div>
        ))}
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

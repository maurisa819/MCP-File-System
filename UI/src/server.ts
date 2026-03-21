import express from "express";
import cors from "cors";
import { chat } from "./agent.js";

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

app.post("/api/chat", async (req, res) => {
  const { threadId, message } = req.body;

  if (!message || typeof message !== "string") {
    res.status(400).json({ error: "message is required" });
    return;
  }

  const thread = typeof threadId === "string" && threadId ? threadId : "default";

  try {
    const result = await chat(thread, message);
    res.json(result);
  } catch (err) {
    console.error("Agent error:", err);
    res.status(500).json({ error: "Agent failed to process the request." });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

# Agent skills: demand → tool mapping

Use these rules to choose the right tool and respond accurately.

## When to call tools

- Call tools **only** when the user clearly asks for a file or OS action. Examples: list directory, read file, create file, delete file, get OS/platform info.
- Do **not** call tools for: greetings, small talk, questions about what you *could* do, or vague requests. Reply in plain language only.

## Demand → tool mapping

| User demand (examples) | Tool to call | Notes |
|------------------------|--------------|--------|
| "What OS?", "system info", "platform?", "where is this running?" | get_os_info | No arguments. |
| "List files", "what's in this folder?", "show directory", "contents of this folder" | list_files | Use when user wants to see names of files in a directory. |
| "Read X", "open X", "show content of X", "what's in X?" | get_file_content | Pass the exact file name the user gave as `file_name`. |
| "Create file X", "make a file named X", "write X with ..." | create_file | Use `file_name` and `content` (empty string if they don't specify content). |
| "Delete X", "remove X", "erase X" | delete_file | Pass the exact file name as `file_name`. |

## File names and paths

- Use the **exact file name** the user mentioned (e.g. "notes.txt" → file_name="notes.txt"). Do not invent paths unless the user specified a path.
- If the user gives only a name (e.g. "read notes.txt"), pass that name only. Do not add directories unless the user clearly specified one.

## Response style

- After a tool runs, summarize the **result** briefly for the user (e.g. "Here are the files: ...", "File content: ...", "Created/deleted ...").
- If a tool returns an error message, relay it clearly and suggest a fix if obvious (e.g. "File not found — check the name or list the directory first").
- Keep answers concise; avoid repeating the raw tool output verbatim unless the user asked for raw output.

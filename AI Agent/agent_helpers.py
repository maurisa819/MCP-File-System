import os
import re
import json
import shlex
import asyncio
from difflib import get_close_matches
from typing import Any

from fastmcp import Client
from langchain_core.messages import HumanMessage


# ── Exceptions ─────────────────────────────────────────────────────────────────

class FileSuggestionError(ValueError):
    """Raised when a requested file is not found but close matches may exist."""

    def __init__(self, file_name: str, suggestions: list[str] | None = None):
        self.file_name = file_name
        self.suggestions = suggestions or []

        if self.suggestions:
            msg = f"File '{file_name}' not found. Did you mean: {', '.join(self.suggestions)}?"
        else:
            msg = f"File '{file_name}' not found."

        super().__init__(msg)


# ── MCP helper ─────────────────────────────────────────────────────────────────

async def mcp_tools(mcp_client: str, tool_name: str, args: dict | None = None):
    """Call a tool on the MCP server and unwrap common FastMCP result shapes."""
    args = args or {}
    async with Client(mcp_client) as client:
        result = await client.call_tool(tool_name, args)

        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured

        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured

        content = getattr(result, "content", None)
        if content is not None:
            if isinstance(content, str):
                return content

            if isinstance(content, list):
                extracted = []
                for item in content:
                    text = getattr(item, "text", None)
                    if text is not None:
                        extracted.append(text)
                    elif isinstance(item, dict) and "text" in item:
                        extracted.append(item["text"])
                    else:
                        extracted.append(str(item))
                return extracted

        if isinstance(result, (dict, list, str)):
            return result

        data = getattr(result, "data", None)
        if data is not None:
            return data

        return result


# ── Parsing / normalization helpers ────────────────────────────────────────────

def _maybe_stringify(value: Any) -> str:
    """Convert arbitrary tool output into a readable string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


def extract_text_from_mcp_result(result: Any) -> str:
    """Extract readable text from common MCP return shapes."""
    if result is None:
        return ""

    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        if "ok" in result and "text" in result:
            if result.get("ok", False):
                text = result.get("text", "")
                return text if isinstance(text, str) else _maybe_stringify(text)
            return str(result.get("error", "Unknown error."))

        if "result" in result:
            inner = result["result"]
            return inner if isinstance(inner, str) else _maybe_stringify(inner)

        return _maybe_stringify(result)

    if isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(_maybe_stringify(item["text"]))
                else:
                    parts.append(_maybe_stringify(item))
            else:
                parts.append(_maybe_stringify(item))
        return "\n".join(part for part in parts if part).strip()

    return _maybe_stringify(result)


def extract_result_text(result: Any) -> str:
    """Normalize MCP success/error results into a clean string."""
    return extract_text_from_mcp_result(result)


def clean_extracted_text(text: str) -> str:
    """Clean extracted text for downstream reading/summarization."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n\t]+", " ", text)
    text = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", text)

    lines = [line.strip() for line in text.split("\n")]
    cleaned = []
    empty_count = 0

    for line in lines:
        if not line:
            empty_count += 1
            if empty_count <= 1:
                cleaned.append("")
        else:
            empty_count = 0
            cleaned.append(line)

    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def detect_file_type(file_name: str) -> str:
    """Return file extension in lowercase."""
    _, ext = os.path.splitext(file_name.lower())
    return ext


def default_summary_instruction(file_name: str) -> str:
    """Choose a default summary instruction based on file type."""
    ext = detect_file_type(file_name)

    if ext in {".ppt", ".pptx"}:
        return (
            "Summarize this presentation by focusing on slide titles, main bullet points, "
            "key arguments, findings, and conclusions. Preserve structure."
        )
    if ext in {".csv", ".xlsx", ".xls"}:
        return (
            "Summarize this spreadsheet by identifying the main columns, key values, "
            "trends, comparisons, and takeaways."
        )
    if ext == ".pdf":
        return (
            "Summarize this PDF by focusing on major sections, key concepts, findings, "
            "important details, and final conclusions."
        )
    if ext in {".doc", ".docx"}:
        return (
            "Summarize this document by focusing on the main sections, important points, "
            "decisions, findings, and conclusions."
        )
    return "Summarize this clearly and concisely."


# ── File helpers ───────────────────────────────────────────────────────────────

FILE_NAME_TOOLS = {"get_file_content", "delete_file"}


def extract_filename_from_text(text: str) -> str:
    """Extract a likely filename from free text."""
    if not text:
        return ""

    match = re.search(
        r'([\w\-. ]+\.(pdf|docx|doc|pptx|ppt|txt|csv|xlsx|xls|md|json))',
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def normalize_tool_args(tool_name: str, tool_args: dict | None, user_text: str) -> dict:
    """Ensure file tools get file_name when the model omits it."""
    args = dict(tool_args or {})

    if tool_name in FILE_NAME_TOOLS and not args.get("file_name"):
        inferred = extract_filename_from_text(user_text)
        if inferred:
            args["file_name"] = inferred

    return args


async def get_available_files(mcp_client: str) -> list[str]:
    """Fetch the available file list from the MCP server."""
    result = await mcp_tools(mcp_client, "list_files", {})

    if isinstance(result, list):
        return [str(item) for item in result]

    if isinstance(result, dict):
        files = result.get("result")
        if isinstance(files, list):
            return [str(item) for item in files]

    if isinstance(result, str):
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        return [line for line in lines if "." in os.path.basename(line)]

    return []


async def resolve_file_name(mcp_client: str, file_name: str) -> str:
    """Resolve exact/case-insensitive names or raise a suggestion error."""
    files = await get_available_files(mcp_client)

    if not files:
        raise FileSuggestionError(file_name, [])

    if file_name in files:
        return file_name

    for f in files:
        if f.lower() == file_name.lower():
            return f

    matches = get_close_matches(file_name, files, n=3, cutoff=0.5)
    raise FileSuggestionError(file_name, matches)


async def read_file_cached(
    mcp_client: str,
    file_name: str,
    file_content_cache: dict[str, str],
) -> str:
    """Read a file with cache support."""
    resolved_name = await resolve_file_name(mcp_client, file_name)

    if resolved_name in file_content_cache:
        return file_content_cache[resolved_name]

    raw = await mcp_tools(mcp_client, "get_file_content", {"file_name": resolved_name})
    text = extract_text_from_mcp_result(raw)
    text = clean_extracted_text(text)
    file_content_cache[resolved_name] = text
    return text


# ── Summarize / compare helpers ────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 12000,
    overlap: int = 300,
    max_chunks: int = 6,
) -> list[str]:
    """Split long text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text) and len(chunks) < max_chunks:
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)

    return chunks


def split_text_for_qa(text: str, chunk_size: int = 6000) -> list[str]:
    """Split text by page markers when possible, otherwise by chunk size."""
    text = clean_extracted_text(text)
    if not text:
        return []

    page_pattern = re.compile(r"(?=--- Page \d+ ---)")
    pages = [part.strip() for part in page_pattern.split(text) if part.strip()]

    if len(pages) > 1:
        return pages

    return chunk_text(text, chunk_size=chunk_size, overlap=200, max_chunks=12)


async def summarize_large_text(llm, text: str, instructions: str = "") -> str:
    """Summarize large text, chunking if necessary."""
    text = clean_extracted_text(text)
    if not text.strip():
        return "The file appears to be empty or no readable text could be extracted."

    chunks = chunk_text(text)

    if len(chunks) == 1:
        result = await asyncio.to_thread(
            llm.invoke,
            [HumanMessage(content=f"{instructions}\n\n{chunks[0]}")],
        )
        return result.content if isinstance(result.content, str) else str(result.content)

    partials = []
    for chunk in chunks:
        result = await asyncio.to_thread(
            llm.invoke,
            [HumanMessage(content=f"{instructions}\n\n{chunk}")],
        )
        partials.append(result.content if isinstance(result.content, str) else str(result.content))

    merged = await asyncio.to_thread(
        llm.invoke,
        [HumanMessage(content="\n\n".join(partials))],
    )
    return merged.content if isinstance(merged.content, str) else str(merged.content)


async def summarize_file_helper(
    mcp_client: str,
    llm,
    file_name: str,
    summary_cache: dict[tuple[str, str], str],
    file_content_cache: dict[str, str],
) -> str:
    """Summarize a file with cache support."""
    resolved_name = await resolve_file_name(mcp_client, file_name)
    cache_key = (resolved_name, "default")

    if cache_key in summary_cache:
        return summary_cache[cache_key]

    text = await read_file_cached(mcp_client, resolved_name, file_content_cache)
    summary = await summarize_large_text(llm, text, default_summary_instruction(resolved_name))
    summary_cache[cache_key] = summary
    return summary


async def compare_many(
    mcp_client: str,
    llm,
    files: list[str],
    file_content_cache: dict[str, str],
) -> str:
    """Compare multiple files using grounded summaries."""
    resolved_files = [await resolve_file_name(mcp_client, file_name) for file_name in files]
    texts = await asyncio.gather(*[
        read_file_cached(mcp_client, file_name, file_content_cache)
        for file_name in resolved_files
    ])

    cleaned = [clean_extracted_text(t) for t in texts]

    for i, text in enumerate(cleaned):
        if not text.strip():
            return f"File '{resolved_files[i]}' appears to be empty or no readable text could be extracted."

    if all(len(text.split()) < 40 for text in cleaned):
        previews = []
        for i, text in enumerate(cleaned):
            preview = text.replace("\n", " ").strip()
            previews.append(f"{resolved_files[i]}: {preview}")

        return (
            "These files are not meaningfully comparable beyond basic document/file differences.\n\n"
            + "\n".join(previews)
        )

    summaries = []
    for i, text in enumerate(cleaned):
        summaries.append(
            await summarize_large_text(
                llm,
                text,
                f"{default_summary_instruction(resolved_files[i])}\n"
                "Focus on information that will help comparison."
            )
        )

    prompt = (
        "Compare these documents using only the provided summaries.\n"
        "Do not say the documents are unavailable.\n"
        "If they have little in common, say that clearly.\n"
        "If the comparison is weak or only superficial, say so directly.\n\n"
    )
    prompt += "\n\n".join(
        f"Document {i+1} ({resolved_files[i]}):\n{summaries[i]}"
        for i in range(len(resolved_files))
    )

    result = await asyncio.to_thread(
        llm.invoke,
        [HumanMessage(content=prompt)],
    )
    return result.content if isinstance(result.content, str) else str(result.content)


async def answer_question_from_file(
    llm,
    question: str,
    file_text: str,
) -> str:
    """Answer a question from file content by checking pages/chunks and stopping early."""
    cleaned = clean_extracted_text(file_text)
    if not cleaned:
        return "The file appears to be empty or no readable text could be extracted."

    parts = split_text_for_qa(cleaned)
    if not parts:
        return "The file appears to be empty or no readable text could be extracted."

    for part in parts:
        check_prompt = (
            "You are checking whether the following file excerpt contains enough information to answer the user's question.\n"
            "If the excerpt contains enough information, reply exactly in this format:\n"
            "FOUND: <answer>\n"
            "If the excerpt does not contain enough information, reply exactly: NOT FOUND\n\n"
            f"User question:\n{question}\n\n"
            f"File excerpt:\n{part}"
        )

        result = await asyncio.to_thread(
            llm.invoke,
            [HumanMessage(content=check_prompt)],
        )
        answer = result.content if isinstance(result.content, str) else str(result.content)
        answer = answer.strip()

        if answer.startswith("FOUND:"):
            return answer[len("FOUND:"):].strip()

    final_prompt = (
        "Answer the user's question using only the file content below.\n"
        "If the answer is not clearly stated, say that.\n"
        "Do not dump the entire file.\n"
        "Give a concise answer.\n\n"
        f"User question:\n{question}\n\n"
        f"File content:\n{cleaned}"
    )
    result = await asyncio.to_thread(
        llm.invoke,
        [HumanMessage(content=final_prompt)],
    )
    return result.content if isinstance(result.content, str) else str(result.content)


# ── Direct action helpers ──────────────────────────────────────────────────────

async def create_file_response(mcp_client: str, file_name: str, content: str) -> str:
    """Create a file and return a clean response string."""
    result = await mcp_tools(mcp_client, "create_file", {"file_name": file_name, "content": content})
    return extract_result_text(result)


async def delete_file_response(mcp_client: str, file_name: str) -> str:
    """Delete a file and return a clean response string."""
    resolved_name = await resolve_file_name(mcp_client, file_name)
    result = await mcp_tools(mcp_client, "delete_file", {"file_name": resolved_name})
    return extract_result_text(result)


async def get_file_content_response(
    mcp_client: str,
    file_name: str,
    file_content_cache: dict[str, str],
) -> str:
    """Read file content and return a clean response string."""
    resolved_name = await resolve_file_name(mcp_client, file_name)
    content = await read_file_cached(mcp_client, resolved_name, file_content_cache)

    if not content.strip():
        return f"The content of the file {resolved_name} is empty."

    return f"The content of the file {resolved_name} is:\n\n{content}"


# ── Pending flow helpers ───────────────────────────────────────────────────────

def set_pending_resolution(sessions: dict, thread_id: str, payload: dict) -> None:
    """Store an unresolved file-based workflow awaiting corrected filename."""
    session = sessions.get(thread_id)
    if session is not None:
        session["pending_resolution"] = payload


def clear_pending_resolution(sessions: dict, thread_id: str) -> None:
    """Clear the pending filename-resolution workflow."""
    session = sessions.get(thread_id)
    if session is not None:
        session["pending_resolution"] = None


async def continue_pending_resolution(
    sessions: dict,
    thread_id: str,
    user_text: str,
    mcp_client: str,
    llm,
    file_content_cache: dict[str, str],
    summary_cache: dict[tuple[str, str], str],
    last_output_by_thread: dict[str, str],
) -> dict | None:
    """Continue a previously failed flow after the user clarifies the filename."""
    session = sessions.get(thread_id)
    if session is None:
        return None

    pending = session.get("pending_resolution")
    if not pending:
        return None

    candidate = user_text.strip()

    if not extract_filename_from_text(candidate):
        clear_pending_resolution(sessions, thread_id)
        return None

    try:
        corrected = await resolve_file_name(mcp_client, candidate)
    except FileSuggestionError as e:
        return {"reply": str(e), "pendingAction": False}

    action = pending.get("action")

    try:
        if action == "read":
            clear_pending_resolution(sessions, thread_id)
            reply = await get_file_content_response(mcp_client, corrected, file_content_cache)
            last_output_by_thread[thread_id] = reply
            return {"reply": reply, "pendingAction": False}

        if action == "delete":
            clear_pending_resolution(sessions, thread_id)
            reply = await delete_file_response(mcp_client, corrected)
            last_output_by_thread[thread_id] = reply
            return {"reply": reply, "pendingAction": False}

        if action == "summarize":
            clear_pending_resolution(sessions, thread_id)
            summary = await summarize_file_helper(
                mcp_client, llm, corrected, summary_cache, file_content_cache
            )
            last_output_by_thread[thread_id] = summary

            output_file = pending.get("output_file")
            ask_for_name = pending.get("ask_for_name", False)

            if ask_for_name:
                session["pending_save"] = summary
                return {"reply": "What would you like to name the new file?", "pendingAction": False}

            if output_file:
                if not output_file.lower().endswith((".txt", ".docx", ".pdf")):
                    return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}
                reply = await create_file_response(mcp_client, output_file, summary)
                last_output_by_thread[thread_id] = reply
                return {"reply": reply, "pendingAction": False}

            return {"reply": summary, "pendingAction": False}

        if action == "compare":
            clear_pending_resolution(sessions, thread_id)
            files = list(pending.get("files", []))
            missing_index = pending.get("missing_index", 0)
            files[missing_index] = corrected

            comparison = await compare_many(mcp_client, llm, files, file_content_cache)
            last_output_by_thread[thread_id] = comparison

            output_file = pending.get("output_file")
            ask_for_name = pending.get("ask_for_name", False)

            if ask_for_name:
                session["pending_save"] = comparison
                return {"reply": "What would you like to name the new file?", "pendingAction": False}

            if output_file:
                if not output_file.lower().endswith((".txt", ".docx", ".pdf")):
                    return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}
                reply = await create_file_response(mcp_client, output_file, comparison)
                last_output_by_thread[thread_id] = reply
                return {"reply": reply, "pendingAction": False}

            return {"reply": comparison, "pendingAction": False}

    except FileSuggestionError as e:
        return {"reply": str(e), "pendingAction": False}

    return None


# ── Slash command helpers ──────────────────────────────────────────────────────

def parse_compare_files(text: str) -> list[str]:
    """Parse compare file arguments, supporting quoted names and skipping connectors."""
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = [part.strip() for part in text.split() if part.strip()]

    return [p for p in parts if p.lower() not in {"and", ","}]


async def handle_slash_command(
    sessions: dict,
    thread_id: str,
    user_text: str,
    mcp_client: str,
    llm,
    file_content_cache: dict[str, str],
    summary_cache: dict[tuple[str, str], str],
    last_output_by_thread: dict[str, str],
) -> dict | None:
    """Handle summarize/compare/save slash commands and save-related follow-ups."""
    stripped = user_text.strip()
    session = sessions.get(thread_id)

    if stripped.startswith("/summarize"):
        body = stripped[len("/summarize"):].strip()
        if not body:
            return {
                "reply": "Usage: /summarize <file> or /summarize <file> -> <output.docx>",
                "pendingAction": False,
            }

        source_file = None
        output_file = None
        ask_for_name = False

        if "->" in body:
            left, right = body.split("->", 1)
            source_file = left.strip()
            output_file = right.strip()
        else:
            match_save_as = re.match(r"^(.*?)\s+then\s+save\s+as\s+(.+)$", body, re.IGNORECASE)
            match_save_new = re.match(r"^(.*?)\s+then\s+save\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)
            match_put_new = re.match(r"^(.*?)\s+and\s+put\s+(?:the\s+)?summary\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)
            match_and_save_as = re.match(r"^(.*?)\s+and\s+save\s+as\s+(.+)$", body, re.IGNORECASE)
            match_and_save_new = re.match(r"^(.*?)\s+and\s+save\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)

            if match_save_as:
                source_file = match_save_as.group(1).strip()
                output_file = match_save_as.group(2).strip()
            elif match_save_new:
                source_file = match_save_new.group(1).strip()
                ask_for_name = True
            elif match_put_new:
                source_file = match_put_new.group(1).strip()
                ask_for_name = True
            elif match_and_save_as:
                source_file = match_and_save_as.group(1).strip()
                output_file = match_and_save_as.group(2).strip()
            elif match_and_save_new:
                source_file = match_and_save_new.group(1).strip()
                ask_for_name = True
            else:
                source_file = body.strip()

        if not source_file:
            return {
                "reply": "Usage: /summarize <file> or /summarize <file> -> <output.docx>",
                "pendingAction": False,
            }

        try:
            summary = await summarize_file_helper(
                mcp_client, llm, source_file, summary_cache, file_content_cache
            )
            last_output_by_thread[thread_id] = summary

            if ask_for_name:
                session["pending_save"] = summary
                return {"reply": "What would you like to name the new file?", "pendingAction": False}

            if output_file:
                if not output_file.lower().endswith((".txt", ".docx", ".pdf")):
                    return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}
                reply = await create_file_response(mcp_client, output_file, summary)
                last_output_by_thread[thread_id] = reply
                return {"reply": reply, "pendingAction": False}

            return {"reply": summary, "pendingAction": False}

        except FileSuggestionError as e:
            set_pending_resolution(sessions, thread_id, {
                "action": "summarize",
                "output_file": output_file,
                "ask_for_name": ask_for_name,
            })
            return {"reply": str(e), "pendingAction": False}

    if stripped.startswith("/compare"):
        body = stripped[len("/compare"):].strip()
        if not body:
            return {
                "reply": "Usage: /compare <file1> <file2> [file3 ...] or /compare <files...> -> <output.docx>",
                "pendingAction": False,
            }

        files = []
        output_file = None
        ask_for_name = False

        if "->" in body:
            left, right = body.split("->", 1)
            files = parse_compare_files(left.strip())
            output_file = right.strip()
        else:
            match_save_as = re.match(r"^(.*?)\s+then\s+save\s+as\s+(.+)$", body, re.IGNORECASE)
            match_save_new = re.match(r"^(.*?)\s+then\s+save\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)
            match_put_new = re.match(r"^(.*?)\s+and\s+put\s+(?:the\s+)?comparison\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)
            match_and_save_as = re.match(r"^(.*?)\s+and\s+save\s+as\s+(.+)$", body, re.IGNORECASE)
            match_and_save_new = re.match(r"^(.*?)\s+and\s+save\s+into\s+a\s+new\s+file\s*$", body, re.IGNORECASE)

            if match_save_as:
                files = parse_compare_files(match_save_as.group(1).strip())
                output_file = match_save_as.group(2).strip()
            elif match_save_new:
                files = parse_compare_files(match_save_new.group(1).strip())
                ask_for_name = True
            elif match_put_new:
                files = parse_compare_files(match_put_new.group(1).strip())
                ask_for_name = True
            elif match_and_save_as:
                files = parse_compare_files(match_and_save_as.group(1).strip())
                output_file = match_and_save_as.group(2).strip()
            elif match_and_save_new:
                files = parse_compare_files(match_and_save_new.group(1).strip())
                ask_for_name = True
            else:
                files = parse_compare_files(body)

        if len(files) < 2:
            return {"reply": "Please provide at least two files to compare.", "pendingAction": False}

        try:
            comparison = await compare_many(mcp_client, llm, files, file_content_cache)
            last_output_by_thread[thread_id] = comparison

            if ask_for_name:
                session["pending_save"] = comparison
                return {"reply": "What would you like to name the new file?", "pendingAction": False}

            if output_file:
                if not output_file.lower().endswith((".txt", ".docx", ".pdf")):
                    return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}
                reply = await create_file_response(mcp_client, output_file, comparison)
                last_output_by_thread[thread_id] = reply
                return {"reply": reply, "pendingAction": False}

            return {"reply": comparison, "pendingAction": False}

        except FileSuggestionError as e:
            missing_name = e.file_name
            missing_index = next((i for i, f in enumerate(files) if f == missing_name), 0)
            set_pending_resolution(sessions, thread_id, {
                "action": "compare",
                "files": files,
                "missing_index": missing_index,
                "output_file": output_file,
                "ask_for_name": ask_for_name,
            })
            return {"reply": str(e), "pendingAction": False}

    if stripped.startswith("/save"):
        body = stripped[len("/save"):].strip()
        if not body:
            return {"reply": "Usage: /save <output.docx>", "pendingAction": False}

        if not body.lower().endswith((".txt", ".docx", ".pdf")):
            return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}

        content = last_output_by_thread.get(thread_id, "")
        if not content:
            return {"reply": "No previous output is available to save.", "pendingAction": False}

        reply = await create_file_response(mcp_client, body, content)
        last_output_by_thread[thread_id] = reply
        return {"reply": reply, "pendingAction": False}

    lowered = stripped.lower()
    if (
        lowered.startswith("save this")
        or lowered.startswith("save that")
        or lowered.startswith("put that in")
        or lowered.startswith("put this in")
        or lowered.startswith("put the summary into a new file")
        or lowered.startswith("put summary into a new file")
        or lowered.startswith("put the comparison into a new file")
        or lowered.startswith("put comparison into a new file")
    ):
        file_name = extract_filename_from_text(stripped)
        content = last_output_by_thread.get(thread_id, "")

        if not content:
            return {"reply": "No previous output is available to save.", "pendingAction": False}

        if file_name:
            if not file_name.lower().endswith((".txt", ".docx", ".pdf")):
                return {"reply": "Output file must end in .txt, .docx, or .pdf", "pendingAction": False}
            reply = await create_file_response(mcp_client, file_name, content)
            last_output_by_thread[thread_id] = reply
            return {"reply": reply, "pendingAction": False}

        session["pending_save"] = content
        return {"reply": "What would you like to name the new file?", "pendingAction": False}

    return None

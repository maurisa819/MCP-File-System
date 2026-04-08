from docx import Document
from fpdf import FPDF
from fastmcp import FastMCP
import logging
import os
import re
import json
from fileTypeReader import FileTypeReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fastmcp.server")


# ── Directory setup ────────────────────────────────────────────────────────────

BASE_DIR = os.getcwd()
SOURCE_DIR = os.environ.get("SOURCE_DIR", os.path.join(BASE_DIR, "source"))
os.environ["SOURCE_DIR"] = SOURCE_DIR

if not os.path.exists(SOURCE_DIR):
    logger.info(f"Creating source directory at {SOURCE_DIR}")
    os.makedirs(SOURCE_DIR, exist_ok=True)
else:
    logger.info(f"Source directory already exists at {SOURCE_DIR}")


def normalize_directory(directory: str | None = None) -> str:
    """Return a normalized absolute directory path."""
    if directory is None:
        directory = SOURCE_DIR

    if directory.startswith("~"):
        directory = os.path.expanduser(directory)

    if not os.path.isabs(directory):
        directory = os.path.abspath(directory)

    return directory


def ensure_directory_exists(directory: str | None = None) -> str:
    """Validate that a directory exists and return its normalized path."""
    directory = normalize_directory(directory)

    if not os.path.isdir(directory):
        logger.error(f"Directory not found: {directory}")
        raise FileNotFoundError(f"Directory '{directory}' does not exist.")

    return directory


def safe_join(directory: str | None, file_name: str) -> str:
    """Safely join directory and file name."""
    directory = ensure_directory_exists(directory)
    return os.path.join(directory, file_name)


# ── Content helpers ────────────────────────────────────────────────────────────

def classify_content_type(ext: str) -> str:
    ext = ext.lower()

    if ext in {".txt", ".md"}:
        return "text"
    if ext in {".doc", ".docx"}:
        return "document"
    if ext == ".pdf":
        return "pdf"
    if ext in {".ppt", ".pptx"}:
        return "presentation"
    if ext in {".xls", ".xlsx", ".csv"}:
        return "spreadsheet"
    if ext == ".svg":
        return "vector_image"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}:
        return "image"

    return "unknown"


def normalize_extracted_content(raw_content) -> str:
    """Convert extractor output into cleaner text for the agent."""
    if raw_content is None:
        return ""

    if isinstance(raw_content, dict):
        try:
            raw_content = json.dumps(raw_content, indent=2, ensure_ascii=False)
        except Exception:
            raw_content = str(raw_content)
    elif isinstance(raw_content, list):
        raw_content = "\n".join(str(x) for x in raw_content)
    else:
        raw_content = str(raw_content)

    text = raw_content.replace("\r\n", "\n").replace("\r", "\n")
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


# ── Shared reader ──────────────────────────────────────────────────────────────

file_reader = FileTypeReader()


# ── MCP server ─────────────────────────────────────────────────────────────────

mcp = FastMCP(name="My First MCP Server")


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool("get_os_info")
def get_os_info() -> dict:
    """Retrieve information about the operating system."""
    logger.info("Fetching OS information")
    return {
        "os_name": os.name,
        "platform": os.sys.platform,
        "cwd": os.getcwd(),
        "source_dir": SOURCE_DIR,
    }


@mcp.tool("list_files")
def list_files(directory: str = SOURCE_DIR) -> list:
    """List files in a specified directory."""
    try:
        directory = ensure_directory_exists(directory)
        logger.info(f"Listing files in directory: {directory}")
        return sorted(os.listdir(directory))
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {e}")
        return []


@mcp.tool("create_file")
def create_file(file_name: str, content: str = "", directory: str = SOURCE_DIR) -> str:
    """
    Create a new file with the specified content.

    Supported output types:
    - .txt
    - .docx
    - .pdf
    """
    logger.info(f"Creating file {file_name} in directory {directory}")

    try:
        file_path = safe_join(directory, file_name)
        ext = os.path.splitext(file_name)[1].lower()

        if ext == ".txt":
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)

        elif ext == ".docx":
            doc = Document()
            for line in content.splitlines():
                doc.add_paragraph(line)
            doc.save(file_path)

        elif ext == ".pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)

            for line in content.splitlines():
                pdf.multi_cell(0, 10, line)

            pdf.output(file_path)

        else:
            return f"Unsupported file type: {ext}. Supported types are .txt, .docx, .pdf"

        return f"File '{file_name}' created successfully in '{normalize_directory(directory)}'."

    except Exception as e:
        logger.error(f"Error creating file {file_name} in {directory}: {e}")
        return f"Error creating file '{file_name}': {e}"


@mcp.tool("delete_file")
def delete_file(file_name: str, directory: str = SOURCE_DIR) -> str:
    """Delete a specified file."""
    logger.info(f"Deleting file {file_name} from directory {directory}")

    try:
        file_path = safe_join(directory, file_name)

        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            return f"File '{file_name}' not found in '{normalize_directory(directory)}'."

        os.remove(file_path)
        return f"File '{file_name}' deleted successfully from '{normalize_directory(directory)}'."

    except Exception as e:
        logger.error(f"Error deleting file {file_name} from {directory}: {e}")
        return f"Error deleting file '{file_name}': {e}"


@mcp.tool("get_file_content")
def get_file_content(file_name: str, directory: str = SOURCE_DIR) -> dict:
    """
    Read and return normalized content plus metadata for a file.
    """
    logger.info(f"Reading file {file_name} from directory {directory}")

    try:
        directory = ensure_directory_exists(directory)
        file_path = safe_join(directory, file_name)

        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            return {
                "ok": False,
                "file_name": file_name,
                "directory": directory,
                "error": f"File '{file_name}' not found in '{directory}'.",
                "content_type": "missing",
                "text": "",
            }

        ext = os.path.splitext(file_name)[1].lower()
        raw_content = file_reader.read_file(file_name, directory)
        text = normalize_extracted_content(raw_content)

        return {
            "ok": True,
            "file_name": file_name,
            "directory": directory,
            "extension": ext,
            "content_type": classify_content_type(ext),
            "text": text,
        }

    except Exception as e:
        logger.error(f"Error reading file {file_name} from {directory}: {e}")
        return {
            "ok": False,
            "file_name": file_name,
            "directory": normalize_directory(directory),
            "error": str(e),
            "content_type": "error",
            "text": "",
        }


if __name__ == "__main__":
    mcp.run()
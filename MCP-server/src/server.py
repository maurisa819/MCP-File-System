from docx import Document
from fpdf import FPDF
from fastmcp import FastMCP
import logging
import os
from fileTypeReader import FileTypeReader

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fastmcp.server")

os.environ["SOURCE_DIR"] = os.path.join(os.getcwd(), "source")
source_dir = os.environ["SOURCE_DIR"]



if not os.path.exists(source_dir):
    logger.info(f"Creating source directory at {source_dir}")
    os.makedirs(source_dir)
else:
    logger.info(f"Source directory already exists at {source_dir}")



def set_working_directory(directory: str = None) -> str:
    """Sets the working directory for file operations.
    
    If no directory is provided, it defaults to the current working directory.

    params:
        directory: The directory to set as the working directory. Can be an absolute path,
        a relative path, or a path with a tilde (~) for the home directory.
    
    returns: The absolute path of the directory that has been set as the working directory.
    """

    logger.info(f"Setting working directory. Input directory: {directory}")
    if directory is None:
        directory = os.getcwd()
        logger.info(f"No directory provided, using current working directory: {directory}")
    else:
        logger.info(f"Using provided directory: {directory}")

    # Check if the directory is the current working directory before attempting to change to it
    logger.info(f"Absolute path of the directory: {os.path.abspath(directory)}")
    if os.path.abspath(directory) == os.getcwd():
        logger.info(f"Directory '{directory}' is already the current working directory.")
        return os.getcwd()

    # Check if the directory exists before attempting to change to it
    if not os.path.isdir(directory):
        logger.error(f"Directory not found: {directory}")
        raise FileNotFoundError(f"Directory '{directory}' does not exist.")    
    
    logger.info(f"Setting working directory to {directory}")
    if directory.startswith('~'):
        logger.info(f"Expanding user path for {directory}")
        directory = os.path.expanduser(directory)

    if not os.path.isabs(directory):
        logger.info(f"Converting to absolute path for {directory}")
        directory = os.path.abspath(directory)

    os.chdir(directory)

    return directory

set_working_directory(source_dir)

# 1. Create the server
mcp = FastMCP(name="My First MCP Server")

# 2. Define tools
@mcp.tool("get_os_info")
def get_os_info() -> dict:
    """Retrieves information about the operating system.
    
    returns: A dictionary containing the OS name, platform, and current working directory."""
    logger.info("Fetching OS information")
    return {
        "os_name": os.name,
        "platform": os.sys.platform,
        "cwd": os.getcwd()
    }

@mcp.tool("list_files")
def list_files(directory: str = source_dir) -> list:
    """Lists files in a specified directory.
    
    params:
        directory: The directory to list files from. If not provided, it defaults to the current working directory. Can be an absolute path, a relative path, or a path with a tilde (~) for the home directory. 

    returns: A list of file names in the specified directory. If the directory cannot be accessed, an empty list is returned.
    """

    logger.info(f"Listing files in directory: {directory}")
    try:
        return os.listdir(directory)
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {e}")
        return []
    
@mcp.tool("create_file")
def create_file(file_name: str, content: str = "", directory: str = source_dir) -> str:
    """Creates a new file with the specified content.
    
    params:
        file_name: The name of the file to create.
        content: The content to write to the file. If not provided, the file will be created empty.
        directory: The directory where the file should be created. If not provided, it defaults to the current working directory. Can be an absolute path, a relative path, or a path with a tilde (~) for the home directory.

    returns: A message indicating whether the file was created successfully or if an error occurred.
    """

    logger.info(f"Creating file {file_name} in directory {directory}")
    try:
        file_path = os.path.join(directory, file_name)
        ext = os.path.splitext(file_name)[1].lower()

        if ext == ".txt":
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)

        elif ext == ".docx":
            doc = Document()
            doc.add_paragraph(content)
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

        return f"File '{file_name}' created successfully in '{directory}'."

    except Exception as e:
        logger.error(f"Error creating file {file_name} in {directory}: {e}")
        return f"Error creating file '{file_name}': {e}"
    
@mcp.tool("delete_file")
def delete_file(file_name: str, directory: str = source_dir) -> str:
    """Deletes a specified file.
    
    params:
        file_name: The name of the file to delete.
        directory: The directory where the file is located. If not provided, it defaults to the current working directory. Can be an absolute path, a relative path, or a path with a tilde (~) for the home directory.

    returns: A message indicating whether the file was deleted successfully or if an error occurred.
    """

    logger.info(f"Deleting file {file_name} from directory {directory}")
    try:
        file_path = os.path.join(directory, file_name)
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            return f"File '{file_name}' not found in '{directory}'."
        
        os.remove(file_path)
        return f"File '{file_name}' deleted successfully from '{directory}'."
    except Exception as e:
        logger.error(f"Error deleting file {file_name} from {directory}: {e}")
        return f"Error deleting file '{file_name}': {e}"

@mcp.tool("get_file_content")
def get_file_content(file_name: str, directory: str = source_dir) -> str:
    """Reads and returns the content of a file.
    
    Supports reading content from:
    - Text files (.txt)
    - CSV files (.csv)
    - Word documents (.docx, .doc)
    - PowerPoint presentations (.pptx, .ppt)
    - Excel spreadsheets (.xlsx, .xls)
    - PDF documents (.pdf)
    - Image files (.jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff, .ico - returned as base64)
    - SVG files (.svg)
    
    params:
        file_name: The name of the file to read.
        directory: The directory where the file is located. If not provided, it defaults to the current working directory. Can be an absolute path, a relative path, or a path with a tilde (~) for the home directory.
    
    returns: The content of the file as a string. If the file cannot be read, an empty string is returned.
    """
    file_reader = FileTypeReader()
    return file_reader.read_file(file_name, directory)

# 5. Make the server runnable
if __name__ == "__main__":
    mcp.run()

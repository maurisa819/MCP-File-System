from fastmcp import FastMCP
import logging
import os
import csv
from io import StringIO
from docx import Document as DocxDocument
from pptx import Presentation
from openpyxl import load_workbook
from PyPDF2 import PdfReader

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
        with open(file_path, 'w') as file:
            file.write(content)
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
    
    params:
        file_name: The name of the file to read.
        directory: The directory where the file is located. If not provided, it defaults to the current working directory. Can be an absolute path, a relative path, or a path with a tilde (~) for the home directory.
    
    returns: The content of the file as a string. If the file cannot be read, an empty string is returned.
    """

    logger.info(f"Reading file content from {file_name} in directory {directory}")
    try:
        # Check if the file exists before attempting to read it
        file_path = os.path.join(directory, file_name)
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            return ""

        # Get file extension
        _, file_ext = os.path.splitext(file_name)
        file_ext = file_ext.lower()

        # Handle different file types
        if file_ext == '.txt':
            with open(file_path, 'r') as file:
                return file.read()
        
        elif file_ext == '.csv':
            content = StringIO()
            try:
                with open(file_path, 'r') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        content.write(','.join(row) + '\n')
                return content.getvalue()
            except Exception as e:
                logger.error(f"Error reading CSV file {file_path}: {e}")
                return ""
        
        elif file_ext in ['.docx']:
            try:
                doc = DocxDocument(file_path)
                content = []
                for para in doc.paragraphs:
                    content.append(para.text)
                for table in doc.tables:
                    for row in table.rows:
                        row_content = [cell.text for cell in row.cells]
                        content.append(' | '.join(row_content))
                return '\n'.join(content)
            except Exception as e:
                logger.error(f"Error reading DOCX file {file_path}: {e}")
                return ""
        
        elif file_ext in ['.doc']:
            logger.warning(f"Legacy .doc format not fully supported. Please use .docx format.")
            return ""
        
        elif file_ext in ['.pptx']:
            try:
                prs = Presentation(file_path)
                content = []
                for slide_num, slide in enumerate(prs.slides, 1):
                    content.append(f"--- Slide {slide_num} ---")
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            if shape.text.strip():
                                content.append(shape.text)
                return '\n'.join(content)
            except Exception as e:
                logger.error(f"Error reading PPTX file {file_path}: {e}")
                return ""
        
        elif file_ext in ['.ppt']:
            logger.warning(f"Legacy .ppt format not fully supported. Please use .pptx format.")
            return ""
        
        elif file_ext in ['.xlsx']:
            try:
                wb = load_workbook(file_path)
                content = []
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    content.append(f"--- Sheet: {sheet_name} ---")
                    for row in ws.iter_rows(values_only=True):
                        row_content = [str(cell) if cell is not None else '' for cell in row]
                        content.append(' | '.join(row_content))
                return '\n'.join(content)
            except Exception as e:
                logger.error(f"Error reading XLSX file {file_path}: {e}")
                return ""
        
        elif file_ext in ['.xls']:
            logger.warning(f"Legacy .xls format not fully supported. Please use .xlsx format.")
            return ""
        
        elif file_ext in ['.pdf']:
            try:
                pdf_reader = PdfReader(file_path)
                content = []
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    content.append(f"--- Page {page_num} ---")
                    content.append(page.extract_text())
                return '\n'.join(content)
            except Exception as e:
                logger.error(f"Error reading PDF file {file_path}: {e}")
                return ""
        
        else:
            logger.warning(f"Unsupported file format: {file_ext}")
            # Try to read as plain text for unknown formats
            try:
                with open(file_path, 'r') as file:
                    return file.read()
            except:
                return ""
        
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""

# 5. Make the server runnable
if __name__ == "__main__":
    mcp.run()
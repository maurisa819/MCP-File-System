import logging
import os
import csv
import base64
from io import StringIO
from docx import Document as DocxDocument
from pptx import Presentation
from openpyxl import load_workbook
from PyPDF2 import PdfReader

logger = logging.getLogger("fastmcp.server")


class FileTypeReader:
    """Handles reading various file types and extracting their content."""
    
    def read_file(self, file_name: str, directory: str) -> str:
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
            directory: The directory where the file is located.
        
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
                return self._read_txt(file_path)
            
            elif file_ext == '.csv':
                return self._read_csv(file_path)
            
            elif file_ext in ['.docx']:
                return self._read_docx(file_path)
            
            elif file_ext in ['.doc']:
                logger.warning(f"Legacy .doc format not fully supported. Please use .docx format.")
                return ""
            
            elif file_ext in ['.pptx']:
                return self._read_pptx(file_path)
            
            elif file_ext in ['.ppt']:
                logger.warning(f"Legacy .ppt format not fully supported. Please use .pptx format.")
                return ""
            
            elif file_ext in ['.xlsx']:
                return self._read_xlsx(file_path)
            
            elif file_ext in ['.xls']:
                logger.warning(f"Legacy .xls format not fully supported. Please use .xlsx format.")
                return ""
            
            elif file_ext in ['.pdf']:
                return self._read_pdf(file_path)
            
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico']:
                return self._read_image(file_path, file_ext)
            
            elif file_ext in ['.svg']:
                return self._read_svg(file_path)
            
            else:
                return self._read_unknown(file_path)
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""
    
    def _read_txt(self, file_path: str) -> str:
        """Reads a text file."""
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading TXT file {file_path}: {e}")
            return ""
    
    def _read_csv(self, file_path: str) -> str:
        """Reads a CSV file."""
        try:
            content = StringIO()
            with open(file_path, 'r') as file:
                reader = csv.reader(file)
                for row in reader:
                    content.write(','.join(row) + '\n')
            return content.getvalue()
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            return ""
    
    def _read_docx(self, file_path: str) -> str:
        """Reads a DOCX file."""
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
    
    def _read_pptx(self, file_path: str) -> str:
        """Reads a PPTX file."""
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
    
    def _read_xlsx(self, file_path: str) -> str:
        """Reads an XLSX file."""
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
    
    def _read_pdf(self, file_path: str) -> str:
        """Reads a PDF file."""
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
    
    def _read_image(self, file_path: str, file_ext: str) -> str:
        """Reads an image file and returns it as base64."""
        try:
            with open(file_path, 'rb') as file:
                image_data = file.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')
                return f"data:image/{file_ext[1:]};base64,{base64_data}"
        except Exception as e:
            logger.error(f"Error reading image file {file_path}: {e}")
            return ""
    
    def _read_svg(self, file_path: str) -> str:
        """Reads an SVG file."""
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading SVG file {file_path}: {e}")
            return ""
    
    def _read_unknown(self, file_path: str) -> str:
        """Attempts to read an unknown file format as plain text."""
        logger.warning(f"Unsupported file format: {file_path}")
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except:
            return ""

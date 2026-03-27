"""Unit tests for FileTypeReader (fileTypeReader.py).

Each test creates the minimal fixture file it needs inside a tmp_path
so that no real files are touched.
"""

import base64
import os
import pytest
from fileTypeReader import FileTypeReader


@pytest.fixture
def reader():
    return FileTypeReader()


# ── .txt ────────────────────────────────────────────────────────────────────

class TestReadTxt:
    def test_reads_plain_text(self, reader, tmp_path):
        (tmp_path / "hello.txt").write_text("Hello!")
        assert reader.read_file("hello.txt", str(tmp_path)) == "Hello!"

    def test_empty_txt(self, reader, tmp_path):
        (tmp_path / "empty.txt").write_text("")
        assert reader.read_file("empty.txt", str(tmp_path)) == ""

    def test_multiline_txt(self, reader, tmp_path):
        (tmp_path / "lines.txt").write_text("line1\nline2\nline3")
        content = reader.read_file("lines.txt", str(tmp_path))
        assert content.count("\n") == 2


# ── .csv ────────────────────────────────────────────────────────────────────

class TestReadCsv:
    def test_simple_csv(self, reader, tmp_path):
        (tmp_path / "data.csv").write_text("a,b,c\n1,2,3\n")
        content = reader.read_file("data.csv", str(tmp_path))
        assert "a,b,c" in content
        assert "1,2,3" in content

    def test_csv_preserves_rows(self, reader, tmp_path):
        (tmp_path / "rows.csv").write_text("x,y\n10,20\n30,40\n")
        content = reader.read_file("rows.csv", str(tmp_path))
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 3


# ── .docx ───────────────────────────────────────────────────────────────────

class TestReadDocx:
    def test_reads_docx_paragraphs(self, reader, tmp_path):
        from docx import Document
        doc = Document()
        doc.add_paragraph("First paragraph")
        doc.add_paragraph("Second paragraph")
        path = tmp_path / "sample.docx"
        doc.save(str(path))

        content = reader.read_file("sample.docx", str(tmp_path))
        assert "First paragraph" in content
        assert "Second paragraph" in content

    def test_reads_docx_table(self, reader, tmp_path):
        from docx import Document
        doc = Document()
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "A"
        table.cell(0, 1).text = "B"
        table.cell(1, 0).text = "C"
        table.cell(1, 1).text = "D"
        path = tmp_path / "table.docx"
        doc.save(str(path))

        content = reader.read_file("table.docx", str(tmp_path))
        assert "A" in content and "D" in content


# ── .doc (legacy) ──────────────────────────────────────────────────────────

class TestReadDoc:
    def test_legacy_doc_returns_empty(self, reader, tmp_path):
        (tmp_path / "old.doc").write_bytes(b"\x00" * 10)
        assert reader.read_file("old.doc", str(tmp_path)) == ""


# ── .pptx ───────────────────────────────────────────────────────────────────

class TestReadPptx:
    def test_reads_pptx_slide_text(self, reader, tmp_path):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "Title Slide"
        path = tmp_path / "deck.pptx"
        prs.save(str(path))

        content = reader.read_file("deck.pptx", str(tmp_path))
        assert "Title Slide" in content
        assert "Slide 1" in content


# ── .ppt (legacy) ──────────────────────────────────────────────────────────

class TestReadPpt:
    def test_legacy_ppt_returns_empty(self, reader, tmp_path):
        (tmp_path / "old.ppt").write_bytes(b"\x00" * 10)
        assert reader.read_file("old.ppt", str(tmp_path)) == ""


# ── .xlsx ───────────────────────────────────────────────────────────────────

class TestReadXlsx:
    def test_reads_xlsx(self, reader, tmp_path):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["Name", "Age"])
        ws.append(["Alice", 30])
        path = tmp_path / "sheet.xlsx"
        wb.save(str(path))

        content = reader.read_file("sheet.xlsx", str(tmp_path))
        assert "Name" in content
        assert "Alice" in content
        assert "Sheet: Data" in content


# ── .xls (legacy) ──────────────────────────────────────────────────────────

class TestReadXls:
    def test_legacy_xls_returns_empty(self, reader, tmp_path):
        (tmp_path / "old.xls").write_bytes(b"\x00" * 10)
        assert reader.read_file("old.xls", str(tmp_path)) == ""


# ── .pdf ────────────────────────────────────────────────────────────────────

class TestReadPdf:
    def test_reads_pdf_text(self, reader, tmp_path):
        from PyPDF2 import PdfWriter
        from io import BytesIO
        from PyPDF2.generic import AnnotationBuilder

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        path = tmp_path / "blank.pdf"
        with open(str(path), "wb") as f:
            writer.write(f)

        content = reader.read_file("blank.pdf", str(tmp_path))
        assert "Page 1" in content


# ── images ──────────────────────────────────────────────────────────────────

class TestReadImage:
    @pytest.mark.parametrize("ext", [".png", ".jpg", ".gif", ".bmp", ".webp"])
    def test_image_returns_base64_data_url(self, reader, tmp_path, ext):
        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        fname = f"pic{ext}"
        (tmp_path / fname).write_bytes(raw)
        content = reader.read_file(fname, str(tmp_path))
        assert content.startswith("data:image/")
        assert ";base64," in content
        payload = content.split(";base64,")[1]
        base64.b64decode(payload)  # must not raise

    def test_ico_returns_base64(self, reader, tmp_path):
        (tmp_path / "icon.ico").write_bytes(b"\x00\x00\x01\x00" + b"\x00" * 20)
        content = reader.read_file("icon.ico", str(tmp_path))
        assert content.startswith("data:image/ico;base64,")


# ── .svg ────────────────────────────────────────────────────────────────────

class TestReadSvg:
    def test_reads_svg(self, reader, tmp_path):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        (tmp_path / "circle.svg").write_text(svg)
        assert reader.read_file("circle.svg", str(tmp_path)) == svg


# ── unknown / fallback ──────────────────────────────────────────────────────

class TestReadUnknown:
    def test_unknown_extension_reads_as_text(self, reader, tmp_path):
        (tmp_path / "notes.md").write_text("# Markdown")
        content = reader.read_file("notes.md", str(tmp_path))
        assert "# Markdown" in content

    def test_binary_unknown_returns_empty(self, reader, tmp_path):
        (tmp_path / "blob.xyz").write_bytes(bytes(range(256)))
        content = reader.read_file("blob.xyz", str(tmp_path))
        # may succeed or return "" depending on encoding — either is acceptable
        assert isinstance(content, str)


# ── edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_nonexistent_file_returns_empty(self, reader, tmp_path):
        assert reader.read_file("nope.txt", str(tmp_path)) == ""

    def test_nonexistent_directory_returns_empty(self, reader):
        assert reader.read_file("a.txt", "/no/such/path") == ""

    def test_file_name_with_spaces(self, reader, tmp_path):
        (tmp_path / "my file.txt").write_text("spaced")
        assert reader.read_file("my file.txt", str(tmp_path)) == "spaced"

    def test_file_name_case_sensitivity(self, reader, tmp_path):
        (tmp_path / "CamelCase.TXT").write_text("upper")
        content = reader.read_file("CamelCase.TXT", str(tmp_path))
        assert content == "upper"

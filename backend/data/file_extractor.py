"""
Unified multi-format text extractor for Project Sentinel.

Dispatches by file extension to format-specific extractors.
All extractors raise ValueError on invalid / unreadable input.
"""
import io
import os
import re
from pathlib import Path

# Point pytesseract at the Windows installer path if not already on PATH.
_TESSERACT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.exists(_TESSERACT_WIN):
    try:
        import pytesseract as _pt
        _pt.pytesseract.tesseract_cmd = _TESSERACT_WIN
    except ImportError:
        pass


def extract_text(filename: str, content: bytes) -> str:
    """Extract plain text from file bytes based on the file extension."""
    ext = Path(filename.lower()).suffix
    if ext == ".pdf":
        return _from_pdf(content)
    elif ext == ".docx":
        return _from_docx(content)
    elif ext in (".xlsx", ".xls"):
        return _from_excel(content)
    elif ext == ".pptx":
        return _from_pptx(content)
    elif ext in (".html", ".htm"):
        return _from_html(content)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        return _ocr_image(content)
    else:
        return _from_text(content)


# ---------------------------------------------------------------------------
# Format-specific extractors (private)
# ---------------------------------------------------------------------------

def _from_pdf(content: bytes) -> str:
    from data.pdf_extractor import extract_text_from_pdf
    return extract_text_from_pdf(content)


def _from_docx(content: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"not a valid DOCX: {exc}") from exc

    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)

    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("DOCX contains no extractable text")
    return text.strip()


def _from_excel(content: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"not a valid XLSX: {exc}") from exc

    parts = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            row_text = " | ".join(str(v) for v in row if v is not None and str(v).strip())
            if row_text:
                parts.append(row_text)
    wb.close()

    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("Excel file contains no extractable text")
    return text.strip()


def _from_pptx(content: bytes) -> str:
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(content))
    except Exception as exc:
        raise ValueError(f"not a valid PPTX: {exc}") from exc

    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        parts.append(text)

    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("PPTX contains no extractable text")
    return text.strip()


def _from_html(content: bytes) -> str:
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts: list[str] = []
            self._skip_tags = {"script", "style", "head"}
            self._skip_depth = 0

        def handle_starttag(self, tag, attrs):
            if tag in self._skip_tags:
                self._skip_depth += 1

        def handle_endtag(self, tag):
            if tag in self._skip_tags:
                self._skip_depth = max(0, self._skip_depth - 1)

        def handle_data(self, data):
            if not self._skip_depth and data.strip():
                self._parts.append(data.strip())

        def get_text(self) -> str:
            return "\n".join(self._parts)

    html_text = content.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(html_text)
    text = re.sub(r"\n{3,}", "\n\n", parser.get_text())
    return text.strip()


def _ocr_image(content: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(content))
    except ImportError as exc:
        raise ValueError(
            "OCR not available: install Pillow and pytesseract, and ensure Tesseract is installed."
        ) from exc
    except Exception as exc:
        raise ValueError(f"not a valid image: {exc}") from exc

    try:
        text = pytesseract.image_to_string(img)
    except Exception as exc:
        raise ValueError(f"OCR failed: {exc}") from exc

    return text.strip()


def _from_text(content: bytes) -> str:
    try:
        return content.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ValueError(
            "File must be a PDF, DOCX, XLSX, PPTX, HTML, image, or UTF-8 encoded text."
        )

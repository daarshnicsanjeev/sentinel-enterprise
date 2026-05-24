"""
PDF text extractor with hybrid digital/OCR support.

Strategy per page:
  1. Extract embedded text with PyMuPDF (fast, no dependencies).
  2. If a page yields fewer than _OCR_THRESHOLD characters it is treated as
     a scanned image page — render it at 2x DPI and run Tesseract OCR.

This handles:
  - Pure digital PDFs     -> direct text extraction, no OCR cost
  - Pure scanned PDFs     -> OCR every page
  - Mixed PDFs            -> per-page decision
"""
import io
import os
import re

_OCR_THRESHOLD = 50  # chars below which a page is treated as scanned

# Point pytesseract at the Windows installer path if not already on PATH.
_TESSERACT_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.exists(_TESSERACT_WIN):
    try:
        import pytesseract as _pt
        _pt.pytesseract.tesseract_cmd = _TESSERACT_WIN
    except ImportError:
        pass


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes (digital or scanned).

    Raises ValueError if the bytes are not a valid PDF.
    Raises ValueError if a scanned page is encountered but Tesseract is absent.
    """
    if not pdf_bytes or not pdf_bytes.lstrip().startswith(b"%PDF-"):
        raise ValueError("not a valid PDF: missing %PDF- header")

    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"not a valid PDF: {exc}") from exc

    try:
        page_texts: list[str] = []
        for page in doc:
            text = page.get_text().strip()
            if len(text) < _OCR_THRESHOLD:
                # Sparse or empty page — likely scanned; render and OCR
                mat = fitz.Matrix(2, 2)  # 2x zoom for sharper OCR input
                pix = page.get_pixmap(matrix=mat)
                text = _ocr_page_image(pix)
            page_texts.append(text)
    finally:
        doc.close()

    combined = "\n\n".join(t for t in page_texts if t.strip())
    combined = re.sub(r"\n{3,}", "\n\n", combined)
    return combined.strip()


def _ocr_page_image(pix) -> str:
    """Run Tesseract OCR on a PyMuPDF Pixmap. Raises ValueError if Tesseract is absent."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "OCR required but pytesseract/Pillow is not installed."
        ) from exc

    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    try:
        return pytesseract.image_to_string(img).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "OCR required but Tesseract is not installed or not in PATH. "
            "Download from https://github.com/UB-Mannheim/tesseract/wiki"
        ) from exc
    except Exception as exc:
        raise ValueError(f"OCR failed: {exc}") from exc
    finally:
        img.close()

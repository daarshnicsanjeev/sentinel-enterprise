"""
Unit tests for data/pdf_extractor.py — TDD RED first.

Spec:
- extract_text_from_pdf(bytes) -> str
- Returns non-empty string for valid PDF bytes
- Raises ValueError for non-PDF bytes
- Raises ValueError for encrypted/password-protected PDFs
- Strips excessive whitespace from output
- Preserves meaningful newlines between paragraphs
"""
import io
import pytest


# ---------------------------------------------------------------------------
# Minimal valid PDF bytes (hand-crafted, no external lib needed for test data)
# ---------------------------------------------------------------------------

def _make_minimal_pdf(text: str = "This is a test document with sufficient digital text content for extraction.") -> bytes:
    """Build a minimal valid single-page PDF using PyMuPDF (guarantees proper text embedding)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 720), text)
    return doc.tobytes()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractTextFromPdf:
    def test_returns_string(self):
        from data.pdf_extractor import extract_text_from_pdf
        result = extract_text_from_pdf(_make_minimal_pdf())
        assert isinstance(result, str)

    def test_non_empty_for_valid_pdf(self):
        from data.pdf_extractor import extract_text_from_pdf
        result = extract_text_from_pdf(_make_minimal_pdf("Test content here — enough text to exceed the OCR threshold."))
        assert len(result.strip()) > 0

    def test_raises_value_error_for_non_pdf_bytes(self):
        from data.pdf_extractor import extract_text_from_pdf
        with pytest.raises(ValueError, match="not a valid PDF"):
            extract_text_from_pdf(b"this is not a pdf file at all")

    def test_raises_value_error_for_empty_bytes(self):
        from data.pdf_extractor import extract_text_from_pdf
        with pytest.raises(ValueError, match="not a valid PDF"):
            extract_text_from_pdf(b"")

    def test_strips_leading_trailing_whitespace(self):
        from data.pdf_extractor import extract_text_from_pdf
        result = extract_text_from_pdf(_make_minimal_pdf("  padded text with enough characters to clear the OCR threshold check here  "))
        assert result == result.strip()

    def test_accepts_bytes_input(self):
        from data.pdf_extractor import extract_text_from_pdf
        pdf_bytes = _make_minimal_pdf()
        assert isinstance(pdf_bytes, bytes)
        result = extract_text_from_pdf(pdf_bytes)
        assert isinstance(result, str)

    def test_pdf_magic_bytes_required(self):
        from data.pdf_extractor import extract_text_from_pdf
        # Valid-looking bytes but no %PDF- header
        with pytest.raises(ValueError, match="not a valid PDF"):
            extract_text_from_pdf(b"\x00\x01\x02\x03" * 100)


# ---------------------------------------------------------------------------
# Scanned PDF (image-only pages) — hybrid OCR extraction
# ---------------------------------------------------------------------------

def _make_scanned_pdf() -> bytes:
    """Build a PDF whose single page contains a raster image but NO text layer."""
    import fitz
    from PIL import Image, ImageDraw
    import io as _io

    # Draw white page with text as pixels (simulates a scanner output)
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 80), "Force majeure clause scanned page", fill="black")
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=612, height=200)
    page.insert_image(page.rect, stream=img_bytes)
    return doc.tobytes()


class TestScannedPdfExtraction:
    def test_scanned_pdf_does_not_return_empty(self, monkeypatch):
        """Scanned PDF must produce text via OCR, not empty string."""
        import data.pdf_extractor as mod
        monkeypatch.setattr(mod, "_ocr_page_image", lambda pix: "Force majeure clause scanned page")
        result = mod.extract_text_from_pdf(_make_scanned_pdf())
        assert result.strip() != ""

    def test_scanned_pdf_ocr_text_returned(self, monkeypatch):
        import data.pdf_extractor as mod
        monkeypatch.setattr(mod, "_ocr_page_image", lambda pix: "Governing law clause found")
        result = mod.extract_text_from_pdf(_make_scanned_pdf())
        assert "Governing law clause found" in result

    def test_digital_pdf_skips_ocr(self, monkeypatch):
        """A digital PDF with embedded text must never call OCR."""
        import data.pdf_extractor as mod
        ocr_called = []
        monkeypatch.setattr(mod, "_ocr_page_image", lambda pix: ocr_called.append(1) or "should not appear")
        mod.extract_text_from_pdf(_make_minimal_pdf("Direct embedded text content here — sufficient chars to exceed the OCR threshold check."))
        assert len(ocr_called) == 0

    def test_mixed_pdf_combines_digital_and_ocr_text(self, monkeypatch):
        """PDF with both digital and scanned pages returns combined text."""
        import fitz, io as _io
        from PIL import Image, ImageDraw
        import data.pdf_extractor as mod

        monkeypatch.setattr(mod, "_ocr_page_image", lambda pix: "OCR page content")

        # Build a 2-page PDF: page 1 has embedded text, page 2 is image-only
        img = Image.new("RGB", (612, 100), color="white")
        ImageDraw.Draw(img).text((10, 40), "scan", fill="black")
        buf = _io.BytesIO()
        img.save(buf, format="PNG")

        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((72, 720), "Digital text page one " * 5)  # enough chars to skip OCR
        p2 = doc.new_page()
        p2.insert_image(p2.rect, stream=buf.getvalue())
        pdf_bytes = doc.tobytes()

        result = mod.extract_text_from_pdf(pdf_bytes)
        assert "Digital text page one" in result
        assert "OCR page content" in result

    def test_tesseract_not_found_raises_value_error(self, monkeypatch):
        """If Tesseract is missing, raise a clear ValueError instead of crashing."""
        import data.pdf_extractor as mod

        def _raise(pix):
            raise ValueError("OCR required but Tesseract is not installed or not in PATH.")

        monkeypatch.setattr(mod, "_ocr_page_image", _raise)
        with pytest.raises(ValueError, match="Tesseract"):
            mod.extract_text_from_pdf(_make_scanned_pdf())

"""
TDD security tests for file upload validation (Phase 9 hardening).
Covers gaps not addressed by existing test_batch.py / test_file_extractor.py.

Run: pytest tests/unit/test_file_security.py -v
"""
import io
import struct
import zipfile
import pytest



def make_zip(*files: tuple[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. ZIP bomb — outer batch ZIP total uncompressed size
# ---------------------------------------------------------------------------

class TestZipBomb:
    def test_zip_bomb_rejected_when_uncompressed_exceeds_limit(self, client):
        """Batch ZIP whose total uncompressed bytes exceed the limit must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write two entries whose declared file_size sums past the limit.
            # We manipulate the ZipInfo directly so no actual RAM is needed.
            for i in range(2):
                info = zipfile.ZipInfo(f"doc{i}.txt")
                # Actual small content — we patch file_size after writing
                zf.writestr(info, b"x" * 10)
        # Re-open and patch the central-directory file_size fields
        # Instead: write a real small compressed file but forge ZipInfo.file_size
        # via a second approach — craft a proper zip with large declared sizes.
        # Simplest reliable approach: write content that decompresses to > limit.
        # We write one file with ~201 MB of zeros (compresses well).
        buf2 = io.BytesIO()
        with zipfile.ZipFile(buf2, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.txt", b"\x00" * (201 * 1024 * 1024))
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("bomb.zip", buf2.getvalue(), "application/zip")},
        )
        assert resp.status_code in (413, 422)

    def test_small_zip_accepted(self, client):
        """A small legitimate ZIP must not be rejected by the bomb check."""
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("ok.zip", make_zip(("doc.txt", b"Normal document content.")), "application/zip")},
        )
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# 2. ZIP slip — additional traversal vectors
# ---------------------------------------------------------------------------

class TestZipSlipComplete:
    def test_null_byte_in_filename_rejected(self, client):
        """ZIP entry with null byte in filename must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("safe\x00.txt")
            zf.writestr(info, b"content")
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("null.zip", buf.getvalue(), "application/zip")},
        )
        assert resp.status_code == 422

    def test_windows_drive_letter_path_rejected(self, client):
        """ZIP entry like 'C:\\file.txt' must be rejected as an unsafe absolute path."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("C:\\file.txt")
            zf.writestr(info, b"evil content")
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("win.zip", buf.getvalue(), "application/zip")},
        )
        assert resp.status_code == 422

    def test_symlink_entry_rejected(self, client):
        """ZIP entry encoded as a Unix symlink must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("link.txt")
            # Unix symlink mode: S_IFLNK = 0o120000; mode 0o120755
            info.external_attr = (0o120755 << 16)
            zf.writestr(info, b"/etc/passwd")
        resp = client.post(
            "/api/analyze/batch",
            files={"file": ("sym.zip", buf.getvalue(), "application/zip")},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Single-file upload — extension allowlist
# ---------------------------------------------------------------------------

class TestSingleFileExtensionAllowlist:
    def _post_file(self, client, filename: str, content: bytes, ctype: str = "application/octet-stream"):
        return client.post(
            "/api/analyze",
            files={"file": (filename, content, ctype)},
        )

    def test_rejects_exe_file(self, client):
        resp = self._post_file(client, "malware.exe", b"MZ\x90\x00")
        assert resp.status_code == 400

    def test_rejects_shell_script(self, client):
        resp = self._post_file(client, "exploit.sh", b"#!/bin/bash\nrm -rf /")
        assert resp.status_code == 400

    def test_rejects_python_script(self, client):
        resp = self._post_file(client, "payload.py", b"import os; os.system('whoami')")
        assert resp.status_code == 400

    def test_rejects_batch_file(self, client):
        resp = self._post_file(client, "run.bat", b"@echo off\ndel /Q /F /S C:\\")
        assert resp.status_code == 400

    def test_rejects_javascript_file(self, client):
        resp = self._post_file(client, "attack.js", b"fetch('http://evil.com')")
        assert resp.status_code == 400

    def test_accepts_txt_file(self, client):
        # txt should still work (pipeline runs, may complete or error on LLM)
        resp = self._post_file(client, "contract.txt", b"This is a valid contract text for compliance review.")
        # Accepts the file (may return 200 stream or 400 if LLM unavailable)
        assert resp.status_code != 400 or "extension" not in resp.text.lower()

    def test_accepts_pdf_magic(self, client):
        # A well-formed PDF header should pass extension check
        # (Will fail deeper in the pipeline, but not at extension validation)
        resp = self._post_file(client, "doc.pdf", b"%PDF-1.4 fake", "application/pdf")
        assert resp.status_code != 400 or "extension" not in resp.text.lower()


# ---------------------------------------------------------------------------
# 4. Image magic byte validation
# ---------------------------------------------------------------------------

class TestImageMagicBytes:
    def test_png_magic_required(self):
        """A file with .png extension but wrong magic bytes must be rejected."""
        from data.file_extractor import extract_text
        not_png = b"This is not a PNG file at all\x00\x01\x02"
        with pytest.raises(ValueError, match="(?i)magic|valid|image|PNG"):
            extract_text("scan.png", not_png)

    def test_jpeg_magic_required(self):
        """A file with .jpg extension but wrong magic bytes must be rejected."""
        from data.file_extractor import extract_text
        not_jpg = b"GIF89a fake gif data not jpeg"
        with pytest.raises(ValueError, match="(?i)magic|valid|image|JPEG|JPG"):
            extract_text("photo.jpg", not_jpg)

    def test_tiff_magic_required(self):
        """A file with .tiff extension but wrong magic bytes must be rejected."""
        from data.file_extractor import extract_text
        not_tiff = b"Not a TIFF file at all here"
        with pytest.raises(ValueError, match="(?i)magic|valid|image|TIFF"):
            extract_text("scan.tiff", not_tiff)

    def test_valid_png_magic_passes_check(self):
        """Correct PNG magic bytes should not raise a magic-byte error."""
        from data.file_extractor import extract_text
        # PNG magic: \x89PNG\r\n\x1a\n followed by garbage (will fail OCR but not magic)
        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        with pytest.raises(ValueError) as exc_info:
            extract_text("img.png", png_magic)
        # Should NOT be a magic byte error — the error comes from PIL/tesseract
        assert "magic" not in str(exc_info.value).lower()

    def test_valid_jpeg_magic_passes_check(self):
        """Correct JPEG magic bytes should not raise a magic-byte error."""
        from data.file_extractor import extract_text
        jpeg_magic = b"\xff\xd8\xff" + b"\x00" * 20
        with pytest.raises(ValueError) as exc_info:
            extract_text("photo.jpg", jpeg_magic)
        assert "magic" not in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 5. Image pixel bomb
# ---------------------------------------------------------------------------

class TestImagePixelBomb:
    def test_decompression_bomb_raises_value_error(self, monkeypatch):
        """PIL DecompressionBombError must be caught and re-raised as ValueError."""
        from PIL import Image
        import data.file_extractor as fe

        # Monkeypatch Image.open to raise DecompressionBombError
        def _bomb(*args, **kwargs):
            raise Image.DecompressionBombError("Image size exceeds limit")

        monkeypatch.setattr(Image, "open", _bomb)
        # Valid JPEG magic so it passes the magic check
        jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 20
        with pytest.raises(ValueError, match="(?i)bomb|size|limit|image"):
            fe._ocr_image(jpeg_bytes)

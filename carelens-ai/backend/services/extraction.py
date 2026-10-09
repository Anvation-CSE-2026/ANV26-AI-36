"""Text extraction from uploaded documents (PDF text layer, OCR for images/scans).

Every optional dependency is detected at run time. When one is missing the
caller gets ExtractionUnavailable with a user-safe message; the upload itself
is never lost.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path


MAX_PDF_PAGES = 150          # a medical report is never longer; stops a crafted file from tying the machine up
MAX_IMAGE_PIXELS = 60_000_000  # refuse "decompression bombs" (tiny files that unpack to enormous images)


class ExtractionUnavailable(Exception):
    """A needed component (e.g. OCR engine) isn't installed on this machine."""


class ExtractionFailed(Exception):
    """The file was readable but no usable text could be produced."""


def capabilities():
    try:
        import pypdf  # noqa: F401
        pdf = True
    except ImportError:
        pdf = False
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        ocr = True
    except Exception:
        ocr = False
    return {"pdf_text": pdf, "ocr": ocr, "pdf_ocr": ocr and bool(shutil.which("pdftoppm"))}


def _ocr_image(img):
    import pytesseract
    try:
        return pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractionUnavailable("Text recognition isn't set up on this device.") from exc


def _pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionUnavailable("PDF reading isn't set up on this device.") from exc
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ExtractionFailed("This PDF is password protected.")
        return "\f".join((page.extract_text() or "") for page in list(reader.pages)[:MAX_PDF_PAGES])  # \f marks a page break
    except ExtractionFailed:
        raise
    except Exception as exc:
        raise ExtractionFailed("This PDF couldn't be read.") from exc


def _pdf_ocr(path, max_pages=8):
    if not capabilities()["pdf_ocr"]:
        raise ExtractionUnavailable("This looks like a scanned PDF, and text recognition for scans isn't set up on this device.")
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "200", "-l", str(max_pages), "-png", str(path), f"{tmp}/p"],
                       check=True, capture_output=True, timeout=120)
        return "\f".join(_ocr_image(Image.open(f)) for f in sorted(Path(tmp).glob("p*.png")))


def extract_text(path, mime):
    """Return (text, method)."""
    if mime == "application/pdf":
        text = _pdf_text(path)
        if len(text.strip()) >= 30:
            return text.strip(), "pdf-text"
        text = _pdf_ocr(path)
        method = "pdf-ocr"
    else:
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
            img = Image.open(path)
            img.load()
        except ImportError as exc:
            raise ExtractionUnavailable("Image reading isn't set up on this device.") from exc
        except Exception as exc:
            raise ExtractionFailed("This image couldn't be read.") from exc
        text = _ocr_image(img)
        method = "image-ocr"
    if len(text.strip()) < 10:
        raise ExtractionFailed("No readable text was found in this document.")
    return text.strip(), method

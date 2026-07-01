"""Extract plain text from a PDF or DOCX byte stream — with OCR fallback.

Reused from the toeic_app extraction-service (the OCR path is what makes OCR a
Phase-1 MUST-have feasible here). PDFs may be born-digital (real text layer) or
scanned images. We read the text layer with pdfplumber and, for any page that
comes back essentially empty, fall back to OCR (PyMuPDF renders the page ->
Tesseract recognises it). Pages are joined with form-feed (\\f) so the chunker
can attribute concepts back to a page.

`classify_pdf` implements the PRD's type-detection (FR-0.2): digital / scanned /
hybrid, from the text-layer coverage ratio.
"""
import io

from app.observability import audit

# A page with fewer than this many characters of real text is treated as a
# scanned image and sent to OCR.
_PAGE_TEXT_MIN_CHARS = 20
_OCR_DPI = 300
# LSTM engine, automatic page segmentation (handles multi-column layouts).
_OCR_CONFIG = "--oem 1 --psm 3 -c preserve_interword_spaces=1"

PAGE_MARKER = "\f"  # form feed — page boundary


def classify_pdf(data: bytes) -> tuple[str, float]:
    """Return (label, digital_page_fraction) where label is digital/scanned/hybrid.

    Cheap heuristic (PRD FR-0.2): a page "has a text layer" if its extracted text
    exceeds _PAGE_TEXT_MIN_CHARS. >=85% digital -> digital, <=15% -> scanned, else
    hybrid."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = len(pdf.pages)
        if pages == 0:
            return "empty", 0.0
        digital = sum(
            1 for p in pdf.pages if len((p.extract_text() or "").strip()) >= _PAGE_TEXT_MIN_CHARS
        )
    frac = digital / pages
    label = "digital" if frac >= 0.85 else ("scanned" if frac <= 0.15 else "hybrid")
    return label, frac


def extract_text(data: bytes, mime: str) -> str:
    if mime == "application/pdf":
        return _from_pdf(data)
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _from_docx(data)
    raise ValueError(f"unsupported mime: {mime}")


def _from_pdf(data: bytes) -> str:
    import pdfplumber

    parts: list[str] = []
    ocr_pages: list[int] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text() or ""
            parts.append(txt)
            if len(txt.strip()) < _PAGE_TEXT_MIN_CHARS:
                ocr_pages.append(i)

    if ocr_pages:
        recognised = _ocr_pdf_pages(data, ocr_pages)
        for i, txt in recognised.items():
            if len(txt.strip()) > len(parts[i].strip()):
                parts[i] = txt

    return PAGE_MARKER.join(parts)


def _ocr_pdf_pages(data: bytes, pages: list[int]) -> dict[int, str]:
    """Render the given page indices and OCR them. Best-effort: if the OCR stack
    is unavailable or a page fails, skip it and let downstream guardrails decide."""
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
    except Exception as e:  # pragma: no cover - import/runtime env issue
        audit("OCR_UNAVAILABLE", error=str(e))
        return {}

    audit("OCR_FALLBACK", pages=len(pages), dpi=_OCR_DPI)
    out: dict[int, str] = {}
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i in pages:
            try:
                pix = doc[i].get_pixmap(dpi=_OCR_DPI)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                out[i] = pytesseract.image_to_string(img, config=_OCR_CONFIG)
            except Exception as e:
                audit("OCR_PAGE_FAILED", page=i, error=str(e))
    return out


def _from_docx(data: bytes) -> str:
    import docx  # python-docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)

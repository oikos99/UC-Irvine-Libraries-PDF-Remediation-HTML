from __future__ import annotations

from typing import List

import fitz  # PyMuPDF


def render_pdf_pages(pdf_bytes: bytes, dpi: int = 180) -> List[dict]:
    """Render PDF pages into in-memory PNG images for side-by-side review."""
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_meta: List[dict] = []
    try:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            page_meta.append(
                {
                    "page_number": page_number,
                    "image_bytes": pixmap.tobytes("png"),
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                }
            )
    finally:
        document.close()
    return page_meta

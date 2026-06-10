from __future__ import annotations

import base64
from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).parent / "components" / "zoomable_pdf_panel"
_component = components.declare_component("zoomable_pdf_panel", path=str(_COMPONENT_PATH))


def zoomable_pdf_panel(
    *,
    image_bytes: bytes,
    page_number: int,
    height: int = 650,
    key: str,
) -> None:
    """Render an original PDF-page screenshot in an accessible zoomable panel."""
    image_data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    _component(
        image_data_url=image_data_url,
        page_number=page_number,
        height=height,
        default=None,
        key=key,
    )

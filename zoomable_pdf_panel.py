from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).parent / "components" / "zoomable_pdf_panel"
_COMPONENT_AVAILABLE = _COMPONENT_PATH.is_dir() and (_COMPONENT_PATH / "index.html").is_file()
_component = (
    components.declare_component("zoomable_pdf_panel", path=str(_COMPONENT_PATH))
    if _COMPONENT_AVAILABLE
    else None
)


def zoomable_pdf_panel(
    *,
    image_bytes: bytes,
    page_number: int,
    height: int = 650,
    key: str,
) -> None:
    """Render an original PDF-page screenshot in a zoomable panel, with a safe static fallback."""
    if _component is None:
        st.warning(
            "Zoomable PDF panel component files were not found. "
            "Using a static image fallback. Add components/zoomable_pdf_panel/index.html "
            "to the deployed repository to restore zoom controls."
        )
        st.image(image_bytes, caption=None, use_container_width=True)
        return

    image_data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    _component(
        image_data_url=image_data_url,
        page_number=page_number,
        height=height,
        default=None,
        key=key,
    )

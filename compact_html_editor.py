from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).parent / "components" / "compact_html_editor"
_COMPONENT_AVAILABLE = _COMPONENT_PATH.is_dir() and (_COMPONENT_PATH / "index.html").is_file()
_component = (
    components.declare_component("compact_html_editor_buffered_v3", path=str(_COMPONENT_PATH))
    if _COMPONENT_AVAILABLE
    else None
)


def compact_html_editor(
    *,
    value: str,
    tokens: list[dict[str, Any]],
    preview_styles: str,
    height: int = 650,
    key: str,
) -> str:
    """Render the custom compact-token HTML editor, with a safe text-area fallback."""
    if _component is None:
        st.warning(
            "Compact HTML editor component files were not found. "
            "Using the plain HTML editor fallback. Add components/compact_html_editor/index.html "
            "to the deployed repository to restore inline image pills and rendered page previews."
        )
        return st.text_area(
            "Edit HTML source",
            value=value,
            height=height,
            key=f"{key}_fallback_textarea",
            help="Embedded images remain protected as compact placeholder tokens in this fallback editor.",
        )

    result = _component(
        value=value,
        tokens=tokens,
        preview_styles=preview_styles,
        height=height,
        editor_id=key,
        default=value,
        key=key,
    )
    return result if isinstance(result, str) else value

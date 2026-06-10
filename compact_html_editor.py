from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).parent / "components" / "compact_html_editor"
_component = components.declare_component("compact_html_editor", path=str(_COMPONENT_PATH))


def compact_html_editor(
    *,
    value: str,
    tokens: list[dict[str, Any]],
    preview_styles: str,
    height: int = 650,
    key: str,
) -> str:
    """Render a source editor whose embedded Base64 placeholders appear as compact pills."""
    result = _component(
        value=value,
        tokens=tokens,
        preview_styles=preview_styles,
        height=height,
        default=value,
        key=key,
    )
    return result if isinstance(result, str) else value

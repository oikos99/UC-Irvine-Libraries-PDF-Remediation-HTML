from __future__ import annotations

import base64
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup, Tag


PAGE_SELECTOR = '[id^="page-"]'
HEADING_NAMES = ["h1", "h2", "h3", "h4", "h5", "h6"]
TOKEN_PREFIX_IMAGE = "EMBEDDED_IMAGE"
TOKEN_PREFIX_ASSET = "EMBEDDED_ASSET"
TOKEN_RE = re.compile(r"\{\{(?:EMBEDDED_IMAGE|EMBEDDED_ASSET)_\d{4}\}\}")
DATA_URI_RE = re.compile(
    r"data:(?P<mime>[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+)"
    r"(?P<params>(?:;[A-Za-z0-9!#$&^_.+\-=]+)*)"
    r";base64,(?P<payload>[A-Za-z0-9+/=\r\n]+)",
    re.IGNORECASE,
)


@dataclass
class PageFragment:
    page_number: int
    element_id: str
    html: str
    label: str
    was_added_as_fallback: bool = False


def decode_html_bytes(html_bytes: bytes) -> str:
    """Decode generated HTML while tolerating a non-UTF-8 fallback."""
    try:
        return html_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return html_bytes.decode("utf-8", errors="replace")


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _asset_label(index: int, mime_type: str, size_bytes: int) -> str:
    subtype = mime_type.split("/", 1)[-1].upper().replace("+XML", "")
    if mime_type.lower().startswith("image/"):
        return f"🖼 Image {index} · {subtype} · {_format_bytes(size_bytes)}"
    return f"📎 Asset {index} · {subtype} · {_format_bytes(size_bytes)}"


def tokenize_embedded_assets(html_text: str) -> Tuple[str, Dict[str, dict]]:
    """Replace long Base64 data URIs with stable short tokens for the review editor."""
    assets: Dict[str, dict] = {}
    token_by_uri: Dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        data_uri = match.group(0)
        if data_uri in token_by_uri:
            return token_by_uri[data_uri]

        mime_type = match.group("mime").lower()
        payload = re.sub(r"\s+", "", match.group("payload"))
        try:
            size_bytes = len(base64.b64decode(payload, validate=False))
        except Exception:
            size_bytes = 0

        index = len(assets) + 1
        prefix = TOKEN_PREFIX_IMAGE if mime_type.startswith("image/") else TOKEN_PREFIX_ASSET
        token = f"{{{{{prefix}_{index:04d}}}}}"
        assets[token] = {
            "token": token,
            "data_uri": data_uri,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "label": _asset_label(index, mime_type, size_bytes),
        }
        token_by_uri[data_uri] = token
        return token

    return DATA_URI_RE.sub(replace, html_text), assets


def restore_embedded_assets(html_text: str, embedded_assets: Dict[str, dict] | None) -> str:
    """Restore the original Base64 data URIs for rendered preview and final export."""
    restored = html_text
    for token, asset in (embedded_assets or {}).items():
        restored = restored.replace(token, str(asset.get("data_uri", "")))
    return restored


def embedded_assets_for_text(review_document: dict, html_text: str) -> List[dict]:
    """Return only the compact-token metadata needed by a specific editor instance."""
    registry = review_document.get("embedded_assets", {})
    tokens = set(TOKEN_RE.findall(html_text))
    return [registry[token] for token in registry if token in tokens]


def preview_style_html(review_document: dict) -> str:
    """Return the generated document's style tags with hidden assets restored."""
    soup = BeautifulSoup(review_document["original_html"], "html.parser")
    style_html = "".join(str(style) for style in soup.find_all("style"))
    return restore_embedded_assets(style_html, review_document.get("embedded_assets", {}))


def _safe_page_number(tag: Tag, fallback: int) -> int:
    for candidate in (
        tag.get("data-pdf-page-number", ""),
        tag.get("id", ""),
    ):
        match = re.search(r"(\d+)", str(candidate))
        if match:
            return int(match.group(1))
    return fallback


def _is_top_level_page(tag: Tag) -> bool:
    parent = tag.parent
    while isinstance(parent, Tag):
        parent_id = str(parent.get("id", ""))
        if parent_id.startswith("page-"):
            return False
        parent = parent.parent
    return True


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _first_sentence(value: str, max_len: int = 90) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    match = re.search(r"(.{20,}?[.!?])\s", text)
    if match:
        text = match.group(1)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def _is_bad_heading(value: str) -> bool:
    text = _clean_text(value).lower()
    if not text:
        return True
    return bool(re.fullmatch(r"(pdf\s+)?page\s*\d+", text) or re.fullmatch(r"\d+", text))


def page_display_label(page: Tag, page_number: int) -> str:
    printed_value = _clean_text(str(page.get("data-printed-page-number", "")))
    prefix = f"PDF page {page_number}"
    if printed_value:
        prefix += f" · printed page {printed_value}"

    for level in HEADING_NAMES:
        for heading in page.find_all(level):
            heading_text = _clean_text(heading.get_text(" ", strip=True))
            if not _is_bad_heading(heading_text):
                return f"{prefix} - {_first_sentence(heading_text)}"

    clone = BeautifulSoup(str(page), "html.parser")
    for marker in clone.select(".page-marker"):
        marker.decompose()
    text = _first_sentence(clone.get_text(" ", strip=True))
    return f"{prefix} - {text}" if text else prefix


def _new_page_placeholder(soup: BeautifulSoup, page_number: int) -> Tag:
    page = soup.new_tag("div", id=f"page-{page_number}")
    page["data-pdf-page-number"] = str(page_number)
    marker = soup.new_tag("p")
    marker["class"] = ["page-marker"]
    marker["role"] = "doc-pagebreak"
    marker["aria-label"] = f"PDF page {page_number}"
    marker["data-pdf-page-number"] = str(page_number)
    marker.string = f"PDF page {page_number}"
    page.append(marker)
    return page


def prepare_review_document(html_text: str, pdf_page_count: int) -> dict:
    """
    Parse the complete generated HTML and expose page-level fragments for review.

    The complete document remains authoritative. Long embedded Base64 data URIs are
    replaced with stable short tokens before fragments are sent to the visual editor.
    """
    tokenized_html, embedded_assets = tokenize_embedded_assets(html_text)
    soup = BeautifulSoup(tokenized_html, "html.parser")
    warnings: List[str] = []

    body = soup.body
    if body is None:
        html_tag = soup.find("html")
        if html_tag is None:
            html_tag = soup.new_tag("html")
            soup.append(html_tag)
        body = soup.new_tag("body")
        html_tag.append(body)
        warnings.append("The generated HTML did not include a body element. A body element was added for review.")

    all_candidates = [tag for tag in soup.select(PAGE_SELECTOR) if isinstance(tag, Tag)]
    pages = [tag for tag in all_candidates if _is_top_level_page(tag)]

    if not pages:
        warnings.append(
            "No page containers were detected in the generated HTML. Empty page containers were added so the document can still be reviewed."
        )

    existing_page_numbers = {_safe_page_number(tag, index) for index, tag in enumerate(pages, start=1)}
    fallback_ids = set()
    append_target = soup.find("main") or body

    for page_number in range(1, pdf_page_count + 1):
        if page_number not in existing_page_numbers:
            placeholder = _new_page_placeholder(soup, page_number)
            append_target.append(placeholder)
            pages.append(placeholder)
            fallback_ids.add(placeholder["id"])
            warnings.append(
                f"Generated HTML did not contain a container for PDF page {page_number}. A blank review container was appended."
            )

    pages = sorted(
        pages,
        key=lambda tag: (_safe_page_number(tag, 10**9), str(tag.get("id", ""))),
    )

    fragments: List[PageFragment] = []
    used_ids = set()
    for index, page in enumerate(pages, start=1):
        page_number = _safe_page_number(page, index)
        element_id = str(page.get("id", "")).strip() or f"page-{page_number}"
        if element_id in used_ids:
            replacement_id = f"{element_id}-review-{index}"
            warnings.append(f"Duplicate page container ID '{element_id}' was changed to '{replacement_id}' for review.")
            element_id = replacement_id
            page["id"] = element_id
        used_ids.add(element_id)
        fragments.append(
            PageFragment(
                page_number=page_number,
                element_id=element_id,
                html=str(page),
                label=page_display_label(page, page_number),
                was_added_as_fallback=element_id in fallback_ids,
            )
        )

    if len(fragments) != pdf_page_count:
        warnings.append(
            f"The PDF has {pdf_page_count} page(s), while the generated HTML exposes {len(fragments)} page container(s). Review the mapping carefully."
        )

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Accessible HTML Alternative"

    return {
        "original_html": str(soup),
        "document_title": title,
        "fragments": [asdict(fragment) for fragment in fragments],
        "embedded_assets": embedded_assets,
        "warnings": warnings,
    }


def _find_replacement_tag(fragment_html: str, expected_id: str) -> Tuple[Tag | None, List[str]]:
    warnings: List[str] = []
    fragment_soup = BeautifulSoup(fragment_html, "html.parser")
    replacement = fragment_soup.find(id=expected_id)
    if replacement is None:
        replacement = fragment_soup.find(True)
        if replacement is None:
            return None, [f"Page container #{expected_id} is empty and could not be merged."]
        warnings.append(
            f"Page container #{expected_id} no longer included its original ID. The ID was restored during export."
        )
    if not isinstance(replacement, Tag):
        return None, [f"Page container #{expected_id} could not be parsed during export."]
    replacement["id"] = expected_id
    return replacement, warnings


def _refresh_navigation_labels(soup: BeautifulSoup) -> None:
    nav = soup.find("nav", attrs={"aria-label": "Document pages"}) or soup.find(
        "nav", attrs={"role": "doc-pagelist"}
    )
    if nav is None:
        return
    nav["aria-label"] = "Document pages"
    nav["role"] = "doc-pagelist"
    ul = nav.find("ul")
    if ul is None:
        ul = soup.new_tag("ul")
        nav.append(ul)
    ul.clear()
    pages = [tag for tag in soup.select(PAGE_SELECTOR) if isinstance(tag, Tag) and _is_top_level_page(tag)]
    for index, page in enumerate(pages, start=1):
        element_id = str(page.get("id", "")).strip()
        if not element_id:
            continue
        page_number = _safe_page_number(page, index)
        li = soup.new_tag("li")
        link = soup.new_tag("a", href=f"#{element_id}")
        link.string = page_display_label(page, page_number)
        li.append(link)
        ul.append(li)


def _set_document_title(soup: BeautifulSoup, document_title: str) -> None:
    head = soup.head
    if head is None:
        html_tag = soup.find("html")
        if html_tag is None:
            html_tag = soup.new_tag("html")
            soup.insert(0, html_tag)
        head = soup.new_tag("head")
        html_tag.insert(0, head)
    title = head.find("title")
    if title is None:
        title = soup.new_tag("title")
        head.append(title)
    title.string = document_title.strip() or "Accessible HTML Alternative"


def _validate_asset_tokens(html_text: str, embedded_assets: Dict[str, dict]) -> List[str]:
    warnings: List[str] = []
    unknown = sorted(set(TOKEN_RE.findall(html_text)) - set(embedded_assets))
    if unknown:
        warnings.append("Unknown embedded-asset tokens remain: " + ", ".join(unknown[:10]))
    return warnings


def merge_reviewed_document(review_document: dict, edited_fragments: Dict[str, str], document_title: str) -> Tuple[str, List[str]]:
    """Merge edited page fragments and restore hidden Base64 assets for final download."""
    soup = BeautifulSoup(review_document["original_html"], "html.parser")
    warnings: List[str] = []

    for fragment in review_document["fragments"]:
        element_id = fragment["element_id"]
        current = soup.find(id=element_id)
        if current is None:
            warnings.append(f"Page container #{element_id} was not found in the complete HTML and was skipped.")
            continue
        replacement, replacement_warnings = _find_replacement_tag(
            edited_fragments.get(element_id, fragment["html"]),
            element_id,
        )
        warnings.extend(replacement_warnings)
        if replacement is not None:
            current.replace_with(replacement)

    _set_document_title(soup, document_title)
    _refresh_navigation_labels(soup)
    warnings.extend(validate_complete_html(soup))
    tokenized_html = str(soup)
    warnings.extend(_validate_asset_tokens(tokenized_html, review_document.get("embedded_assets", {})))
    return restore_embedded_assets(tokenized_html, review_document.get("embedded_assets", {})), warnings


def validate_complete_html(soup_or_html: BeautifulSoup | str) -> List[str]:
    soup = soup_or_html if isinstance(soup_or_html, BeautifulSoup) else BeautifulSoup(soup_or_html, "html.parser")
    warnings: List[str] = []

    ids = [str(tag.get("id")) for tag in soup.find_all(id=True)]
    duplicates = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
    if duplicates:
        warnings.append("Duplicate HTML IDs remain: " + ", ".join(duplicates[:10]))

    html_tag = soup.find("html")
    if html_tag is None or not html_tag.get("lang"):
        warnings.append("The complete HTML does not declare a document language on the html element.")

    if soup.find("title") is None or not soup.find("title").get_text(strip=True):
        warnings.append("The complete HTML does not include a non-empty browser title.")

    previous_level = None
    for heading in soup.find_all(HEADING_NAMES):
        level = int(heading.name[1])
        if previous_level is not None and level > previous_level + 1:
            warnings.append(
                f"Heading hierarchy skips from H{previous_level} to H{level} near: {_first_sentence(heading.get_text(' ', strip=True), 60)}"
            )
            break
        previous_level = level

    return warnings


def _safe_preview_fragment(fragment_html: str) -> str:
    soup = BeautifulSoup(fragment_html, "html.parser")
    for blocked in soup.find_all(["script", "iframe", "object", "embed", "base"]):
        blocked.decompose()
    for tag in soup.find_all(True):
        for attribute in list(tag.attrs):
            if attribute.lower().startswith("on"):
                del tag.attrs[attribute]
        for attribute in ("href", "src", "action"):
            value = str(tag.get(attribute, "")).strip().lower()
            if value.startswith("javascript:"):
                del tag.attrs[attribute]
    return str(soup)


def build_page_preview(review_document: dict, fragment_html: str) -> str:
    """Create an iframe-friendly preview document without active scripting."""
    restored_fragment = restore_embedded_assets(fragment_html, review_document.get("embedded_assets", {}))
    safe_fragment = _safe_preview_fragment(restored_fragment)
    style_html = preview_style_html(review_document)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{style_html}
<style>
body {{ padding: 1rem; font-family: Arial, sans-serif; line-height: 1.45; }}
img {{ max-width: 100%; height: auto; }}
table {{ max-width: 100%; border-collapse: collapse; }}
</style>
</head>
<body>
{safe_fragment}
</body>
</html>"""


def build_document_preview(reviewed_html: str) -> str:
    """Strip active content before rendering a complete-document preview."""
    return _safe_preview_fragment(reviewed_html)

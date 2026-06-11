from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Tuple

from bs4 import BeautifulSoup, Tag

from html_document import HEADING_NAMES, TOKEN_RE

OPENAI_DEFAULT_MODEL = "gpt-4.1"
OPENAI_API_URL = "https://api.openai.com/v1/responses"


class AICorrectionError(RuntimeError):
    """Raised when AI-assisted page correction fails or returns invalid output."""


def build_document_outline(review_document: dict, max_items: int = 30) -> list[str]:
    soup = BeautifulSoup(review_document.get("original_html", ""), "html.parser")
    outline: list[str] = []
    for heading in soup.find_all(HEADING_NAMES):
        text = heading.get_text(" ", strip=True)
        if not text:
            continue
        outline.append(f"{heading.name}: {text}")
        if len(outline) >= max_items:
            break
    return outline


def _response_text_from_json(response_json: dict) -> str:
    texts: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(str(content.get("text", "")))
    if texts:
        return "\n".join(texts).strip()
    # Some error conditions may still place text elsewhere.
    if isinstance(response_json.get("output_text"), str):
        return str(response_json["output_text"]).strip()
    raise AICorrectionError("OpenAI did not return readable text output.")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json|JSON)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _json_dumps_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def request_ai_page_correction(
    *,
    api_key: str,
    current_fragment_html: str,
    page_image_bytes: bytes,
    page_number: int,
    total_pages: int,
    document_title: str,
    document_outline: list[str],
    allowed_tokens: Iterable[str],
    model: str = OPENAI_DEFAULT_MODEL,
) -> dict:
    allowed_tokens = sorted(set(allowed_tokens))
    image_data_url = "data:image/png;base64," + base64.b64encode(page_image_bytes).decode("ascii")

    system_prompt = (
        "You are correcting one page of an HTML accessibility remediation output. "
        "Use the supplied page screenshot as the authoritative visual source of truth. Treat the supplied HTML page fragment as an editable draft, not as a complete transcription. "
        "Return a corrected HTML fragment for the same page, plus a concise inventory of visible text regions, a short summary of changes, and uncertainty notes.\n\n"
        "Improve OCR, paragraph boundaries, semantic structure, heading hierarchy, lists, tables, and accessible image alt text when supported by the screenshot.\n\n"
        "Completeness requirements:\n"
        "- Identify every visually meaningful text region in the screenshot, including headers, footers, marginal notes, captions, advertisements, envelope text, legends, labels, and body text.\n"
        "- Ensure that every meaningful visible text region is represented exactly once in the corrected HTML or in an appropriate text alternative.\n"
        "- Add text that is visibly present in the screenshot even when it is missing from the draft HTML.\n"
        "- Do not omit text merely because it appears decorative, secondary, handwritten, faint, or outside the main body area.\n"
        "- Do not invent text that cannot be reasonably read from the screenshot.\n"
        "- When text is uncertain, preserve the most likely transcription and describe the uncertainty in review_notes.\n\n"
        "Semantic HTML requirements:\n"
        "- Use headings only for genuine document sections. Do not mark visual emphasis, branding, identifiers, dates, or individual legend items as headings unless they introduce a section.\n"
        "- Use paragraph elements for prose.\n"
        "- Use ordered or unordered lists only for genuine lists.\n"
        "- Use definition lists for label-value metadata when appropriate.\n"
        "- Use tables only when the screenshot presents meaningful row-column relationships. Use caption, th, td, and scope where applicable. Do not use tables for visual layout.\n"
        "- Do not use br elements for spacing, layout, table rows, list items, or ordinary paragraph wrapping.\n"
        "- Use br only when a line break is genuinely part of the content, such as an address or a transcription whose lineation carries meaning.\n"
        "- Prefer semantic elements over generic div elements whenever the meaning is clear.\n\n"
        "Embedded-image requirements:\n"
        "- Preserve the existing outer page container and its id exactly.\n"
        "- Preserve every embedded-image src token exactly as provided.\n"
        "- Do not invent, delete, duplicate, rename, or modify embedded-image tokens.\n"
        "- Preserve each img element's existing class, style, width, height, data-bda-relative-width, and data-image-width-source attributes exactly. These values were calculated from the original PDF crop geometry.\n"
        "- Do not guess, enlarge, shrink, or restyle embedded-image dimensions. You may move an img element into a more appropriate semantic container such as figure, but its protected presentation attributes must remain unchanged.\n"
        "- You may edit alt attributes.\n"
        "- When important image text is transcribed as nearby HTML text, avoid repeating the full transcription unnecessarily in alt text.\n\n"
        "Safety requirements:\n"
        "- Return exactly one corrected page fragment.\n"
        "- Do not include a complete HTML document.\n"
        "- Do not include <html>, <head>, <body>, <style>, <script>, <iframe>, <object>, or <embed>.\n"
        "- Do not introduce external URLs.\n\n"
        "Before returning the corrected HTML:\n"
        "- Verify that no meaningful visible text region from the screenshot has been omitted.\n"
        "- Report uncertain readings and any intentionally excluded decorative content in review_notes and intentionally_excluded_regions.\n"
        "- Respond ONLY with valid JSON matching this shape:\n"
        "{\n"
        '  "corrected_page_html": "<section id=\\"page-3\\">...</section>",\n'
        '  "visible_text_regions": [{"region": "Telegram header", "status": "included", "notes": "Western Union branding and symbols legend"}],\n'
        '  "intentionally_excluded_regions": [{"region": "Decorative border", "reason": "No meaningful text content"}],\n'
        '  "changes_summary": ["..."],\n'
        '  "needs_human_review": true,\n'
        '  "review_notes": ["..."]\n'
        "}"
    )

    user_prompt = (
        f"DOCUMENT TITLE:\n{document_title or 'Accessible HTML Alternative'}\n\n"
        f"CURRENT PAGE:\n{page_number} of {total_pages}\n\n"
        "DOCUMENT OUTLINE:\n"
        + ("\n".join(f"- {item}" for item in document_outline) if document_outline else "- (No headings detected)")
        + "\n\nALLOWED EMBEDDED-IMAGE TOKENS:\n"
        + ("\n".join(allowed_tokens) if allowed_tokens else "(none)")
        + "\n\nCURRENT HTML PAGE FRAGMENT:\n"
        + current_fragment_html
    )

    payload = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                ],
            },
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AICorrectionError(f"OpenAI API request failed ({exc.code}): {details}") from exc
    except urllib.error.URLError as exc:
        raise AICorrectionError(f"OpenAI API request failed: {exc.reason}") from exc

    try:
        response_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AICorrectionError("OpenAI returned a non-JSON API response.") from exc

    text = _response_text_from_json(response_json)
    text = _strip_code_fences(text)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AICorrectionError(
            "OpenAI returned text, but it was not valid JSON in the expected schema.\n\n"
            f"Returned text:\n{text[:2000]}"
        ) from exc

    if not isinstance(result, dict):
        raise AICorrectionError("OpenAI returned JSON, but it was not an object.")
    return result



def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def collect_accessibility_review_warnings(fragment: Tag) -> list[str]:
    """Return deterministic warnings for common semantic HTML risks.

    These are intentionally warnings rather than blockers. Context still
    matters, so a staff reviewer makes the final decision.
    """
    warnings: list[str] = []

    br_tags = fragment.find_all("br")
    if len(br_tags) >= 3:
        warnings.append(
            f"The corrected page contains {len(br_tags)} <br> elements. Review whether ordinary paragraph wrapping, layout spacing, or pseudo-table rows should use semantic HTML instead."
        )
    for parent in fragment.find_all(["p", "div", "td", "li"]):
        child_br_count = len(parent.find_all("br"))
        if child_br_count >= 2:
            preview = re.sub(r"\s+", " ", parent.get_text(" ", strip=True))[:80]
            warnings.append(
                f"Repeated <br> elements appear inside <{parent.name}> near '{preview}'. Confirm that the line breaks are meaningful content rather than visual layout."
            )
            break

    previous_level: int | None = None
    for heading in fragment.find_all(HEADING_NAMES):
        text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
        if not text:
            warnings.append(f"An empty <{heading.name}> heading remains.")
        elif re.fullmatch(r"[\d\W_]+", text):
            warnings.append(f"Heading <{heading.name}> contains only numbers or symbols: '{text}'. Confirm that this is a genuine section heading.")
        elif len(text) > 120:
            warnings.append(f"Heading <{heading.name}> is unusually long ({len(text)} characters). Confirm that prose has not been marked as a heading.")
        level = int(heading.name[1])
        if previous_level is not None and level > previous_level + 1:
            warnings.append(f"Heading hierarchy skips from H{previous_level} to H{level} near '{text[:80]}'.")
        previous_level = level

    for index, table in enumerate(fragment.find_all("table"), start=1):
        if not table.find("th"):
            warnings.append(f"Table {index} does not include any <th> header cells. Confirm that headers are programmatically identified.")
        for th in table.find_all("th"):
            if not th.get("scope") and not th.get("id"):
                warnings.append(f"Table {index} includes a <th> without scope or id. Review header associations for complex tables.")
                break
        if not table.find("caption"):
            warnings.append(f"Table {index} has no <caption>. Add one when a table title or concise description would help users understand the table.")

    for index, image in enumerate(fragment.find_all("img"), start=1):
        if "alt" not in image.attrs:
            warnings.append(f"Image {index} is missing an alt attribute. Add meaningful alt text or alt=\"\" if the image is decorative.")
        else:
            alt = str(image.get("alt", "")).strip()
            if re.search(r"\b(unclear|unknown|image of image|possibly decorative|visual cue)\b", alt, flags=re.IGNORECASE):
                warnings.append(f"Image {index} has uncertain alt text: '{alt[:100]}'. Review it against the scan.")

    return _dedupe_preserve_order(warnings)


def validate_ai_corrected_fragment(
    *,
    corrected_fragment_html: str,
    expected_page_id: str,
    allowed_tokens: Iterable[str],
) -> tuple[str, list[str]]:
    """
    Extract and validate the expected page container from an AI response.

    Some models occasionally wrap the requested fragment in harmless document
    scaffolding such as <!doctype html>, <html>, or <body>. The review app only
    needs the expected page container, so discard outer wrappers rather than
    rejecting an otherwise usable correction. Unsafe content inside the page
    fragment is still rejected.
    """
    allowed_tokens = set(allowed_tokens)
    errors: list[str] = []
    warnings: list[str] = []
    html = _strip_code_fences(corrected_fragment_html or "")

    if not html.strip():
        raise AICorrectionError("The AI returned an empty HTML fragment.")

    if re.search(r"data:[^\"'\s>]+;base64,", html, flags=re.IGNORECASE):
        errors.append("The AI returned a raw Base64 data URI. Embedded-image tokens must remain tokenized.")

    soup = BeautifulSoup(html, "html.parser")
    replacement = soup.find(id=expected_page_id)

    if replacement is None:
        # If the model dropped the page ID but returned exactly one obvious
        # page-level element, recover it locally rather than discarding a useful
        # result. This is reported to the reviewer as a local validation note.
        top_level_tags = [child for child in soup.contents if isinstance(child, Tag)]
        if len(top_level_tags) == 1:
            candidate = top_level_tags[0]
            if candidate.name in {"html", "body"}:
                nested = [child for child in candidate.find_all(recursive=False) if isinstance(child, Tag)]
                if len(nested) == 1:
                    candidate = nested[0]
            replacement = candidate
        else:
            replacement = soup.find(True)

        if replacement is None:
            errors.append("The AI response could not be parsed into an HTML element.")
        else:
            replacement["id"] = expected_page_id
            warnings.append(f"The AI fragment did not preserve id='{expected_page_id}'. The ID was restored locally.")

    if not isinstance(replacement, Tag):
        errors.append("The AI response did not contain a usable page container element.")
    else:
        # Reject unsafe or document-level content only when it occurs inside the
        # extracted page fragment. Harmless outer <html>/<body> wrappers are
        # discarded when the page container is serialized below.
        if replacement.name.lower() in {"html", "head", "body", "style", "script", "iframe", "object", "embed", "base"}:
            errors.append("The AI did not return a usable page-level HTML container.")

        blocked = replacement.find(["html", "head", "body", "style", "script", "iframe", "object", "embed", "base"])
        if blocked is not None:
            errors.append(f"The AI returned a forbidden <{blocked.name}> element inside the page fragment.")

        for tag in replacement.find_all(True):
            for attr_name, attr_value in list(tag.attrs.items()):
                attr_name_l = attr_name.lower()
                if attr_name_l.startswith("on"):
                    errors.append(f"Unsafe event handler attribute found: {attr_name}")
                values = attr_value if isinstance(attr_value, list) else [attr_value]
                for value in values:
                    value_s = str(value).strip()
                    value_l = value_s.lower()
                    if attr_name_l in {"href", "src", "action"}:
                        if value_l.startswith("javascript:"):
                            errors.append(f"Unsafe javascript: URI found in {attr_name}.")
                        if value_l.startswith(("http://", "https://", "//")):
                            errors.append(f"External URL found in {attr_name}.")

        replacement["id"] = expected_page_id
        serialized = str(replacement)
        token_set = set(TOKEN_RE.findall(serialized))
        if token_set != allowed_tokens:
            missing = sorted(allowed_tokens - token_set)
            extra = sorted(token_set - allowed_tokens)
            if missing:
                errors.append("The AI removed required embedded-image tokens: " + ", ".join(missing))
            if extra:
                errors.append("The AI introduced unexpected embedded-image tokens: " + ", ".join(extra))

    if errors:
        raise AICorrectionError("\n".join(dict.fromkeys(errors)))

    warnings.extend(collect_accessibility_review_warnings(replacement))
    return str(replacement), _dedupe_preserve_order(warnings)


def _normalize_region_inventory(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            region = item.strip()
            if region:
                normalized.append({"region": region, "status": "included", "notes": ""})
            continue
        if not isinstance(item, dict):
            continue
        region = str(item.get("region", "")).strip()
        if not region:
            continue
        normalized.append(
            {
                "region": region,
                "status": str(item.get("status", "included")).strip() or "included",
                "notes": str(item.get("notes", "")).strip(),
            }
        )
    return normalized


def _normalize_excluded_regions(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            region = item.strip()
            if region:
                normalized.append({"region": region, "reason": ""})
            continue
        if not isinstance(item, dict):
            continue
        region = str(item.get("region", "")).strip()
        if not region:
            continue
        normalized.append({"region": region, "reason": str(item.get("reason", "")).strip()})
    return normalized


def normalize_ai_result(result: dict[str, Any]) -> dict[str, Any]:
    corrected_page_html = str(result.get("corrected_page_html", "")).strip()
    changes_summary = result.get("changes_summary", [])
    review_notes = result.get("review_notes", [])
    visible_text_regions = _normalize_region_inventory(result.get("visible_text_regions", []))
    intentionally_excluded_regions = _normalize_excluded_regions(result.get("intentionally_excluded_regions", []))
    needs_human_review = bool(result.get("needs_human_review", False))

    if isinstance(changes_summary, str):
        changes_summary = [changes_summary]
    if isinstance(review_notes, str):
        review_notes = [review_notes]

    if not isinstance(changes_summary, list):
        changes_summary = []
    if not isinstance(review_notes, list):
        review_notes = []

    cleaned = {
        "corrected_page_html": corrected_page_html,
        "visible_text_regions": visible_text_regions,
        "intentionally_excluded_regions": intentionally_excluded_regions,
        "changes_summary": [str(item).strip() for item in changes_summary if str(item).strip()],
        "review_notes": [str(item).strip() for item in review_notes if str(item).strip()],
        "needs_human_review": needs_human_review,
    }
    return cleaned

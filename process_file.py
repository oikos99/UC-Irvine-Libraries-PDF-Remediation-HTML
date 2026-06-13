from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


PROCESS_FILE_FORMAT = "uci-libraries-pdf-html-review-process"
PROCESS_FILE_VERSION = 1
PROCESS_FILE_EXTENSION = ".ucipdfreview"
MAX_ARCHIVE_ENTRIES = 500
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GiB safety guard against malformed archives.


class ProcessFileError(ValueError):
    """Raised when a saved review process file is invalid or incomplete."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def build_process_file_bytes(
    *,
    uploaded_name: str,
    job_filename: str,
    upload_key: str,
    output_key: str,
    original_pdf_bytes: bytes,
    original_generated_html_bytes: bytes,
    reviewed_html_bytes: bytes,
    page_meta: List[dict],
    edited_fragments: Dict[str, str],
    document_title: str,
    render_dpi: int,
) -> bytes:
    """Create a single local ZIP-based process file containing a resumable review workspace."""
    page_manifest: List[dict] = []
    for meta in page_meta:
        page_number = int(meta["page_number"])
        image_path = f"pages/page_{page_number:04d}.png"
        image_bytes = bytes(meta["image_bytes"])
        page_manifest.append(
            {
                "page_number": page_number,
                "image_path": image_path,
                "image_sha256": _sha256(image_bytes),
                "width": float(meta.get("width", 0.0)),
                "height": float(meta.get("height", 0.0)),
            }
        )

    fragments_bytes = _json_bytes(edited_fragments)
    manifest = {
        "format": PROCESS_FILE_FORMAT,
        "format_version": PROCESS_FILE_VERSION,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "uploaded_name": uploaded_name,
        "job_filename": job_filename,
        "upload_key": upload_key,
        "output_key": output_key,
        "document_title": document_title,
        "render_dpi": int(render_dpi),
        "page_count": len(page_manifest),
        "pages": page_manifest,
        "files": {
            "original_pdf": "source/original.pdf",
            "original_generated_html": "source/aws-generated.html",
            "reviewed_html_at_save": "state/reviewed-at-save.html",
            "edited_fragments": "state/edited-fragments.json",
        },
        "checksums": {
            "source/original.pdf": _sha256(original_pdf_bytes),
            "source/aws-generated.html": _sha256(original_generated_html_bytes),
            "state/reviewed-at-save.html": _sha256(reviewed_html_bytes),
            "state/edited-fragments.json": _sha256(fragments_bytes),
        },
        "notes": [
            "This file contains the original PDF, generated HTML including embedded Base64 assets, rendered page images, and the current edited page fragments.",
            "AI-assisted-correction click state is intentionally reset when the workspace is resumed.",
        ],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        archive.writestr("source/original.pdf", original_pdf_bytes)
        archive.writestr("source/aws-generated.html", original_generated_html_bytes)
        archive.writestr("state/reviewed-at-save.html", reviewed_html_bytes)
        archive.writestr("state/edited-fragments.json", fragments_bytes)
        for meta in page_meta:
            page_number = int(meta["page_number"])
            archive.writestr(f"pages/page_{page_number:04d}.png", bytes(meta["image_bytes"]))
    return buffer.getvalue()


def _read_required(archive: zipfile.ZipFile, path: str) -> bytes:
    try:
        return archive.read(path)
    except KeyError as exc:
        raise ProcessFileError(f"The saved process file is missing required item: {path}") from exc


def _validate_checksum(path: str, data: bytes, checksums: Dict[str, str]) -> None:
    expected = str(checksums.get(path, "")).strip()
    if expected and _sha256(data) != expected:
        raise ProcessFileError(f"The saved process file appears damaged: checksum mismatch for {path}.")


def load_process_file_bytes(process_file_bytes: bytes) -> dict:
    """Validate and load a saved local process file without extracting files to disk."""
    if not process_file_bytes:
        raise ProcessFileError("Choose a saved process file first.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(process_file_bytes), mode="r")
    except zipfile.BadZipFile as exc:
        raise ProcessFileError("The selected file is not a valid UC Irvine Libraries saved review process file.") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ProcessFileError("The saved process file contains too many entries and was rejected.")
        uncompressed_size = sum(info.file_size for info in infos)
        if uncompressed_size > MAX_UNCOMPRESSED_BYTES:
            raise ProcessFileError("The saved process file is too large after decompression and was rejected.")

        manifest_bytes = _read_required(archive, "manifest.json")
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProcessFileError("The saved process file has an unreadable manifest.") from exc

        if manifest.get("format") != PROCESS_FILE_FORMAT:
            raise ProcessFileError("The selected file is not a supported UC Irvine Libraries review process file.")
        if int(manifest.get("format_version", 0)) != PROCESS_FILE_VERSION:
            raise ProcessFileError(
                f"Unsupported saved process file version: {manifest.get('format_version')}. Expected version {PROCESS_FILE_VERSION}."
            )

        files = manifest.get("files") or {}
        checksums = manifest.get("checksums") or {}
        original_pdf_path = str(files.get("original_pdf", "source/original.pdf"))
        generated_html_path = str(files.get("original_generated_html", "source/aws-generated.html"))
        fragments_path = str(files.get("edited_fragments", "state/edited-fragments.json"))
        reviewed_html_path = str(files.get("reviewed_html_at_save", "state/reviewed-at-save.html"))

        original_pdf_bytes = _read_required(archive, original_pdf_path)
        original_generated_html_bytes = _read_required(archive, generated_html_path)
        fragments_bytes = _read_required(archive, fragments_path)
        reviewed_html_at_save_bytes = _read_required(archive, reviewed_html_path)
        for path, data in (
            (original_pdf_path, original_pdf_bytes),
            (generated_html_path, original_generated_html_bytes),
            (fragments_path, fragments_bytes),
            (reviewed_html_path, reviewed_html_at_save_bytes),
        ):
            _validate_checksum(path, data, checksums)

        try:
            edited_fragments = json.loads(fragments_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProcessFileError("The saved process file contains unreadable edited page fragments.") from exc
        if not isinstance(edited_fragments, dict):
            raise ProcessFileError("The saved edited page fragments are not in the expected format.")
        edited_fragments = {str(key): str(value) for key, value in edited_fragments.items()}

        page_meta: List[dict] = []
        for page in manifest.get("pages") or []:
            try:
                page_number = int(page["page_number"])
                image_path = str(page["image_path"])
                image_bytes = _read_required(archive, image_path)
            except (KeyError, TypeError, ValueError) as exc:
                raise ProcessFileError("The saved process file contains invalid page-image metadata.") from exc
            expected_page_checksum = str(page.get("image_sha256", "")).strip()
            if expected_page_checksum and _sha256(image_bytes) != expected_page_checksum:
                raise ProcessFileError(f"The saved process file appears damaged: checksum mismatch for {image_path}.")
            page_meta.append(
                {
                    "page_number": page_number,
                    "image_bytes": image_bytes,
                    "width": float(page.get("width", 0.0)),
                    "height": float(page.get("height", 0.0)),
                }
            )

        expected_page_count = int(manifest.get("page_count", len(page_meta)))
        if len(page_meta) != expected_page_count:
            raise ProcessFileError(
                f"The saved process file expected {expected_page_count} page images but contained {len(page_meta)}."
            )
        page_meta.sort(key=lambda item: item["page_number"])

        return {
            "uploaded_name": str(manifest.get("uploaded_name", "resumed-review.pdf")),
            "job_filename": str(manifest.get("job_filename", "")),
            "upload_key": str(manifest.get("upload_key", "")),
            "output_key": str(manifest.get("output_key", "")),
            "document_title": str(manifest.get("document_title", "Accessible HTML Alternative")),
            "render_dpi": int(manifest.get("render_dpi", 180)),
            "saved_at_utc": str(manifest.get("saved_at_utc", "")),
            "original_pdf_bytes": original_pdf_bytes,
            "original_generated_html_bytes": original_generated_html_bytes,
            "reviewed_html_at_save_bytes": reviewed_html_at_save_bytes,
            "edited_fragments": edited_fragments,
            "page_meta": page_meta,
        }

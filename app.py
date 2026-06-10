from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

from html_document import (
    build_document_preview,
    decode_html_bytes,
    embedded_assets_for_text,
    merge_reviewed_document,
    prepare_review_document,
    preview_style_html,
)
from compact_html_editor import compact_html_editor
from render_pages import render_pdf_pages
from zoomable_pdf_panel import zoomable_pdf_panel


APP_TITLE = "UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 2)"
DEFAULT_REGION = "us-west-2"
DEFAULT_BUCKET = "pdf2html-bucket-947047971739-us-west-2"
DEFAULT_MAX_FILE_MB = 100
DEFAULT_MAX_PAGES = 100
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_POLL_TIMEOUT_SECONDS = 20 * 60


@dataclass(frozen=True)
class AppConfig:
    aws_region: str
    bucket_name: str
    max_file_mb: int
    max_pages: int
    poll_interval_seconds: int
    poll_timeout_seconds: int


def read_setting(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if value is None:
        value = os.environ.get(name, default)
    return str(value)


def get_config() -> AppConfig:
    return AppConfig(
        aws_region=read_setting("AWS_REGION", DEFAULT_REGION),
        bucket_name=read_setting("PDF_TO_HTML_BUCKET", DEFAULT_BUCKET),
        max_file_mb=int(read_setting("MAX_FILE_MB", str(DEFAULT_MAX_FILE_MB))),
        max_pages=int(read_setting("MAX_PAGES", str(DEFAULT_MAX_PAGES))),
        poll_interval_seconds=int(read_setting("POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS))),
        poll_timeout_seconds=int(read_setting("POLL_TIMEOUT_SECONDS", str(DEFAULT_POLL_TIMEOUT_SECONDS))),
    )


def get_s3_client(config: AppConfig):
    access_key = read_setting("AWS_ACCESS_KEY_ID")
    secret_key = read_setting("AWS_SECRET_ACCESS_KEY")
    session_token = read_setting("AWS_SESSION_TOKEN")
    kwargs: dict[str, Any] = {"region_name": config.aws_region}
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    if session_token:
        kwargs["aws_session_token"] = session_token
    return boto3.client("s3", **kwargs)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_logo_data_url() -> str:
    logo_path = Path(__file__).parent / "assets" / "uci_libraries_logo.jpg"
    if not logo_path.exists():
        return ""
    encoded = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def apply_custom_theme() -> None:
    st.markdown(
        """
<style>
:root {
  --uci-blue: #00508f;
  --uci-light-blue: #78b9e6;
  --uci-pale-blue: #eef6fb;
  --uci-border: #d7e3ec;
}
.block-container { max-width: 1500px; padding-top: 3.75rem !important; }
.uci-header {
  display: flex;
  gap: 1.2rem;
  align-items: center;
  border-bottom: 4px solid var(--uci-blue);
  padding-bottom: 1rem;
  margin-bottom: 1.1rem;
}
.uci-header img { width: 112px; height: 112px; object-fit: contain; object-position: center; display: block; flex: 0 0 auto; border-radius: 3px; }
.uci-header h1 {
  color: var(--uci-blue);
  font-size: 2rem;
  margin: 0;
  padding-top: 0 !important;
}
#uc-irvine-libraries-pdf-to-html-accessibility-converter-ver-2 {
  padding-top: 0 !important;
}
.uci-header p { margin: 0.35rem 0 0 0; max-width: 980px; }
.review-intro {
  border-left: 5px solid var(--uci-blue);
  background: var(--uci-pale-blue);
  padding: 0.8rem 1rem;
  margin: 0.5rem 0 1rem 0;
}
[data-testid="stSidebar"] { border-right: 1px solid var(--uci-border); }
[data-testid="stExpander"] { border-color: var(--uci-border); }
.panel-caption {
  margin: 0.38rem 0 0 0;
  color: #6b7280;
  font-size: 0.875rem;
  text-align: center;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
  background-color: var(--uci-blue);
  border-color: var(--uci-blue);
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
  background-color: var(--uci-light-blue);
  border-color: var(--uci-light-blue);
  color: #102a43;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header() -> None:
    logo_data_url = get_logo_data_url()
    image = f'<img src="{logo_data_url}" alt="UC Irvine Libraries">' if logo_data_url else ""
    st.markdown(
        f"""
<div class="uci-header">
  {image}
  <div>
    <h1>UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 2)</h1>
    <p>
      Create a single-file HTML accessibility alternative from a PDF document, compare each original PDF page
      with its generated HTML, make corrections, preview the result, and download the reviewed HTML file.
    </p>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(config: AppConfig) -> int:
    with st.sidebar:
        st.header("Settings")
        st.subheader("Prototype access")
        if st.session_state.get("access_granted", False):
            st.success("Access granted.")
        else:
            entered_key = st.text_input(
                "Access key",
                type="password",
                autocomplete="off",
                help="Enter the shared prototype key provided by UC Irvine Libraries.",
                key="sidebar_access_key",
            )
            if st.button("Unlock", type="primary", use_container_width=True):
                expected_hash = read_setting("APP_ACCESS_KEY_SHA256")
                if not expected_hash:
                    st.error("The shared access key has not been configured.")
                elif hmac.compare_digest(sha256_text(entered_key), expected_hash.strip()):
                    st.session_state["access_granted"] = True
                    st.rerun()
                else:
                    st.error("Invalid access key.")

        st.subheader("Document limits")
        st.markdown(
            f"""
- PDF documents only
- Maximum file size: **{config.max_file_mb} MB**
- Maximum length: **{config.max_pages} pages**
- Upload one document at a time
            """
        )

        st.subheader("PDF page images")
        render_dpi = st.slider(
            "Render DPI",
            min_value=120,
            max_value=240,
            value=180,
            step=20,
            help="Higher values make the original-page screenshot sharper but use more memory.",
        )

        st.subheader("Review notice")
        st.write(
            "The AWS-generated HTML is loaded directly into this review screen. "
            "Download the reviewed HTML before leaving the page because edits are not saved after the session ends."
        )
        st.markdown("---")
        st.caption(
            "This tool is a customized version of the "
            "[ASU PDF Accessibility Remediation solution](https://www.remediate-pdf.com/home), adapted for UC Irvine Libraries. "
            "Backend processing is powered by AWS."
        )
    return render_dpi


def require_access() -> None:
    if st.session_state.get("access_granted", False):
        return
    st.info("Enter the shared prototype access key in the Settings sidebar to enable PDF processing.")
    st.stop()


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    stem = Path(base).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    stem = stem[:80] or "document"
    return f"{stem}.pdf"


def build_job_keys(filename: str) -> tuple[str, str, str]:
    cleaned = sanitize_filename(filename)
    stem = Path(cleaned).stem
    short_id = uuid.uuid4().hex[:10]
    job_filename = f"{stem}_{short_id}.pdf"
    upload_key = f"uploads/{job_filename}"
    output_key = f"remediated/{Path(job_filename).stem}.html"
    return job_filename, upload_key, output_key


def count_pdf_pages(pdf_bytes: bytes) -> int:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def validate_pdf(uploaded_file, config: AppConfig) -> tuple[bytes, int]:
    if uploaded_file is None:
        raise ValueError("Choose a PDF document.")
    if not uploaded_file.name.lower().endswith(".pdf"):
        raise ValueError("Only PDF documents are accepted.")
    pdf_bytes = uploaded_file.getvalue()
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > config.max_file_mb:
        raise ValueError(f"The PDF is {size_mb:.1f} MB. The maximum size is {config.max_file_mb} MB.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("The selected file does not appear to be a valid PDF.")
    try:
        pages = count_pdf_pages(pdf_bytes)
    except Exception as exc:
        raise ValueError("The PDF could not be opened. It may be corrupted or encrypted.") from exc
    if pages > config.max_pages:
        raise ValueError(f"The PDF has {pages} pages. The maximum is {config.max_pages} pages.")
    return pdf_bytes, pages


def upload_pdf(s3, config: AppConfig, upload_key: str, pdf_bytes: bytes) -> None:
    s3.put_object(
        Bucket=config.bucket_name,
        Key=upload_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )


def object_exists(s3, config: AppConfig, object_key: str) -> bool:
    try:
        s3.head_object(Bucket=config.bucket_name, Key=object_key)
        return True
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = exc.response.get("Error", {}).get("Code", "")
        if status == 404 or error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def wait_for_html(s3, config: AppConfig, output_key: str) -> bytes:
    started = time.monotonic()
    with st.status("Processing your PDF...", expanded=True) as status:
        st.write("Uploaded PDF to the private AWS processing bucket.")
        st.write("Waiting for the accessible HTML alternative.")
        elapsed_placeholder = st.empty()
        while True:
            elapsed = int(time.monotonic() - started)
            elapsed_placeholder.caption(f"Time elapsed: {elapsed // 60}:{elapsed % 60:02d}")
            if object_exists(s3, config, output_key):
                response = s3.get_object(Bucket=config.bucket_name, Key=output_key)
                html_bytes = response["Body"].read()
                status.update(label="Accessible HTML is ready for review.", state="complete")
                return html_bytes
            if elapsed >= config.poll_timeout_seconds:
                status.update(label="Processing has not completed yet.", state="error")
                raise TimeoutError(
                    "The HTML file was not ready before the polling timeout. Check the Pdf2HtmlPipeline CloudWatch logs."
                )
            time.sleep(config.poll_interval_seconds)


def clear_review_state() -> None:
    preserved = {"access_granted", "sidebar_access_key"}
    for key in list(st.session_state):
        if key not in preserved:
            del st.session_state[key]


def initialize_review_state(
    *,
    uploaded_name: str,
    job_filename: str,
    upload_key: str,
    output_key: str,
    pdf_bytes: bytes,
    html_bytes: bytes,
    page_meta: list[dict],
) -> None:
    review_document = prepare_review_document(decode_html_bytes(html_bytes), len(page_meta))
    review_id = uuid.uuid4().hex[:10]
    st.session_state["review_id"] = review_id
    st.session_state["uploaded_name"] = uploaded_name
    st.session_state["job_filename"] = job_filename
    st.session_state["last_upload_key"] = upload_key
    st.session_state["last_output_key"] = output_key
    st.session_state["original_pdf_bytes"] = pdf_bytes
    st.session_state["original_generated_html_bytes"] = html_bytes
    st.session_state["page_meta"] = page_meta
    st.session_state["review_document"] = review_document
    st.session_state["document_title_key"] = review_document["document_title"]
    for fragment in review_document["fragments"]:
        # Keep the canonical edited fragment separate from the text-area widget.
        # Streamlit removes a widget's state when the widget is temporarily hidden
        # (for example, while the rendered HTML preview is displayed).
        st.session_state[f"fragment_value_{review_id}_{fragment['element_id']}"] = fragment["html"]


def fragment_value_key(review_id: str, element_id: str) -> str:
    return f"fragment_value_{review_id}_{element_id}"


def fragment_editor_key(review_id: str, element_id: str) -> str:
    return f"fragment_editor_{review_id}_{element_id}"


def current_edited_fragments() -> Dict[str, str]:
    review_id = st.session_state["review_id"]
    review_document = st.session_state["review_document"]
    return {
        fragment["element_id"]: st.session_state.get(
            fragment_value_key(review_id, fragment["element_id"]), fragment["html"]
        )
        for fragment in review_document["fragments"]
    }


def build_reviewed_output() -> tuple[str, list[str]]:
    return merge_reviewed_document(
        st.session_state["review_document"],
        current_edited_fragments(),
        st.session_state.get("document_title_key", "Accessible HTML Alternative"),
    )


def render_review_workspace() -> None:
    review_document = st.session_state["review_document"]
    page_meta = st.session_state["page_meta"]
    review_id = st.session_state["review_id"]
    uploaded_name = st.session_state["uploaded_name"]

    action_left, action_right = st.columns([1, 5])
    with action_left:
        if st.button("Start over", use_container_width=True):
            clear_review_state()
            st.rerun()
    with action_right:
        st.success(f"Generated HTML is ready for review: **{uploaded_name}**")

    st.markdown(
        """
<div class="review-intro">
<strong>Review workflow:</strong> Open a PDF page, compare the original screenshot with the generated HTML source,
make corrections, and switch to <strong>Preview HTML</strong> to see the rendered result. The original Lambda output
remains available as a fallback download. Your reviewed file is assembled in memory and downloads directly to your computer.
</div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Document settings")
    st.text_input(
        "Browser title",
        key="document_title_key",
        help="This updates the HTML title element in the downloaded reviewed file.",
    )
    embedded_assets = review_document.get("embedded_assets", {})
    if embedded_assets:
        st.info(
            f"Compact embedded-image tokens are active. {len(embedded_assets)} Base64-encoded "
            f"asset{'s are' if len(embedded_assets) != 1 else ' is'} hidden behind inline pills while you edit. "
            "Preview and download restore the complete self-contained HTML automatically."
        )
        with st.expander("Embedded image token reference"):
            for asset in embedded_assets.values():
                st.code(f"{asset['token']}  →  {asset['label']}", language=None)

    for warning in review_document.get("warnings", []):
        st.warning(warning)

    st.subheader("Review and edit")
    fragment_by_number = {}
    for fragment in review_document["fragments"]:
        fragment_by_number.setdefault(fragment["page_number"], fragment)

    for meta in page_meta:
        page_number = meta["page_number"]
        fragment = fragment_by_number.get(page_number)
        expander_label = fragment["label"] if fragment else f"PDF page {page_number} - HTML container not detected"
        with st.expander(expander_label, expanded=(page_number == 1)):
            left, right = st.columns([1, 1], gap="large")
            with left:
                zoomable_pdf_panel(
                    image_bytes=meta["image_bytes"],
                    page_number=page_number,
                    height=650,
                    key=f"zoom_pdf_{review_id}_{page_number}",
                )
            with right:
                if fragment is None:
                    st.error("The generated HTML does not expose an editable container for this PDF page.")
                else:
                    value_key = fragment_value_key(review_id, fragment["element_id"])
                    editor_key = f"compact_{fragment_editor_key(review_id, fragment['element_id'])}"
                    current_fragment = st.session_state.get(value_key, fragment["html"])
                    page_assets = embedded_assets_for_text(review_document, current_fragment)
                    edited_fragment = compact_html_editor(
                        value=current_fragment,
                        tokens=page_assets,
                        preview_styles=preview_style_html(review_document),
                        height=650,
                        key=editor_key,
                    )
                    if edited_fragment != current_fragment:
                        st.session_state[value_key] = edited_fragment

            # Render captions in one shared row after both panels. Keeping the
            # captions outside the independently sized component columns makes
            # their baselines align even if the two component iframes report
            # slightly different outer heights to Streamlit.
            caption_left, caption_right = st.columns([1, 1], gap="large")
            with caption_left:
                st.markdown(
                    f'<p class="panel-caption">Rendered original PDF page {page_number}</p>',
                    unsafe_allow_html=True,
                )
            with caption_right:
                if fragment is not None:
                    st.markdown(
                        '<p class="panel-caption">Rendered preview of the current edited HTML for this page.</p>',
                        unsafe_allow_html=True,
                    )

    edited_fragments = current_edited_fragments()
    reviewed_html, export_warnings = merge_reviewed_document(
        review_document,
        edited_fragments,
        st.session_state.get("document_title_key", "Accessible HTML Alternative"),
    )
    reviewed_html_bytes = reviewed_html.encode("utf-8")
    base_name = Path(uploaded_name).stem

    st.subheader("Download")
    st.write("Download the reviewed HTML before closing this tab. The reviewed file is not written back to S3.")
    col_reviewed, col_original = st.columns(2)
    with col_reviewed:
        st.download_button(
            "Download Reviewed HTML File",
            data=reviewed_html_bytes,
            file_name=f"{base_name}_reviewed.html",
            mime="text/html",
            type="primary",
            use_container_width=True,
        )
    with col_original:
        st.download_button(
            "Download Original AWS-Generated HTML",
            data=st.session_state["original_generated_html_bytes"],
            file_name=f"{base_name}_generated.html",
            mime="text/html",
            use_container_width=True,
        )

    if export_warnings:
        with st.expander("Review export warnings"):
            st.write("These checks are warnings, not blockers. Review them before publishing the file.")
            for warning in export_warnings:
                st.warning(warning)

    with st.expander("Preview complete reviewed HTML"):
        st.caption("This preview reflects the merged document that will download from the reviewed HTML button.")
        if st.checkbox("Render complete document preview", key=f"full_preview_{review_id}"):
            components.html(build_document_preview(reviewed_html), height=800, scrolling=True)

    with st.expander("Processing details"):
        st.code(
            "\n".join(
                [
                    f"Uploaded: {st.session_state.get('last_upload_key', '')}",
                    f"Generated: {st.session_state.get('last_output_key', '')}",
                    "Reviewed HTML: assembled in the active Streamlit session and downloaded directly",
                ]
            )
        )


def render_upload_screen(config: AppConfig, render_dpi: int) -> None:
    uploaded_file = st.file_uploader(
        "Upload a PDF document",
        type=["pdf"],
        accept_multiple_files=False,
        help=f"Maximum {config.max_file_mb} MB and {config.max_pages} pages.",
    )
    if uploaded_file is None:
        st.info("Upload a PDF to begin.")
        return

    if st.button("Convert and Review HTML", type="primary"):
        try:
            pdf_bytes, pages = validate_pdf(uploaded_file, config)
            job_filename, upload_key, output_key = build_job_keys(uploaded_file.name)
            s3 = get_s3_client(config)
            st.info(f"Uploading **{uploaded_file.name}** ({pages} page{'s' if pages != 1 else ''}) for processing.")
            upload_pdf(s3, config, upload_key, pdf_bytes)
            html_bytes = wait_for_html(s3, config, output_key)
            with st.status("Preparing the page-by-page review workspace...", expanded=True) as status:
                st.write("Rendering the original PDF pages as images for comparison.")
                page_meta = render_pdf_pages(pdf_bytes, dpi=render_dpi)
                st.write("Loading the AWS-generated HTML into editable page sections.")
                initialize_review_state(
                    uploaded_name=uploaded_file.name,
                    job_filename=job_filename,
                    upload_key=upload_key,
                    output_key=output_key,
                    pdf_bytes=pdf_bytes,
                    html_bytes=html_bytes,
                    page_meta=page_meta,
                )
                status.update(label="Review workspace is ready.", state="complete")
            st.rerun()
        except TimeoutError as exc:
            st.error(str(exc))
        except NoCredentialsError:
            st.error("AWS credentials were not found. Add restricted credentials to Streamlit Secrets or run this app with an AWS IAM role.")
        except (BotoCoreError, ClientError) as exc:
            st.error(f"AWS request failed: {exc}")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")


def main() -> None:
    favicon = Path(__file__).parent / "assets" / "uci_libraries_favicon.png"
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=str(favicon) if favicon.exists() else "",
        layout="wide",
    )
    config = get_config()
    apply_custom_theme()
    render_page_header()
    render_dpi = render_sidebar(config)
    require_access()

    if st.session_state.get("review_document"):
        render_review_workspace()
    else:
        render_upload_screen(config, render_dpi)


if __name__ == "__main__":
    main()

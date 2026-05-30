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
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from pypdf import PdfReader
import streamlit as st


APP_TITLE = "UC Irvine Libraries PDF-to-HTML Accessibility Converter"
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
        poll_interval_seconds=int(
            read_setting("POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS))
        ),
        poll_timeout_seconds=int(
            read_setting("POLL_TIMEOUT_SECONDS", str(DEFAULT_POLL_TIMEOUT_SECONDS))
        ),
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
          --uci-blue: #00386c;
          --uci-blue-hover: #00508f;
          --uci-gold: #f6aa0d;
          --uci-light-blue: #78b9e6;
          --uci-control-border: #d9d9d9;
          --uci-control-text: #111111;
        }

        .stApp {
          background: #ffffff;
        }

        .block-container {
          max-width: 1260px;
          padding-top: 3.7rem;
          padding-bottom: 3rem;
        }

        /* Sidebar shell matching the existing UCI Streamlit prototype. */
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div {
          background-color: var(--uci-blue) !important;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stMarkdown p {
          color: #ffffff !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
          color: var(--uci-gold) !important;
        }

        [data-testid="stSidebar"] a,
        [data-testid="stSidebar"] a:visited {
          color: #ffffff !important;
        }

        [data-testid="stSidebar"] a:hover,
        [data-testid="stSidebar"] a:focus {
          color: #ffffff !important;
          text-decoration: underline !important;
        }

        [data-testid="stSidebar"] label {
          font-weight: 600 !important;
        }

        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] [data-baseweb="base-input"],
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
          background-color: #ffffff !important;
          color: var(--uci-control-text) !important;
          border-color: var(--uci-control-border) !important;
          caret-color: var(--uci-control-text) !important;
        }

        [data-testid="stSidebar"] input::placeholder,
        [data-testid="stSidebar"] textarea::placeholder {
          color: #555555 !important;
          opacity: 1 !important;
        }

        [data-testid="stSidebar"] [data-baseweb="input"] button,
        [data-testid="stSidebar"] [data-baseweb="input"] [role="button"] {
          background-color: #ffffff !important;
          color: var(--uci-control-text) !important;
          border-left: 1px solid var(--uci-control-border) !important;
        }

        [data-testid="stSidebar"] [data-baseweb="input"] button svg,
        [data-testid="stSidebar"] [data-baseweb="input"] button svg path,
        [data-testid="stSidebar"] [data-baseweb="input"] [role="button"] svg,
        [data-testid="stSidebar"] [data-baseweb="input"] [role="button"] svg path {
          color: var(--uci-control-text) !important;
          fill: var(--uci-control-text) !important;
          stroke: var(--uci-control-text) !important;
        }

        [data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg,
        [data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] svg,
        [data-testid="stSidebar"] label button[aria-label*="help"] svg,
        [data-testid="stSidebar"] label button[title*="help"] svg {
          color: #ffffff !important;
          fill: none !important;
          stroke: #ffffff !important;
        }

        /* Sidebar Unlock button */
        [data-testid="stSidebar"] div.stButton > button[kind="primary"],
        [data-testid="stSidebar"] div.stButton > button[data-testid="baseButton-primary"] {
          background-color: #00508f !important;
          border-color: #00508f !important;
          color: #ffffff !important;
        }

        [data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover,
        [data-testid="stSidebar"] div.stButton > button[data-testid="baseButton-primary"]:hover {
          background-color: #78b9e6 !important;
          border-color: #78b9e6 !important;
          color: #00386c !important;
        }

        div.stButton > button[kind="primary"],
        div.stButton > button[data-testid="baseButton-primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] {
          background-color: var(--uci-blue) !important;
          color: #ffffff !important;
          border: 1px solid var(--uci-blue) !important;
          font-weight: 700 !important;
        }

        div.stButton > button[kind="primary"]:hover,
        div.stButton > button[data-testid="baseButton-primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
          background-color: var(--uci-blue-hover) !important;
          border-color: var(--uci-blue-hover) !important;
          color: #ffffff !important;
        }

        .uci-header {
          display: flex;
          align-items: center;
          gap: 1rem;
          width: 100%;
          max-width: 100%;
          margin-bottom: 0.75rem;
        }

        .uci-header img {
          width: clamp(82px, 9vw, 110px);
          height: clamp(82px, 9vw, 110px);
          flex: 0 0 auto;
          object-fit: cover;
          border-radius: 10px;
        }

        .uci-header-text {
          flex: 1 1 auto;
          min-width: 0;
        }

        .uci-header-text h1 {
          margin: 0;
          line-height: 1.08;
          font-size: clamp(1.55rem, 3vw, 2.6rem);
          max-width: 100%;
        }

        .uci-subtitle {
          margin-top: 0.75rem;
          max-width: 100%;
          font-size: 1rem;
          line-height: 1.45;
        }

        .uci-helper {
          color: #4a5568;
          margin-top: 0.35rem;
        }

        .uci-access-note {
          background: #e7f0fb;
          border-left: 4px solid var(--uci-blue);
          color: #00386c;
          padding: 0.75rem 0.9rem;
          margin: 0.4rem 0 1rem 0;
          border-radius: 4px;
        }

        div[data-testid="stFileUploader"] {
          background: #f3f5f8;
          border-radius: 10px;
          padding: 0.4rem 0.7rem;
        }

        @media (max-width: 900px) {
          .uci-header {
            align-items: flex-start;
          }

          .uci-header-text h1 {
            font-size: clamp(1.35rem, 4.8vw, 2rem);
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header() -> None:
    logo_data_url = get_logo_data_url()
    img_html = (
        f'<img src="{logo_data_url}" alt="UC Irvine Libraries logo">'
        if logo_data_url
        else ""
    )

    st.markdown(
        f"""
        <div class="uci-header">
          {img_html}
          <div class="uci-header-text">
            <h1>UC Irvine Libraries<br>PDF-to-HTML Accessibility Converter</h1>
          </div>
        </div>
        <div class="uci-subtitle">
          <p>
            This tool creates a single-file HTML accessibility alternative from a PDF document
            using the UC Irvine Libraries prototype AWS processing pipeline. The generated HTML
            should be reviewed before publication.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(config: AppConfig) -> None:
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

        st.subheader("Review notice")
        st.write(
            "This is an AI-assisted prototype. Review the generated HTML before "
            "sharing it as an accessible alternative."
        )

        st.markdown("---")
        st.caption(
            "This tool is a customized version of the "
            "[ASU PDF Accessibility Remediation solution]"
            "(https://www.remediate-pdf.com/home), adapted for UC Irvine Libraries. "
            "Backend processing is powered by AWS."
        )


def require_access() -> None:
    if st.session_state.get("access_granted", False):
        return

    st.markdown(
        """
        <div class="uci-access-note">
          Enter the shared prototype access key in the Settings sidebar to enable PDF processing.
        </div>
        """,
        unsafe_allow_html=True,
    )
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
        raise ValueError(
            f"The PDF is {size_mb:.1f} MB. The maximum size is {config.max_file_mb} MB."
        )

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("The selected file does not appear to be a valid PDF.")

    try:
        pages = count_pdf_pages(pdf_bytes)
    except Exception as exc:
        raise ValueError("The PDF could not be opened. It may be corrupted or encrypted.") from exc

    if pages > config.max_pages:
        raise ValueError(
            f"The PDF has {pages} pages. The maximum is {config.max_pages} pages."
        )

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
                status.update(label="Accessible HTML is ready.", state="complete")
                return html_bytes

            if elapsed >= config.poll_timeout_seconds:
                status.update(label="Processing has not completed yet.", state="error")
                raise TimeoutError(
                    "The HTML file was not ready before the polling timeout. "
                    "Check the Pdf2HtmlPipeline CloudWatch logs."
                )

            time.sleep(config.poll_interval_seconds)


def reset_job() -> None:
    for key in (
        "completed_html",
        "download_filename",
        "last_upload_key",
        "last_output_key",
    ):
        st.session_state.pop(key, None)


def main() -> None:
    favicon = Path("assets/uci_libraries_favicon.png")

    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=str(favicon) if favicon.exists() else "📄",
        layout="wide",
    )

    config = get_config()
    apply_custom_theme()
    render_sidebar(config)
    render_page_header()
    require_access()

    uploaded_file = st.file_uploader(
        "Upload a PDF document",
        type=["pdf"],
        accept_multiple_files=False,
        help=f"Maximum {config.max_file_mb} MB and {config.max_pages} pages.",
    )

    if uploaded_file is None:
        st.info("Upload a PDF to begin.")
        st.stop()

    if st.button("Convert to HTML", type="primary"):
        reset_job()

        try:
            pdf_bytes, pages = validate_pdf(uploaded_file, config)
            job_filename, upload_key, output_key = build_job_keys(uploaded_file.name)
            s3 = get_s3_client(config)

            st.info(
                f"Uploading **{uploaded_file.name}** ({pages} page"
                f"{'s' if pages != 1 else ''}) for processing."
            )

            upload_pdf(s3, config, upload_key, pdf_bytes)
            html_bytes = wait_for_html(s3, config, output_key)

            st.session_state["completed_html"] = html_bytes
            st.session_state["download_filename"] = f"{Path(job_filename).stem}.html"
            st.session_state["last_upload_key"] = upload_key
            st.session_state["last_output_key"] = output_key

        except TimeoutError as exc:
            st.error(str(exc))
        except NoCredentialsError:
            st.error(
                "AWS credentials were not found. Add restricted credentials to "
                "Streamlit Secrets or run this app with an AWS IAM role."
            )
        except (BotoCoreError, ClientError) as exc:
            st.error(f"AWS request failed: {exc}")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")

    html_bytes = st.session_state.get("completed_html")
    download_filename = st.session_state.get("download_filename", "accessible.html")

    if html_bytes:
        st.success("Your accessible HTML alternative is ready.")
        st.download_button(
            "Download HTML File",
            data=html_bytes,
            file_name=download_filename,
            mime="text/html",
            type="primary",
        )

        with st.expander("Processing details"):
            st.code(
                "\n".join(
                    [
                        f"Uploaded: {st.session_state.get('last_upload_key', '')}",
                        f"Generated: {st.session_state.get('last_output_key', '')}",
                    ]
                )
            )


if __name__ == "__main__":
    main()

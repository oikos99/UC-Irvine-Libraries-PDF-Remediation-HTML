# UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 2)

A Streamlit frontend for the existing UC Irvine Libraries AWS PDF-to-HTML accessibility pipeline. This app adds an optional human-review workflow without changing the Lambda backend architecture.

## What the app does

1. The staff user uploads a PDF once.
2. The Streamlit app retains the PDF bytes in the active browser session and uploads the PDF to the existing private S3 `uploads/` prefix.
3. The existing `Pdf2HtmlPipeline` Lambda processes the PDF and writes the self-contained HTML file to the existing private S3 `remediated/` prefix.
4. The Streamlit app quietly reads that generated HTML file into memory.
5. The app displays each original PDF page screenshot beside its editable generated HTML page container.
6. Staff can switch each page between source-editing mode and rendered-preview mode.
7. The reviewed complete HTML file is assembled in memory and downloaded directly to the user's computer.

The reviewed file is **not** written back to S3. The S3 bucket remains the temporary handoff between the existing frontend and Lambda backend.

## Existing backend contract

```text
uploads/<unique-id>.pdf
    -> existing Pdf2HtmlPipeline Lambda
    -> remediated/<unique-id>.html
```

This review app uses the same contract as the existing simple HTML-download frontend.

## Files

- `app.py` — Streamlit orchestration, AWS handoff, and review workspace
- `html_document.py` — split, preview, validate, and merge the generated HTML page containers
- `render_pages.py` — render original PDF pages as PNG images in memory
- `requirements.txt` — Python dependencies
- `secrets.toml.example` — Streamlit secrets template
- `iam/streamlit_s3_policy.json` — same restricted S3 permissions used by the existing simple frontend
- `assets/` — UC Irvine Libraries logo and favicon

## Deploy on Streamlit Community Cloud

1. Create a new GitHub repository for this review frontend.
2. Upload the contents of this package.
3. In Streamlit Community Cloud, create an app from the repository.
4. Use `app.py` as the main file.
5. Open the app's **Settings -> Secrets** page.
6. Copy the contents of `secrets.toml.example`.
7. Paste them into Streamlit Secrets.
8. Replace the blank values with the same restricted IAM credentials and shared-key hash used by the existing simple frontend.
9. Deploy.

No Lambda redeployment is required.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
python -m streamlit run app.py
```

On Windows, activate the virtual environment with:

```text
.venv\Scripts\activate
```

Do not commit `.streamlit/secrets.toml`.

## Generate the shared access-key hash

Use AWS CloudShell:

```bash
ACCESS_KEY=$(openssl rand -base64 24)
echo "PRIVATE ACCESS KEY TO SHARE:"
echo "$ACCESS_KEY"
echo
printf '%s' "$ACCESS_KEY" | sha256sum | awk '{print $1}'
```

Store the resulting hash in:

```text
APP_ACCESS_KEY_SHA256 = "PASTE_HASH_HERE"
```

## S3 permissions

The included IAM policy is intentionally unchanged from the existing simple frontend. It grants only:

- `s3:PutObject` to `uploads/*`
- `s3:GetObject` to `remediated/*`
- `s3:ListBucket` limited to the `remediated/*` prefix

The review app does not need permission to write reviewed HTML files to S3.

## Session limitation

The reviewed HTML exists only in the active Streamlit session until the user downloads it. Closing the browser tab, resetting the app, or redeploying the app can discard unsaved edits.

## Recommended early testing

Start with a small PDF that has two or three pages. Confirm that:

1. The app reaches the same Lambda backend successfully.
2. Each PDF screenshot appears beside the corresponding generated HTML source.
3. Source edits and rendered output remain populated through repeated **Edit HTML source** → **Preview HTML** → **Edit HTML source** → **Preview HTML** cycles.
4. The reviewed download preserves the complete document, embedded images, navigation, title, and edited page content.
5. The original generated HTML fallback download remains unchanged.

## Compact embedded-image tokens

The page source editor hides long embedded Base64 data URIs behind compact inline pills such as:

```text
🖼 Image 1 · PNG · 184 KB
```

The pills are display-only editor tokens. The app retains each original Base64 data URI in the active Streamlit session and restores it automatically when the reviewer opens **Preview HTML** or downloads the reviewed file. The exported HTML remains a self-contained single-file document.

Each page opens in **Preview HTML** mode by default. Select **Edit HTML source** to modify the tokenized HTML source.

This feature is implemented with a small self-contained Streamlit custom component:

- `compact_html_editor.py` — Python wrapper for the custom editor
- `components/compact_html_editor/index.html` — inline-pill editor and preview UI

No JavaScript build process, external JavaScript package, Lambda change, or additional AWS permission is required.

### Zoomable original PDF page panel

Each original PDF page is rendered in a fixed-height image panel with **Zoom out**, **Fit width**, and **Zoom in** controls. When the image panel has keyboard focus, `Ctrl`/`Command` + `+`, `-`, and `0` also adjust or reset the zoom. The panel scrolls when an enlarged image exceeds its visible area.

## Optional AI-assisted page correction

Each page accordion includes **AI-assisted Correction** and **Restore Original Page** controls. The AI correction is optional and runs only when a staff reviewer presses the button for a specific page. The request sends the current tokenized page HTML and the rendered page image to OpenAI. Raw embedded Base64 data is not sent inside the editable HTML fragment.

The OpenAI API key field and its explanatory text appear only after the shared prototype access key has been entered successfully.

The correction prompt treats the screenshot as the authoritative visual source and the existing HTML as a draft. The model is instructed to recover meaningful text regions that OCR omitted, improve semantic HTML, preserve every embedded-image token, and report uncertainty rather than silently inventing content.

After one successful AI correction, the correction button becomes disabled for that page to prevent repeat charges. **Restore Original Page** reverts the working fragment to the original AWS-generated HTML while preserving the one-call-per-page limit.

The collapsed **AI correction details** section displays:

- visible text region inventory
- intentionally excluded regions
- AI change summary
- AI review notes
- local validation notes

The frontend performs deterministic safety validation before applying an AI result. It blocks unsafe elements, external URLs, raw Base64 values returned by the model, and broken embedded-image token sets. It also warns about suspicious `<br>` overuse, numeric-only or unusually long headings, heading-level skips, tables without useful header markup, and missing or uncertain image alt text. These checks are warnings rather than a WCAG conformance guarantee; staff review remains required.

### Protected backend image sizing

The AWS backend calculates each extracted image's relative width from its crop pixels compared with the original PDF page pixels and records values such as `data-bda-relative-width="31.40"` plus an inline width style. The frontend treats this crop geometry as deterministic protected metadata. AI-assisted correction may improve alt text and surrounding semantic structure, but it is not allowed to enlarge, shrink, or restyle the embedded image dimensions. The app re-applies the original protected image presentation after an AI rewrite and again during final export.

# Changelog

## v16

- Hide the OpenAI API key field and OpenAI explanatory text until the shared prototype access key has been entered successfully.
- Protect backend-calculated BDA image sizing metadata by stable embedded-image token.
- Reapply original image class, style, width, height, `data-bda-relative-width`, and `data-image-width-source` attributes immediately after AI-assisted correction.
- Reapply protected BDA image presentation again during final reviewed-HTML export so later source edits cannot silently discard deterministic crop sizing.
- Expand the AI prompt to prohibit guessed image resizing while still allowing semantic restructuring and improved alt text.

## v15

- Treat the rendered PDF page screenshot as the authoritative source for AI-assisted correction while retaining the current HTML as an editable draft.
- Permit the AI correction pass to recover meaningful text visibly present in the scan even when OCR omitted it from the original HTML.
- Require a visible-text-region inventory and intentionally excluded-region list in the AI response.
- Display the region inventory inside the collapsed **AI correction details** expander.
- Add deterministic local warnings for suspicious `<br>` overuse, questionable headings, heading-level skips, weak table markup, and missing or uncertain image alt text.
- Apply the same semantic warnings during final reviewed-HTML export so manually edited and non-AI pages are checked too.

## v14

- Move AI change summaries, AI review notes, and local validation notes into a collapsed **AI correction details** expander.
- Remove the empty summary-box artifact caused by trying to wrap Streamlit elements in a raw HTML div.
- Right-align the **AI-assisted Correction** and **Restore Original Page** actions within each page accordion.

## v11

- Remove the top padding from the main converter `<h1>` heading while retaining the safer page-level top spacing that prevents logo clipping.

## v10

- Rename the interface to **UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 2)**.
- Add safer top spacing below the Streamlit toolbar so the header logo is not clipped.
- Render the header logo with `object-fit: contain` so the complete logo remains visible.

## v9

- Render both panel captions in a shared Streamlit caption row below the side-by-side components so their baselines align horizontally.

## v7

- Display **Preview HTML** to the left of **Edit HTML source**.
- Open each page in rendered HTML preview mode by default.
- Remove the embedded-image-token count notice above the compact editor.

## v6

- Render the page-preview caption directly in Streamlit below the compact editor component.
- Remove the duplicate caption from inside the custom component iframe so it cannot be clipped by component-height calculations.

## v5

- Fixed repeated HTML previews becoming blank after returning to edit mode.
- Preview iframe now receives a fresh Blob URL for every render instead of repeatedly reusing `srcdoc`.
- Protected the editor against transient empty rerender arguments from Streamlit so the hidden source is not accidentally cleared.
- Dynamically reports the component height so the caption below the preview remains visible.
- Restored the caption: `Rendered preview of the current edited HTML for this page.`

## v4

- Added local editor/preview toggle synchronization fixes.

## v3

- Added compact embedded-image tokens represented as protected inline pills.

## v8

- Replaced the static original-page screenshot with an accessible zoomable image panel.
- Added Zoom out, Fit width, and Zoom in controls plus keyboard zoom shortcuts within the focused image panel.
- Matched the original-page and HTML-review panel heights so their lower edges align.
- Centered both panel captions.

## v13
- Fixed a false-positive AI validation error when a model wraps a corrected page fragment in harmless `<!doctype html>`, `<html>`, or `<body>` scaffolding.
- The AI correction importer now extracts the expected page container and discards outer wrappers before applying the correction.
- Unsafe tags, external assets, raw Base64 data URIs, and broken embedded-image token sets remain blocked.

## v17
- Added safe fallbacks when custom Streamlit component folders are missing from a deployed repository.
- Prevented import-time crashes from `components.declare_component(...)` when nested component directories were omitted during deployment.
- Retained the full `components/compact_html_editor/` and `components/zoomable_pdf_panel/` folders in the deployment package.

## v18
- Added an app-level CSS fallback that hardcodes UC Irvine colors even when `.streamlit/config.toml` is omitted or not loaded by Streamlit Cloud.
- Added direct slider styling for the thumb, active bar, and value label.
- Added branded focus styling for common form controls.

## v19
- Replaced the CSS-only slider fallback with a runtime UCI brand-color synchronizer.
- The synchronizer recalculates Streamlit's generated slider `linear-gradient(...)` in UC Irvine blue after rerenders and slider movements.
- Preserves the active slider percentage while replacing the default red accent.

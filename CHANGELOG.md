## v34

- Rename the interface to **UC Irvine Libraries PDF-to-HTML Accessibility Converter (Ver. 3)**.
- Restyle **Save Process File for Later Review** with a softer `#d7e3ec` default background and `rgb(0, 80, 143)` text while retaining the accessible dark-blue hover and keyboard-focus state.

## v25

- Hide the **Document limits** sidebar section after a saved `.ucipdfreview` workspace is loaded, since no new PDF upload is needed during a resumed review.

## v24

- Style **Save Process File for Later Review** with UC Irvine light blue (`#78b9e6`) and dark readable text; use UC Irvine dark blue with white text for hover and keyboard focus.
- Move **Preview complete reviewed HTML** and **Review export warnings** directly below the page-review accordions, separated from the pages by a subtle divider.
- Always display the export-warning expander and show a no-warning confirmation when no automated warnings are present.
- Add a dedicated **Processing information** section with a collapsed **View processing details** expander at the end of the workspace.
- Hide document limits, PDF-page rendering controls, and the review notice until the shared access key has been unlocked.
- Style **Load Saved Process File** as a primary action so its default and hover colors match **Unlock**.

# Changelog

## v23

- Add **Save Process File for Later Review** so staff can pause a long remediation session and download a resumable local `.ucipdfreview` archive.
- Store the original PDF, original AWS-generated HTML including embedded Base64 assets, rendered page images, page geometry, current edited page fragments, document title, AWS handoff metadata, and a reviewed-HTML snapshot in the process file.
- Add checksums and archive-size guards when loading saved process files.
- Show **Resume saved review** only before access-key unlock. Loading a valid process file reconstructs the review workspace locally without calling AWS.
- Preserve the original AWS-generated baseline after resume so **Restore Original Page** continues to work.
- Intentionally reset AI-assisted-correction click state after resume so pages receive a fresh one-click AI allowance.
- Leave drag-to-pan behavior unchanged while prioritizing the save-and-resume workflow.

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

## v20
- Removed an overbroad slider CSS selector that painted the slider value bubble blue and reduced numeric readability.
- Kept the runtime UCI-blue gradient synchronizer for the actual slider track.
- Preserved the blue slider thumb and readable blue value text on the normal background.

## v22
- Versioned the zoomable PDF custom component name to force Streamlit Cloud and browsers to load the updated iframe instead of a cached earlier copy.
- Added reliable mouse click-and-drag panning handlers for desktop browsers.
- Retained pointer-event panning for touch and pen input.
- Applied grab and grabbing cursors explicitly throughout the PDF viewer surface.

## v26
- Hide **Start over** when a workspace was resumed from a saved `.ucipdfreview` process file.
- Prevent the resumed-workspace path from exposing the fresh PDF-upload workflow before the shared access key is unlocked.

## v27
- Removed the document-limit bullet list from the Settings sidebar.
- Moved the backend PDF constraints into the main upload area beside the file uploader.
- Clarified that the limits are backend-processing limits: 100 MB per PDF and 100 pages per PDF.
- Set Streamlit's native `server.maxUploadSize` to 100 MB so the uploader's built-in size label matches the backend limit instead of showing 200 MB.

## v28
- Fixed glitchy HTML source typing caused by sending a custom-component update to Streamlit after every 250 ms typing pause.
- HTML source keystrokes now remain local while the editor is active.
- Page HTML synchronizes when the reviewer leaves the editor or selects Preview HTML.
- Added a small synchronization status next to the editor mode controls.
- Versioned the compact editor component registration to force browsers and Streamlit Cloud to load the revised iframe.

## v31
- Removed the always-visible “Page edits synchronized” message from the compact HTML editor.
- Removed the redundant helper sentence about synchronizing when leaving the editor or selecting Preview HTML.
- Retained the “Unsaved page edits” warning only while the editor has local pending changes.
- Versioned the compact editor component registration so deployed apps load the revised UI.


## v32
- Restored the clean-state **Page edits synchronized** status in the compact HTML editor.
- Kept the redundant helper sentence removed.
- Retained **Unsaved page edits** while local pending changes exist.
- Versioned the compact editor component registration so deployed apps load the revised UI.
